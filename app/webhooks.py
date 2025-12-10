from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List
from urllib.parse import unquote

import os

from flask import Blueprint, current_app, request, Response, jsonify
from twilio.request_validator import RequestValidator

from .chat_logic import build_chat_engine
from .twilio_client import TwilioService
from .auto_reply import enqueue_auto_reply
from .database import get_auto_reply_config, set_auto_reply_config
from .database import (
    list_scheduled_messages,
    create_scheduled_message,
    update_scheduled_message,
    delete_scheduled_message,
)
from .database import (
    insert_message,
    list_messages,
    update_message_status_by_sid,
    get_message_stats,
    upsert_message,
    delete_message_by_sid,
    list_conversations,
)

webhooks_bp = Blueprint("webhooks", __name__)


def _datetime_to_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def _persist_twilio_message(message) -> None:
    direction = (
        "inbound"
        if (getattr(message, "direction", "") or "").startswith("inbound")
        else "outbound"
    )
    error_details = message.error_message or (
        f"Error code: {message.error_code}" if getattr(message, "error_code", None) else None
    )

    upsert_message(
        sid=message.sid,
        direction=direction,
        to_number=getattr(message, "to", None),
        from_number=getattr(message, "from_", None),
        body=getattr(message, "body", "") or "",
        status=getattr(message, "status", None),
        error=error_details,
        created_at=_datetime_to_iso(getattr(message, "date_created", None)),
        updated_at=_datetime_to_iso(getattr(message, "date_updated", None)),
    )


def _validate_twilio_signature(req) -> bool:
    # Allow disabling validation for local testing (e.g., ngrok) via env flag
    if os.getenv("TWILIO_VALIDATE_SIGNATURE", "true").lower() in {"0", "false", "no", "off"}:
        current_app.logger.warning("Skipping Twilio signature validation (TWILIO_VALIDATE_SIGNATURE disabled)")
        return True

    settings = current_app.config.get("TWILIO_SETTINGS")
    if not settings or not settings.auth_token:
        current_app.logger.error("Missing Twilio auth token; cannot validate signature")
        return False

    signature = req.headers.get("X-Twilio-Signature", "")
    validator = RequestValidator(settings.auth_token)

    # Flask preserves the raw URL including query string; Twilio expects exactly that
    url = req.url
    params = req.form.to_dict(flat=False) or req.form.to_dict() or {}

    is_valid = validator.validate(url, params, signature)
    if not is_valid:
        current_app.logger.warning(
            "Invalid Twilio signature for %s (sig=%s, url=%s, params=%s)",
            req.path,
            signature,
            url,
            params,
        )
    else:
        current_app.logger.debug("Twilio signature validated for %s", req.path)
    return is_valid


def _maybe_enqueue_auto_reply_for_message(message) -> None:
    """Queue auto-reply for a Twilio message when feature is enabled and inbound."""

    cfg = get_auto_reply_config()
    if not cfg.get("enabled"):
        return

    direction = getattr(message, "direction", "") or ""
    if not direction.startswith("inbound"):
        return

    from_number = (getattr(message, "from_", "") or "").strip()
    to_number = (getattr(message, "to", "") or "").strip()
    body = getattr(message, "body", "") or ""
    sid = getattr(message, "sid", None)

    enqueue_auto_reply(
        current_app,
        sid=sid,
        from_number=from_number,
        to_number=to_number,
        body=body,
    )


def _twilio_message_to_dict(message) -> Dict[str, Any]:
    return {
        "sid": message.sid,
        "status": getattr(message, "status", None),
        "direction": getattr(message, "direction", None),
        "from": getattr(message, "from_", None),
        "to": getattr(message, "to", None),
        "body": getattr(message, "body", None),
        "num_media": getattr(message, "num_media", None),
        "num_segments": getattr(message, "num_segments", None),
        "error_code": getattr(message, "error_code", None),
        "error_message": getattr(message, "error_message", None),
        "messaging_service_sid": getattr(message, "messaging_service_sid", None),
        "price": getattr(message, "price", None),
        "price_unit": getattr(message, "price_unit", None),
        "date_created": _datetime_to_iso(getattr(message, "date_created", None)),
        "date_updated": _datetime_to_iso(getattr(message, "date_updated", None)),
        "date_sent": _datetime_to_iso(getattr(message, "date_sent", None)),
    }


