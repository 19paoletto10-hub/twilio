from __future__ import annotations

import threading
import time
from typing import Dict, Any
import re

from flask import Flask

from .database import (
    insert_message,
    list_due_scheduled_messages,
    mark_scheduled_sent,
)
from .twilio_client import TwilioService

E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


def start_reminder_worker(app: Flask, *, interval_seconds: int = 5) -> None:
    """Start background worker sending scheduled reminder SMS.

    - Checks for due scheduled_messages every `interval_seconds`.
    - Sends SMS using Twilio default_from; skips invalid numbers.
    - Updates last_sent_at/next_run_at after successful send attempt.
    """

    if app.config.get("REMINDER_WORKER_STARTED"):
        app.logger.debug("Reminder worker already running; skipping startup")
        return

    def worker() -> None:
        while True:
            time.sleep(interval_seconds)
            try:
                with app.app_context():
                    twilio_service: TwilioService = app.config["TWILIO_SERVICE"]
                    due_items = list_due_scheduled_messages(limit=50)

                    for item in due_items:
                        to_number = (item.get("to_number") or "").strip()
                        body = (item.get("body") or "").strip()
                        sched_id = int(item["id"])
                        interval = int(item.get("interval_seconds") or 60)
                        origin_number = (twilio_service.settings.default_from or "").strip()

                        if not to_number or not E164_RE.match(to_number):
                            app.logger.info("Reminder skip invalid number: %s", to_number)
                            mark_scheduled_sent(sched_id, interval)
                            continue
                        if not body:
                            app.logger.info("Reminder skip empty body for id=%s", sched_id)
                            mark_scheduled_sent(sched_id, interval)
                            continue
                        if not origin_number:
                            app.logger.error(
                                "Reminder worker cannot send: TWILIO_DEFAULT_FROM is unset"
                            )
                            mark_scheduled_sent(sched_id, interval)
                            continue

                        try:
                            app.logger.info("Reminder: sending to %s (id=%s)", to_number, sched_id)
                            message = twilio_service.send_message(
                                to=to_number,
                                body=body,
                                extra_params={"from_": origin_number},
                            )
                            insert_message(
                                direction="outbound",
                                sid=getattr(message, "sid", None),
                                to_number=to_number,
                                from_number=origin_number,
                                body=body,
                                status=getattr(message, "status", "queued"),
                            )
                            mark_scheduled_sent(sched_id, interval)
                        except Exception as exc:  # noqa: BLE001
                            app.logger.exception("Reminder send failed for id=%s: %s", sched_id, exc)
                            insert_message(
                                direction="outbound",
                                sid=None,
                                to_number=to_number,
                                from_number=origin_number or None,
                                body=body,
                                status="failed",
                                error=str(exc),
                            )
            except Exception as exc:  # noqa: BLE001
                app.logger.exception("Reminder worker error: %s", exc)

    thread = threading.Thread(target=worker, name="reminder-worker", daemon=True)
    thread.start()
    app.config["REMINDER_WORKER_STARTED"] = True
