from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List
from urllib.parse import unquote

from flask import Blueprint, current_app, request, Response, jsonify
from twilio.twiml.messaging_response import MessagingResponse

from .chat_logic import build_chat_engine
from .twilio_client import TwilioService
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

    for message in remote_messages:
        _persist_twilio_message(message)

    cache["last_sync"] = now


@webhooks_bp.post("/twilio/inbound")
def inbound_message():
    app = current_app
    app.logger.info("Received inbound hook: %s", request.form.to_dict())

    from_number = request.form.get("From", "")
    to_number = request.form.get("To", "")
    body = request.form.get("Body", "")
    message_sid = request.form.get("MessageSid")
    message_status = request.form.get("SmsStatus")

    chat_engine = build_chat_engine()
    reply_text = chat_engine.build_reply(from_number, body)

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

    resp = MessagingResponse()
    resp.message(reply_text)

    if reply_text:
        insert_message(
            direction="outbound",
            sid=None,
            to_number=from_number,
            from_number=to_number,
            body=reply_text,
            status="generated",
        )

    return Response(str(resp), mimetype="application/xml")


@webhooks_bp.post("/twilio/status")
def message_status():
    app = current_app
    data = request.form.to_dict()
    app.logger.info("Message status update: %s", data)
    message_sid = data.get("MessageSid") or data.get("SmsSid")
    status = data.get("MessageStatus") or data.get("SmsStatus")

    error: str | None = None
    if data.get("ErrorMessage"):
        error = data["ErrorMessage"]
    elif data.get("ErrorCode"):
        error = f"Error code: {data['ErrorCode']}"

    if message_sid:
        updated = update_message_status_by_sid(sid=message_sid, status=status, error=error)
        if not updated:
            app.logger.warning("Received status for unknown message SID: %s", message_sid)

    return jsonify({"status": "ok"})


@webhooks_bp.post("/api/send-message")
def api_send_message():
    """REST endpoint do wysyłania SMS/MMS oraz WhatsApp."""

    payload = request.get_json(force=True, silent=True) or {}
    to = payload.get("to")
    body = payload.get("body")
    channel = (payload.get("channel") or "sms").lower()
    allowed_channels = {"sms", "whatsapp"}
    if channel not in allowed_channels:
        return jsonify({"error": "Unsupported channel."}), 400

    content_sid = payload.get("content_sid")
    content_variables = _encode_content_variables(payload.get("content_variables"))
    media_urls = _coerce_media_urls(payload.get("media_urls"))
    messaging_service_sid = payload.get("messaging_service_sid")

    raw_use_ms = payload.get("use_messaging_service")
    use_ms = bool(raw_use_ms) if raw_use_ms is not None else None

    if not to:
        return jsonify({"error": "Field 'to' is required."}), 400

    if not any([body, content_sid, media_urls]):
        return jsonify({"error": "Provide 'body', 'content_sid' or 'media_urls'."}), 400

    twilio_service: TwilioService = current_app.config["TWILIO_SERVICE"]

    try:
        if channel == "whatsapp":
            message = twilio_service.send_whatsapp_message(
                to=to,
                body=body,
                media_urls=media_urls,
                messaging_service_sid=messaging_service_sid,
                content_sid=content_sid,
                content_variables=content_variables,
            )
        else:
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
        if channel == "whatsapp":
            origin = twilio_service.settings.whatsapp_from or origin
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
    for message in remote_messages:
        _persist_twilio_message(message)
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