def _coerce_media_urls(value: Any) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else None
    if isinstance(value, list | tuple):
        cleaned_list = [str(item) for item in value if str(item).strip()]
        return cleaned_list or None
    return None


def _encode_content_variables(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value)
    except TypeError:
        return None


def _parse_datetime_arg(raw_value: Optional[str]) -> Optional[datetime]:
    if not raw_value:
        return None
    try:
        # datetime.fromisoformat supports timezone-aware inputs as well
        return datetime.fromisoformat(raw_value)
    except ValueError:
        return None


def _maybe_sync_messages(limit: int = 50) -> None:
    cache = current_app.config.setdefault("TWILIO_SYNC_CACHE", {"last_sync": 0.0})
    now = time.time()
    if now - cache.get("last_sync", 0.0) < 10:
        return

    twilio_service: TwilioService = current_app.config["TWILIO_SERVICE"]
    try:
        remote_messages = twilio_service.client.messages.list(limit=limit)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.warning("Unable to sync messages from Twilio: %s", exc)
        cache["last_sync"] = now
        return

    first_inbound_enqueued = False
    for message in remote_messages:
        _persist_twilio_message(message)
        if not first_inbound_enqueued and (getattr(message, "direction", "") or "").startswith("inbound"):
            _maybe_enqueue_auto_reply_for_message(message)
            first_inbound_enqueued = True

    cache["last_sync"] = now


@webhooks_bp.post("/twilio/inbound")
def inbound_message():
    app = current_app
    app.logger.info("Inbound webhook hit: %s", request.path)

    if not _validate_twilio_signature(request):
        return Response("Forbidden", status=403)

    app.logger.info("Received inbound hook: %s", request.form.to_dict())

    # Extract and validate webhook parameters
    from_number = (request.form.get("From") or "").strip()
    to_number = (request.form.get("To") or "").strip()
    body = (request.form.get("Body") or "").strip()
    message_sid = (request.form.get("MessageSid") or "").strip() or None
    message_status = (request.form.get("SmsStatus") or "").strip() or None

    # Validate required parameters
    if not from_number or not to_number:
        app.logger.warning("Missing required webhook parameters: From=%s, To=%s", from_number, to_number)
        return Response("<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response></Response>", mimetype="application/xml")

    # Store the incoming message
    try:
        if message_sid:
            upsert_message(
                sid=message_sid,
                direction="inbound",
                to_number=to_number,
                from_number=from_number,
                body=body,
                status=message_status,
                error=None,
                created_at=None,
                updated_at=None,
            )
        else:
            insert_message(
                direction="inbound",
                sid=None,
                to_number=to_number,
                from_number=from_number,
                body=body,
                status=message_status,
            )
        app.logger.info(
            "Stored inbound message from %s to %s (SID: %s)", 
            from_number, to_number, message_sid or "N/A"
        )
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Failed to store inbound message: %s", exc)

    twilio_service: TwilioService = app.config["TWILIO_SERVICE"]

    # Generate auto-reply using chat engine
    cfg = get_auto_reply_config()

    # If DB-driven auto-reply is enabled, enqueue for background worker
    if cfg.get("enabled"):
        enqueue_auto_reply(
            app,
            sid=message_sid,
            from_number=from_number,
            to_number=to_number,
            body=body,
        )
        return Response("OK", mimetype="text/plain")

    # Otherwise, fall back to chat-engine based reply (synchronous send)
    reply_text = None
    try:
        chat_engine = build_chat_engine()
        reply_text = chat_engine.build_reply(from_number, body)
        if reply_text:
            app.logger.info(
                "Generated auto-reply to %s: %s",
                from_number,
                reply_text[:50] + ("..." if len(reply_text) > 50 else ""),
            )
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Failed to generate auto-reply: %s", exc)
        reply_text = None

    if reply_text:
        try:
            message = twilio_service.send_reply_to_inbound(
                inbound_from=from_number,
                inbound_to=to_number,
                body=reply_text,
            )
            _persist_twilio_message(message)
            app.logger.info("Sent auto-reply via API to %s (SID: %s)", from_number, message.sid)
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("Failed to send auto-reply via API: %s", exc)
            insert_message(
                direction="outbound",
                sid=None,
                to_number=from_number,
                from_number=to_number,
                body=reply_text,
                status="failed",
                error=str(exc),
            )

    return Response("OK", mimetype="text/plain")


