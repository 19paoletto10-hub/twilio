from __future__ import annotations

import re
import threading
from collections import deque
from datetime import datetime
from queue import SimpleQueue, Empty
from typing import Optional, Dict, Any

from flask import Flask

from .database import get_auto_reply_config, insert_message, get_ai_config, get_listener_by_command, has_outbound_reply_for_inbound
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


def start_auto_reply_worker(app: Flask, force_restart: bool = False) -> None:
    """
    Start a daemon background worker for asynchronous message processing.
    
    This worker implements the core async messaging pipeline:
    1. Listens on an in-memory SimpleQueue for inbound message payloads
    2. Performs database-level deduplication to prevent duplicate responses
    3. Processes listener commands (e.g., /news) with highest priority
    4. Handles AI-powered responses when AI mode is enabled
    5. Falls back to configured auto-reply templates
    
    The worker runs as a daemon thread and will be automatically terminated
    when the main Flask process exits. Queue failures are logged but don't
    crash the worker - it continues processing subsequent messages.
    
    Thread Safety:
        - Uses SimpleQueue which is thread-safe for put/get operations
        - Database operations use SQLite's built-in locking
        - Processed SIDs are tracked in a bounded deque (in-memory dedupe)
    
    Recovery:
        - If force_restart=True, kills existing worker and starts fresh
        - Dead workers are auto-restarted on next enqueue_auto_reply() call
    
    Args:
        app: Flask application instance (required for app context and config)
        force_restart: Force restart even if worker thread is alive
        
    Note:
        Worker death in debug mode (Werkzeug reloader) is expected due to
        process forking. The enqueue function handles automatic recovery.
    """

    # Check if worker is already running and alive
    existing_thread = app.config.get("AUTO_REPLY_THREAD")
    if existing_thread and existing_thread.is_alive() and not force_restart:
        app.logger.debug("Auto-reply worker already running and alive; skipping startup")
        return

    # Reset flag to allow restart
    app.config["AUTO_REPLY_WORKER_STARTED"] = False

    app.logger.info("Starting auto-reply worker thread (force_restart=%s)", force_restart)

    # CRITICAL: Always use the SAME queue instance from app.config
    queue: SimpleQueue[InboundPayload] = app.config.setdefault("AUTO_REPLY_QUEUE", SimpleQueue())
    processed_sids: deque[str] = deque(maxlen=1000)  # simple dedupe within process lifetime
    
    app.logger.info("Auto-reply worker will listen on queue id=%s (app config id=%s)", id(queue), id(app.config))

    def worker() -> None:
        app.logger.info("Auto-reply worker thread started, listening on queue id=%s", id(queue))
        while True:
            try:
                try:
                    payload = queue.get(timeout=1.0)
                except Empty:
                    continue

                app.logger.info("Auto-reply worker picked payload: %s", payload)

                with app.app_context():
                    twilio_client: TwilioService = app.config["TWILIO_CLIENT"]
                    auto_cfg = get_auto_reply_config()
                    ai_cfg = get_ai_config()

                    body: str = payload.get("body", "") or ""
                    from_number: Optional[str] = (payload.get("from_number") or "").strip()
                    to_number: Optional[str] = (payload.get("to_number") or "").strip()
                    sid = payload.get("sid") or None

                    # ─────────────────────────────────────────────────────────
                    # DEDUPLIKACJA: Sprawdź w bazie czy już wysłaliśmy odpowiedź
                    # ─────────────────────────────────────────────────────────
                    if sid and from_number:
                        if has_outbound_reply_for_inbound(sid, from_number):
                            app.logger.debug(
                                "Worker: Skipping SID=%s - already replied to %s", sid, from_number
                            )
                            continue

                    app.logger.info("Reactive reply worker processing: from=%s, body=%s", from_number, body[:50])

                    # ─────────────────────────────────────────────────────────
                    # LISTENERS: Check for command-based triggers first
                    # Listeners take priority over AI/auto-reply as they are
                    # explicit user commands (e.g., /news <query>)
                    # ─────────────────────────────────────────────────────────
                    
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
                                
                                # Validate recipient number before sending
                                if not from_number:
                                    app.logger.error("/news: No recipient number (from_number is empty)")
                                    continue
                                
                                message = twilio_client.send_chunked_sms(
                                    from_=origin_number,
                                    to=from_number,  # type: ignore[arg-type] - validated above
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

                    received_at_raw = payload.get("received_at")
                    received_at = _parse_iso_timestamp(received_at_raw)
                    
                    # Check auto-reply timestamp filter (only applies to auto-reply, not AI)
                    skip_auto_reply_due_to_timestamp = False
                    if auto_enabled:
                        enabled_since_raw = auto_cfg.get("enabled_since")
                        enabled_since = _parse_iso_timestamp(enabled_since_raw) if enabled_since_raw else None
                        if enabled_since and received_at and received_at < enabled_since:
                            app.logger.info(
                                "Skipping auto-reply (not AI): message timestamp %s precedes enabled toggle %s",
                                received_at_raw,
                                enabled_since_raw,
                            )
                            skip_auto_reply_due_to_timestamp = True

                    # NOTE: Removed timestamp filtering for AI replies.
                    # Previously we skipped messages received before ai_config.updated_at,
                    # but this caused ALL messages to be skipped when config was updated
                    # after the webhook received the message. AI should respond to any
                    # inbound message as long as AI is enabled NOW.

                    # Validate sender number for auto-reply (AI is more permissive)
                    if not from_number or not ALLOWED_NUMBER_RE.match(from_number):
                        if auto_enabled and not ai_enabled:
                            app.logger.info("Skipping auto-reply: unsupported sender %s", from_number)
                            continue

                    # Check in-memory deduplication
                    if sid and sid in processed_sids:
                        app.logger.debug("Skipping duplicate sid=%s", sid)
                        continue

                    if ai_enabled:
                        # Validate from_number before AI processing
                        if not from_number:
                            app.logger.warning("AI reply skipped: no valid sender number")
                            continue
                            
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
                                participant_number=from_number,  # Validated above
                                latest_user_message=body,
                                origin_number=to_number,
                                logger=app.logger,
                            )

                            if sid:
                                processed_sids.append(sid)
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

                    # Skip auto-reply if timestamp filter blocked it
                    if skip_auto_reply_due_to_timestamp:
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

                        # Validate recipient number before sending auto-reply
                        if not from_number:
                            app.logger.warning("Auto-reply: No recipient number available; skipping")
                            continue

                        app.logger.info(
                            "Auto-reply: sending to %s from %s", from_number, origin_number
                        )
                        message = twilio_client.send_message(
                            to=from_number,  # type: ignore[arg-type] - validated above
                            body=message_body,
                            extra_params={"from_": origin_number},
                        )
                        if sid:
                            processed_sids.append(sid)
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
    app.config["AUTO_REPLY_THREAD"] = thread
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
    """
    Enqueue an inbound message for asynchronous processing.
    
    This is the entry point for the async messaging pipeline. It places the
    message payload on a SimpleQueue that is consumed by the background worker.
    The function is designed to be fast and non-blocking - actual message
    processing happens in the worker thread.
    
    Auto-Recovery:
        Automatically restarts the worker if it has died (common in debug mode
        with Werkzeug reloader due to process forking).
    
    Deduplication:
        While this function doesn't perform deduplication itself, the worker
        checks `has_outbound_reply_for_inbound()` to prevent duplicate responses.
    
    Args:
        app: Flask application instance
        sid: Twilio message SID (used for deduplication)
        from_number: Sender's phone number (recipient of our reply)
        to_number: Twilio number that received the message (origin of reply)
        body: Message text content
        received_at: ISO timestamp of when message was received (defaults to now)
        
    Example:
        >>> enqueue_auto_reply(
        ...     app,
        ...     sid="SM1234567890",
        ...     from_number="+48123456789",
        ...     to_number="+12025551234",
        ...     body="Hello from user",
        ... )
    """
    # CRITICAL: Always use the SAME queue instance from app.config
    queue: SimpleQueue[InboundPayload] = app.config.setdefault("AUTO_REPLY_QUEUE", SimpleQueue())
    
    thread = app.config.get("AUTO_REPLY_THREAD")
    thread_alive = thread.is_alive() if thread else False
    
    app.logger.debug(
        "Worker status: thread=%s, alive=%s",
        thread, thread_alive
    )
    
    # Restart worker if it died
    if not thread_alive:
        app.logger.warning("Auto-reply worker not running or died; restarting now")
        start_auto_reply_worker(app, force_restart=True)

    payload: InboundPayload = {
        "sid": sid,
        "from_number": from_number,
        "to_number": to_number,
        "body": body,
        "received_at": received_at or _utc_now_iso(),
    }
    app.logger.info("Enqueue auto-reply payload: %s", payload)
    queue.put(payload)
    app.logger.debug("Queue size after enqueue: %s", queue.qsize())
