from __future__ import annotations

import threading
from collections import deque
from queue import SimpleQueue, Empty
import re
from typing import Optional, Dict, Any

from flask import Flask

from .database import get_auto_reply_config, insert_message
from .twilio_client import TwilioService

# Type alias for queued inbound payloads
InboundPayload = Dict[str, Any]
# Accept standard E.164 numbers (+country up to 15 digits). Reject empties/short.
ALLOWED_NUMBER_RE = re.compile(r"^\+[1-9]\d{6,14}$")


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
                    twilio_service: TwilioService = app.config["TWILIO_SERVICE"]
                    cfg = get_auto_reply_config()

                    app.logger.info("Auto-reply worker received payload: %s", payload)

                    if not cfg.get("enabled"):
                        app.logger.info("Auto-reply disabled; skipping message")
                        continue

                    message_body = (cfg.get("message") or "").strip()
                    if not message_body:
                        app.logger.warning("Auto-reply enabled but message template is empty; skipping")
                        continue

                    from_number: Optional[str] = (payload.get("from_number") or "").strip()
                    if not from_number or not ALLOWED_NUMBER_RE.match(from_number):
                        app.logger.info("Skipping auto-reply: unsupported sender %s", from_number)
                        continue

                    sid = payload.get("sid") or None
                    if sid and sid in processed_sids:
                        app.logger.debug("Skipping duplicate sid=%s", sid)
                        continue

                    try:
                        origin_number = (twilio_service.settings.default_from or "").strip()
                        if not origin_number:
                            app.logger.error(
                                "Auto-reply enabled but TWILIO_DEFAULT_FROM is unset. Configure sender number to send replies."
                            )
                            continue

                        app.logger.info(
                            "Auto-reply: sending to %s from %s", from_number, origin_number
                        )
                        message = twilio_service.send_message(
                            to=from_number,
                            body=message_body,
                            extra_params={"from_": origin_number},
                        )
                        processed_sids.append(sid) if sid else None
                        insert_message(
                            direction="outbound",
                            sid=getattr(message, "sid", None),
                            to_number=from_number,
                            from_number=twilio_service.settings.default_from,
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
                            from_number=twilio_service.settings.default_from,
                            body=message_body,
                            status="failed",
                            error=str(exc),
                        )
            except Exception as exc:  # noqa: BLE001
                app.logger.exception("Auto-reply worker error: %s", exc)

    thread = threading.Thread(target=worker, name="auto-reply-worker", daemon=True)
    thread.start()
    app.config["AUTO_REPLY_WORKER_STARTED"] = True


def enqueue_auto_reply(app: Flask, *, sid: Optional[str], from_number: Optional[str], to_number: Optional[str], body: str) -> None:
    """Place inbound message data on the queue for async auto-reply.

    Called from webhook after persisting inbound message. Lightweight and non-blocking.
    """

    queue: SimpleQueue[InboundPayload] = app.config.setdefault("AUTO_REPLY_QUEUE", SimpleQueue())
    payload: InboundPayload = {
        "sid": sid,
        "from_number": from_number,
        "to_number": to_number,
        "body": body,
    }
    app.logger.info("Enqueue auto-reply payload: %s", payload)
    queue.put(payload)
