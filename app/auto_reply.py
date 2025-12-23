from __future__ import annotations

import re
import threading
from collections import deque
from datetime import datetime
from queue import SimpleQueue, Empty
from typing import Optional, Dict, Any

from flask import Flask

from .database import get_auto_reply_config, insert_message, get_ai_config, get_listener_by_command
from .twilio_client import TwilioService
from .ai_service import AIResponder, AIReplyError, send_ai_generated_sms

# Type alias for queued inbound payloads
InboundPayload = Dict[str, Any]
# Accept standard E.164 numbers (+country up to 15 digits). Reject empties/short.
ALLOWED_NUMBER_RE = re.compile(r"^\+[1-9]\d{6,14}$")

_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S"


def _utc_now_iso() -> str:
    return datetime.utcnow().strftime(_TIMESTAMP_FORMAT)


def _parse_iso_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def start_auto_reply_worker(app: Flask) -> None:
    """Start a background worker that reacts to inbound messages without polling.

    The worker waits on an in-memory queue fed by webhook `/twilio/inbound`.
    It sends a configured auto-reply SMS when `auto_reply_config.enabled` is true
    and the sender number is valid E.164.
    """

    # Avoid spawning multiple workers if create_app is called more than once
    if app.config.get("AUTO_REPLY_WORKER_STARTED"):
        app.logger.debug("Auto-reply worker already running; skipping startup")
        return

    app.logger.info("Starting auto-reply worker thread")

    queue: SimpleQueue[InboundPayload] = app.config.setdefault("AUTO_REPLY_QUEUE", SimpleQueue())
    processed_sids: deque[str] = deque(maxlen=1000)  # simple dedupe within process lifetime

    def worker() -> None:
        while True:
            try:
                try:
                    payload = queue.get(timeout=1.0)
                except Empty:
                    continue

                with app.app_context():
                    twilio_client: TwilioService = app.config["TWILIO_CLIENT"]
                    auto_cfg = get_auto_reply_config()
                    ai_cfg = get_ai_config()

                    app.logger.info("Reactive reply worker received payload: %s", payload)

                    # ─────────────────────────────────────────────────────────
                    # LISTENERS: Check for command-based triggers first
                    # Listeners take priority over AI/auto-reply as they are
                    # explicit user commands (e.g., /news <query>)
                    # ─────────────────────────────────────────────────────────
                    body: str = payload.get("body", "") or ""
                    from_number: Optional[str] = (payload.get("from_number") or "").strip()
                    to_number: Optional[str] = (payload.get("to_number") or "").strip()
                    sid = payload.get("sid") or None
                    
                    # Check /news listener
                    if body.strip().lower().startswith("/news"):
                        news_listener = get_listener_by_command("/news")
                        if news_listener and news_listener.get("enabled"):
                            app.logger.info(
                                "Processing /news command from %s: %s",
                                from_number,
                                body[:100]
                            )
                            try:
                                from .faiss_service import FAISSService
                                faiss_service = FAISSService()
                                
                                # Extract query after /news prefix
                                query = body.strip()[5:].strip()
                                if not query:
                                    query = "Jakie są najnowsze wiadomości?"
                                
                                response = faiss_service.answer_query(query, top_k=5)
                                
                                if response.get("success") and response.get("answer"):
                                    reply_text = f"📰 News:\n\n{response['answer']}"
                                else:
                                    reply_text = "❌ Nie udało się znaleźć odpowiedzi w bazie newsów."
                                
                                origin_number = to_number or twilio_client.settings.default_from
                                if not origin_number:
                                    app.logger.error("/news: No origin number configured")
                                    continue
                                
                                message = twilio_client.send_chunked_sms(
                                    from_=origin_number,
                                    to=from_number,
                                    body=reply_text,
                                )
                                
                                if message.get("success"):
                                    if sid:
                                        processed_sids.append(sid)
                                    for msg_sid in message.get("sids", []):
                                        insert_message(
                                            direction="outbound",
                                            sid=msg_sid,
                                            to_number=from_number,
                                            from_number=origin_number,
                                            body=reply_text,
                                            status="news-reply",
                                        )
                                    app.logger.info(
                                        "/news reply sent to %s (query: %s)",
                                        from_number,
                                        query[:50]
                                    )
                                else:
                                    app.logger.error("/news send failed: %s", message.get("error"))
                                    insert_message(
                                        direction="outbound",
                                        sid=None,
                                        to_number=from_number,
                                        from_number=origin_number,
                                        body=reply_text,
                                        status="failed",
                                        error=message.get("error"),
                                    )
                            except Exception as exc:
                                app.logger.exception("/news handler error: %s", exc)
                                insert_message(
                                    direction="outbound",
                                    sid=None,
                                    to_number=from_number,
                                    from_number=to_number or twilio_client.settings.default_from,
                                    body="",
                                    status="failed",
                                    error=str(exc),
                                )
                            continue  # Skip normal AI/auto-reply processing
                        else:
                            app.logger.debug(
                                "/news command received but listener is disabled"
                            )

                    # ─────────────────────────────────────────────────────────
                    # Standard AI/Auto-reply processing
                    # ─────────────────────────────────────────────────────────
                    ai_enabled = bool(ai_cfg.get("enabled"))
                    auto_enabled = bool(auto_cfg.get("enabled"))

                    if not ai_enabled and not auto_enabled:
                        app.logger.info("Reactive replies disabled; skipping message")
                        continue

                    enabled_since_raw = auto_cfg.get("enabled_since") if auto_enabled else None
                    enabled_since = _parse_iso_timestamp(enabled_since_raw) if enabled_since_raw else None
                    received_at_raw = payload.get("received_at")
                    received_at = _parse_iso_timestamp(received_at_raw)
                    if enabled_since and received_at and received_at < enabled_since:
                        app.logger.info(
                            "Skipping auto-reply: message timestamp %s precedes enabled toggle %s",
                            received_at_raw,
                            enabled_since_raw,
                        )
                        continue

                    # AI: nie odpowiadamy na wiadomości sprzed włączenia / ostatniej zmiany konfiguracji AI
                    if ai_enabled:
                        ai_enabled_since_raw = ai_cfg.get("updated_at")
                        ai_enabled_since = _parse_iso_timestamp(ai_enabled_since_raw) if ai_enabled_since_raw else None
                        if ai_enabled_since and received_at and received_at < ai_enabled_since:
                            app.logger.info(
                                "Skipping AI auto-reply: message timestamp %s precedes AI config updated_at %s",
                                received_at_raw,
                                ai_enabled_since_raw,
                            )
                            continue

                    from_number: Optional[str] = (payload.get("from_number") or "").strip()
                    if not from_number or not ALLOWED_NUMBER_RE.match(from_number):
                        if auto_enabled and not ai_enabled:
                            app.logger.info("Skipping auto-reply: unsupported sender %s", from_number)
                            continue

                    sid = payload.get("sid") or None
                    if sid and sid in processed_sids:
                        app.logger.debug("Skipping duplicate sid=%s", sid)
                        continue

                    to_number: Optional[str] = (payload.get("to_number") or "").strip()
                    body: str = payload.get("body", "") or ""

                    if ai_enabled:
                        try:
                            api_key = (ai_cfg.get("api_key") or "").strip()
                            if not api_key:
                                app.logger.error("AI mode enabled but OpenAI API key is missing; skipping reply")
                                continue

                            responder = AIResponder(
                                api_key=api_key,
                                model=(ai_cfg.get("model") or "gpt-4o-mini").strip(),
                                system_prompt=ai_cfg.get("system_prompt") or "",
                                temperature=float(ai_cfg.get("temperature", 0.7) or 0.7),
                            )

                            result = send_ai_generated_sms(
                                responder=responder,
                                twilio_client=twilio_client,
                                participant_number=from_number,
                                latest_user_message=body,
                                origin_number=to_number,
                                logger=app.logger,
                            )

                            processed_sids.append(sid) if sid else None
                            insert_message(
                                direction="outbound",
                                sid=result.sid,
                                to_number=result.to_number,
                                from_number=result.origin_number or to_number or twilio_client.settings.default_from,
                                body=result.reply_text,
                                status=result.status or "ai-auto-reply",
                            )
                            app.logger.info(
                                "AI reply sent to %s with SID=%s", from_number, result.sid or "unknown"
                            )
                        except AIReplyError as exc:
                            app.logger.exception("AI auto-reply failed: %s", exc)
                            insert_message(
                                direction="outbound",
                                sid=None,
                                to_number=from_number,
                                from_number=to_number or twilio_client.settings.default_from,
                                body=exc.reply_text or "",
                                status="failed",
                                error=str(exc),
                            )
                        except Exception as exc:  # noqa: BLE001
                            app.logger.exception("Unexpected AI auto-reply error: %s", exc)
                            insert_message(
                                direction="outbound",
                                sid=None,
                                to_number=from_number,
                                from_number=to_number or twilio_client.settings.default_from,
                                body="",
                                status="failed",
                                error=str(exc),
                            )
                        continue

                    message_body = (auto_cfg.get("message") or "").strip()
                    if not message_body:
                        app.logger.warning("Auto-reply enabled but message template is empty; skipping")
                        continue

                    try:
                        origin_number = (twilio_client.settings.default_from or "").strip()
                        if not origin_number:
                            app.logger.error(
                                "Auto-reply enabled but TWILIO_DEFAULT_FROM is unset. Configure sender number to send replies."
                            )
                            continue

                        app.logger.info(
                            "Auto-reply: sending to %s from %s", from_number, origin_number
                        )
                        message = twilio_client.send_message(
                            to=from_number,
                            body=message_body,
                            extra_params={"from_": origin_number},
                        )
                        processed_sids.append(sid) if sid else None
                        insert_message(
                            direction="outbound",
                            sid=getattr(message, "sid", None),
                            to_number=from_number,
                            from_number=twilio_client.settings.default_from,
                            body=message_body,
                            status=getattr(message, "status", "auto-reply"),
                        )
                        app.logger.info(
                            "Auto-reply sent to %s with SID=%s", from_number, getattr(message, "sid", "unknown")
                        )
                    except Exception as exc:  # noqa: BLE001
                        app.logger.exception("Auto-reply send failed: %s", exc)
                        insert_message(
                            direction="outbound",
                            sid=None,
                            to_number=from_number,
                            from_number=twilio_client.settings.default_from,
                            body=message_body,
                            status="failed",
                            error=str(exc),
                        )
            except Exception as exc:  # noqa: BLE001
                app.logger.exception("Auto-reply worker error: %s", exc)

    thread = threading.Thread(target=worker, name="auto-reply-worker", daemon=True)
    thread.start()
    app.config["AUTO_REPLY_WORKER_STARTED"] = True


def enqueue_auto_reply(
    app: Flask,
    *,
    sid: Optional[str],
    from_number: Optional[str],
    to_number: Optional[str],
    body: str,
    received_at: Optional[str] = None,
) -> None:
    """Place inbound message data on the queue for async auto-reply.

    Called from webhook after persisting inbound message. Lightweight and non-blocking.
    """

    queue: SimpleQueue[InboundPayload] = app.config.setdefault("AUTO_REPLY_QUEUE", SimpleQueue())
    payload: InboundPayload = {
        "sid": sid,
        "from_number": from_number,
        "to_number": to_number,
        "body": body,
        "received_at": received_at or _utc_now_iso(),
    }
    app.logger.info("Enqueue auto-reply payload: %s", payload)
    queue.put(payload)