@webhooks_bp.get("/api/auto-reply/config")
def api_get_auto_reply_config():
    """Expose current auto-reply configuration."""

    cfg = get_auto_reply_config()
    return jsonify({"enabled": bool(cfg.get("enabled")), "message": cfg.get("message", "")})


@webhooks_bp.post("/api/auto-reply/config")
def api_update_auto_reply_config():
    """Update auto-reply toggle and message template."""

    payload = request.get_json(force=True, silent=True) or {}
    enabled = bool(payload.get("enabled", False))
    message = (payload.get("message") or "").strip()

    if enabled and not message:
        return jsonify({"error": "Treść auto-odpowiedzi jest wymagana gdy funkcja jest włączona."}), 400

    if len(message) > 640:
        return jsonify({"error": "Treść auto-odpowiedzi nie może przekraczać 640 znaków."}), 400

    set_auto_reply_config(enabled=enabled, message=message)
    cfg = get_auto_reply_config()
    return jsonify({"enabled": bool(cfg.get("enabled")), "message": cfg.get("message", "")})


@webhooks_bp.get("/api/reminders")
def api_list_reminders():
    items = list_scheduled_messages()
    return jsonify({"items": items, "count": len(items)})


@webhooks_bp.post("/api/reminders")
def api_create_reminder():
    payload = request.get_json(force=True, silent=True) or {}
    to_number = (payload.get("to") or "").strip()
    body = (payload.get("body") or "").strip()
    interval_minutes_raw = payload.get("interval_minutes")

    try:
        interval_minutes = int(interval_minutes_raw)
    except (TypeError, ValueError):
        interval_minutes = 0

    if not to_number:
        return jsonify({"error": "Pole 'to' jest wymagane."}), 400
    if not body:
        return jsonify({"error": "Pole 'body' jest wymagane."}), 400
    if interval_minutes < 1:
        return jsonify({"error": "Interwał musi być co najmniej 1 minuta."}), 400

    interval_seconds = interval_minutes * 60

    sched_id = create_scheduled_message(
        to_number=to_number,
        body=body,
        interval_seconds=interval_seconds,
        enabled=True,
    )
    items = list_scheduled_messages()
    return jsonify({"id": sched_id, "items": items, "count": len(items)}), 201


@webhooks_bp.post("/api/reminders/<int:sched_id>/toggle")
def api_toggle_reminder(sched_id: int):
    payload = request.get_json(force=True, silent=True) or {}
    enabled = bool(payload.get("enabled", False))
    updated = update_scheduled_message(sched_id=sched_id, enabled=enabled)
    if not updated:
        return jsonify({"error": "Nie znaleziono rekordu."}), 404
    items = list_scheduled_messages()
    return jsonify({"items": items, "count": len(items)})


@webhooks_bp.delete("/api/reminders/<int:sched_id>")
def api_delete_reminder(sched_id: int):
    deleted = delete_scheduled_message(sched_id)
    if not deleted:
        return jsonify({"error": "Nie znaleziono rekordu."}), 404
    items = list_scheduled_messages()
    return jsonify({"items": items, "count": len(items)})


