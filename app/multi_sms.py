from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Dict, List

from flask import Flask
from twilio.base.exceptions import TwilioRestException

from .database import (
    insert_message,
    list_multi_sms_recipients,
    recalc_multi_sms_counters,
    reserve_next_multi_sms_batch,
    update_multi_sms_batch_status,
    update_multi_sms_recipient,
)
from .reminder import E164_RE
from .twilio_client import TwilioService

_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S"


def _utc_now() -> str:
    return datetime.utcnow().strftime(_TIMESTAMP_FORMAT)


def start_multi_sms_worker(app: Flask, *, interval_seconds: int = 2) -> None:
    """Boot background worker responsible for processing Multi-SMS batches."""

    if app.config.get("MULTI_SMS_WORKER_STARTED"):
        app.logger.debug("Multi-SMS worker already running; skipping startup")
        return

    app.logger.info("Starting Multi-SMS worker thread")

    def worker() -> None:
        while True:
            time.sleep(interval_seconds)
            try:
                with app.app_context():
                    batch = reserve_next_multi_sms_batch()
                    if not batch:
                        continue
                    _process_batch(app, batch)
            except Exception as exc:  # noqa: BLE001
                app.logger.exception("Multi-SMS worker error: %s", exc)

    thread = threading.Thread(target=worker, name="multi-sms-worker", daemon=True)
    thread.start()
    app.config["MULTI_SMS_WORKER_STARTED"] = True


def _process_batch(app: Flask, batch: Dict[str, Any]) -> None:
    twilio_client: TwilioService = app.config["TWILIO_CLIENT"]
    batch_id = batch["id"]
    app.logger.info("Multi-SMS: processing batch %s", batch_id)
    send_delay_seconds = float(app.config.get("MULTI_SMS_SEND_DELAY_SECONDS", 0) or 0)

    try:
        recipients = list_multi_sms_recipients(batch_id, statuses=("pending",))
        if not recipients:
            stats = recalc_multi_sms_counters(batch_id)
            final_status = _resolve_final_status(stats)
            error_text = _build_error_message(stats)
            update_multi_sms_batch_status(batch_id, status=final_status, error=error_text, completed=True)
            return

        for recipient in recipients:
            number = recipient.get("number_normalized") or recipient.get("number_raw") or ""
            recipient_id = recipient["id"]

            if not number or not E164_RE.match(number):
                update_multi_sms_recipient(
                    recipient_id,
                    status="invalid",
                    sid=None,
                    error="Nieprawidłowy numer odbiorcy.",
                    sent_at=_utc_now(),
                )
                continue

            try:
                message = twilio_client.send_message(
                    to=number,
                    body=batch["body"],
                )
                insert_message(
                    direction="outbound",
                    sid=getattr(message, "sid", None),
                    to_number=number,
                    from_number=getattr(message, "from_", None) or twilio_client.settings.default_from,
                    body=batch["body"],
                    status=getattr(message, "status", "queued"),
                )
                update_multi_sms_recipient(
                    recipient_id,
                    status="sent",
                    sid=getattr(message, "sid", None),
                    error=None,
                    sent_at=_utc_now(),
                )
                app.logger.info("Multi-SMS: sent batch %s to %s", batch_id, number)
                if send_delay_seconds > 0:
                    time.sleep(send_delay_seconds)
            except TwilioRestException as exc:
                app.logger.exception(
                    "Multi-SMS: Twilio error sending batch %s to %s (status=%s, code=%s)",
                    batch_id,
                    number,
                    getattr(exc, "status", None),
                    getattr(exc, "code", None),
                )
                update_multi_sms_recipient(
                    recipient_id,
                    status="failed",
                    sid=None,
                    error=_format_twilio_error(exc),
                    sent_at=_utc_now(),
                )
            except Exception as exc:  # noqa: BLE001
                app.logger.exception("Multi-SMS: failed sending batch %s to %s", batch_id, number)
                update_multi_sms_recipient(
                    recipient_id,
                    status="failed",
                    sid=None,
                    error=str(exc),
                    sent_at=_utc_now(),
                )

        stats = recalc_multi_sms_counters(batch_id)
        final_status = _resolve_final_status(stats)
        error_text = _build_error_message(stats)
        update_multi_sms_batch_status(
            batch_id,
            status=final_status,
            error=error_text,
            completed=True,
        )
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Multi-SMS: batch %s failed with error", batch_id)
        update_multi_sms_batch_status(batch_id, status="failed", error=str(exc), completed=True)


def _format_twilio_error(exc: TwilioRestException) -> str:
    status = getattr(exc, "status", None)
    code = getattr(exc, "code", None)
    msg = str(exc)

    parts: List[str] = []
    if status:
        parts.append(f"HTTP {status}")
    if code:
        parts.append(f"code {code}")
    if msg:
        parts.append(msg)

    return " | ".join(parts) if parts else "Twilio error"


def _resolve_final_status(stats: Dict[str, int]) -> str:
    total = stats.get("total", 0)
    success = stats.get("success", 0)
    failed = stats.get("failed", 0)
    invalid = stats.get("invalid", 0)
    pending = max(total - success - failed - invalid, 0)

    if total == 0:
        return "completed"
    if success == total:
        return "completed"
    if failed == total:
        return "failed"
    if failed > 0:
        return "completed_with_errors"
    if pending > 0:
        return "processing"
    if invalid == total:
        return "completed_with_errors"
    return "completed"


def _build_error_message(stats: Dict[str, int]) -> str | None:
    failed = stats.get("failed", 0)
    invalid = stats.get("invalid", 0)
    fragments: List[str] = []

    if failed:
        fragments.append(f"Nie udało się wysłać do {failed} odbiorców.")
    if invalid:
        fragments.append(f"Pominięto {invalid} niepoprawnych numerów.")

    return " ".join(fragments) if fragments else None
