"""
Scheduled reminder service.

Background worker that sends recurring SMS reminders at configured intervals.
Handles scheduled messages from database and dispatches them via Twilio.
"""

from __future__ import annotations

import threading
import time
from typing import Dict, Any

from flask import Flask

from .database import (
    insert_message,
    list_due_scheduled_messages,
    mark_scheduled_sent,
)
from .twilio_client import TwilioService
from .validators import validate_e164_phone, ValidationError


def start_reminder_worker(app: Flask, *, interval_seconds: int = 5) -> None:
    """
    Start background worker sending scheduled reminder SMS.
    
    Runs in a daemon thread, checking database every `interval_seconds`
    for due reminders and sending them via Twilio.
    
    Features:
    - Validates phone numbers before sending
    - Updates next_run_at after successful send
    - Handles errors gracefully (logs and continues)
    - Singleton pattern (prevents duplicate workers)
    
    Args:
        app: Flask application instance
        interval_seconds: Check interval in seconds (default: 5)
        
    Example configuration in database:
        - to_number: '+48123456789'
        - body: 'Daily reminder: Take your medication'
        - interval_seconds: 86400  # 24 hours
        - enabled: 1
    """
    if app.config.get("REMINDER_WORKER_STARTED"):
        app.logger.debug("Reminder worker already running; skipping startup")
        return

    def worker() -> None:
        """Background loop checking for due reminders."""
        while True:
            time.sleep(interval_seconds)
            
            try:
                with app.app_context():
                    twilio_client: TwilioService = app.config["TWILIO_CLIENT"]
                    due_items = list_due_scheduled_messages(limit=50)

                    for item in due_items:
                        to_number = (item.get("to_number") or "").strip()
                        body = (item.get("body") or "").strip()
                        sched_id = int(item["id"])
                        interval = int(item.get("interval_seconds") or 60)
                        origin_number = (twilio_client.settings.default_from or "").strip()

                        # Validate phone number
                        try:
                            validate_e164_phone(to_number, "to_number")
                        except ValidationError:
                            app.logger.warning(
                                "Reminder: skip invalid number %s (id=%s)",
                                to_number,
                                sched_id,
                            )
                            mark_scheduled_sent(sched_id, interval)
                            continue

                        if not body:
                            app.logger.warning(
                                "Reminder: skip empty body for id=%s",
                                sched_id,
                            )
                            mark_scheduled_sent(sched_id, interval)
                            continue

                        if not origin_number:
                            app.logger.error(
                                "Reminder: cannot send (TWILIO_DEFAULT_FROM unset)"
                            )
                            mark_scheduled_sent(sched_id, interval)
                            continue

                        # Send reminder
                        try:
                            app.logger.info(
                                "Reminder: sending to %s (id=%s)",
                                to_number,
                                sched_id,
                            )
                            message = twilio_client.send_message(
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
                            
                        except Exception as exc:
                            app.logger.exception(
                                "Reminder: send failed for id=%s: %s",
                                sched_id,
                                exc,
                            )
                            insert_message(
                                direction="outbound",
                                sid=None,
                                to_number=to_number,
                                from_number=origin_number or None,
                                body=body,
                                status="failed",
                                error=str(exc),
                            )
                            # Mark as sent anyway to avoid spam on persistent errors
                            mark_scheduled_sent(sched_id, interval)
                            
            except Exception as exc:
                app.logger.exception("Reminder worker error: %s", exc)

    thread = threading.Thread(target=worker, name="reminder-worker", daemon=True)
    thread.start()
    app.config["REMINDER_WORKER_STARTED"] = True
    app.logger.info("⏰ Reminder worker started (check every %ds)", interval_seconds)