@webhooks_bp.post("/twilio/status")
def message_status():
    app = current_app
    if not _validate_twilio_signature(request):
        return jsonify({"status": "forbidden", "message": "Invalid signature"}), 403

    data = request.form.to_dict()
    app.logger.info("Message status update: %s", data)
    
    message_sid = (data.get("MessageSid") or data.get("SmsSid") or "").strip() or None
    status = (data.get("MessageStatus") or data.get("SmsStatus") or "").strip() or None

    # Build error message if present
    error: str | None = None
    if data.get("ErrorMessage"):
        error = str(data["ErrorMessage"]).strip()
    elif data.get("ErrorCode"):
        error = f"Error code: {data['ErrorCode']}"

    if not message_sid:
        app.logger.warning("Received status update without MessageSid: %s", data)
        return jsonify({"status": "error", "message": "Missing MessageSid"}), 400

    if not status:
        app.logger.warning("Received status update without status for SID %s", message_sid)
        return jsonify({"status": "error", "message": "Missing status"}), 400

    try:
        updated = update_message_status_by_sid(sid=message_sid, status=status, error=error)
        if updated:
            app.logger.info("Updated status for message %s to %s", message_sid, status)
        else:
            app.logger.warning("Received status for unknown message SID: %s", message_sid)
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Failed to update message status for SID %s: %s", message_sid, exc)
        return jsonify({"status": "error", "message": str(exc)}), 500

    return jsonify({"status": "ok"})


@webhooks_bp.post("/api/send-message")
def api_send_message():
    """REST endpoint for sending SMS/MMS messages via Twilio API."""

    payload = request.get_json(force=True, silent=True) or {}
    
    # Validate and sanitize input parameters (SMS only)
    to = (payload.get("to") or "").strip()
    body = payload.get("body")  # Can be None for MMS-only

    content_sid = payload.get("content_sid")
    content_variables = _encode_content_variables(payload.get("content_variables"))
    media_urls = _coerce_media_urls(payload.get("media_urls"))
    messaging_service_sid = payload.get("messaging_service_sid")

    raw_use_ms = payload.get("use_messaging_service")
    use_ms = bool(raw_use_ms) if raw_use_ms is not None else None

    if not to:
        return jsonify({"error": "Field 'to' is required."}), 400

    if not any([body, content_sid, media_urls]):
        return jsonify({"error": "Provide at least one of: 'body', 'content_sid', or 'media_urls'."}), 400

    twilio_service: TwilioService = current_app.config["TWILIO_SERVICE"]

    try:
        extra_params: Dict[str, Any] = {}
        if media_urls:
            extra_params["media_url"] = media_urls
        if content_sid:
            extra_params["content_sid"] = content_sid
        if content_variables:
            extra_params["content_variables"] = content_variables

        message = twilio_service.send_message(
            to=to,
            body=body or "",
            use_messaging_service=use_ms,
            messaging_service_sid=messaging_service_sid,
            extra_params=extra_params,
        )
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Error while sending message")
        origin = twilio_service.settings.default_from
        insert_message(
            direction="outbound",
            sid=None,
            to_number=to,
            from_number=origin,
            body=body or "",
            status="failed",
            error=str(exc),
        )
        return jsonify({"error": str(exc)}), 500

    _persist_twilio_message(message)

    return jsonify({"sid": message.sid, "status": message.status})


@webhooks_bp.get("/api/messages")
def api_messages():
    limit_raw = request.args.get("limit", "50")
    try:
        limit = max(1, min(int(limit_raw), 500))
    except ValueError:
        limit = 50

    direction = request.args.get("direction")
    _maybe_sync_messages(limit=limit)
    messages = list_messages(limit=limit, direction=direction)
    return jsonify({"items": messages, "count": len(messages)})


@webhooks_bp.get("/api/conversations")
def api_conversations():
    limit_raw = request.args.get("limit", "30")
    try:
        limit = max(1, min(int(limit_raw), 200))
    except ValueError:
        limit = 30

    conversations = list_conversations(limit=limit)
    return jsonify({"items": conversations, "count": len(conversations)})


@webhooks_bp.get("/api/conversations/<path:participant>")
def api_conversation_detail(participant: str):
    limit_raw = request.args.get("limit", "200")
    try:
        limit = max(1, min(int(limit_raw), 500))
    except ValueError:
        limit = 200

    normalized_participant = unquote(participant).strip()
    if not normalized_participant:
        return jsonify({"error": "Participant is required."}), 400

    _maybe_sync_messages(limit=limit)
    messages = list_messages(limit=limit, participant=normalized_participant, ascending=True)
    return jsonify(
        {
            "participant": normalized_participant,
            "items": messages,
            "count": len(messages),
        }
    )


@webhooks_bp.get("/api/messages/stats")
def api_messages_stats():
    _maybe_sync_messages(limit=50)
    stats = get_message_stats()
    return jsonify(stats)


@webhooks_bp.get("/api/messages/remote")
def api_remote_messages():
    limit_raw = request.args.get("limit", "20")
    try:
        limit = max(1, min(int(limit_raw), 100))
    except ValueError:
        limit = 20

    filters: Dict[str, Any] = {"limit": limit}
    to_filter = request.args.get("to")
    if to_filter:
        filters["to"] = to_filter
    from_filter = request.args.get("from")
    if from_filter:
        filters["from_"] = from_filter

    date_sent = _parse_datetime_arg(request.args.get("date_sent"))
    if date_sent:
        filters["date_sent"] = date_sent
    date_sent_before = _parse_datetime_arg(request.args.get("date_sent_before"))
    if date_sent_before:
        filters["date_sent_before"] = date_sent_before
    date_sent_after = _parse_datetime_arg(request.args.get("date_sent_after"))
    if date_sent_after:
        filters["date_sent_after"] = date_sent_after

    twilio_service: TwilioService = current_app.config["TWILIO_SERVICE"]
    try:
        remote_messages = twilio_service.list_messages(**filters)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Unable to list messages")
        return jsonify({"error": str(exc)}), 500

    items = []
    first_inbound_enqueued = False
    for message in remote_messages:
        _persist_twilio_message(message)

        # Enqueue auto-reply for the newest inbound message only (remote list is newest-first)
        if not first_inbound_enqueued and (getattr(message, "direction", "") or "").startswith("inbound"):
            _maybe_enqueue_auto_reply_for_message(message)
            first_inbound_enqueued = True

        items.append(_twilio_message_to_dict(message))

    return jsonify({"items": items, "count": len(items)})


@webhooks_bp.get("/api/messages/<sid>")
def api_message_detail(sid: str):
    twilio_service: TwilioService = current_app.config["TWILIO_SERVICE"]
    try:
        message = twilio_service.fetch_message(sid)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Unable to fetch message %s", sid)
        return jsonify({"error": str(exc)}), 404

    _persist_twilio_message(message)
    return jsonify({"item": _twilio_message_to_dict(message)})


@webhooks_bp.post("/api/messages/<sid>/redact")
def api_redact_message(sid: str):
    twilio_service: TwilioService = current_app.config["TWILIO_SERVICE"]
    try:
        message = twilio_service.redact_message(sid)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Unable to redact message %s", sid)
        return jsonify({"error": str(exc)}), 400

    _persist_twilio_message(message)
    return jsonify({"sid": message.sid, "body": message.body, "status": message.status})


@webhooks_bp.delete("/api/messages/<sid>")
def api_delete_message(sid: str):
    twilio_service: TwilioService = current_app.config["TWILIO_SERVICE"]
    try:
        twilio_service.delete_message(sid)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Unable to delete message %s", sid)
        return jsonify({"error": str(exc)}), 400

    delete_message_by_sid(sid)
    return jsonify({"sid": sid, "deleted": True})
