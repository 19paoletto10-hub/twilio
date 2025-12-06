from __future__ import annotations

from flask import Blueprint, current_app, request, Response, jsonify
from twilio.twiml.messaging_response import MessagingResponse

from .chat_logic import build_chat_engine
from .twilio_client import TwilioService

webhooks_bp = Blueprint("webhooks", __name__)


@webhooks_bp.post("/twilio/inbound")
def inbound_message():
    app = current_app
    app.logger.info("Received inbound hook: %s", request.form.to_dict())

    from_number = request.form.get("From", "")
    body = request.form.get("Body", "")

    chat_engine = build_chat_engine()
    reply_text = chat_engine.build_reply(from_number, body)

    resp = MessagingResponse()
    resp.message(reply_text)

    return Response(str(resp), mimetype="application/xml")


@webhooks_bp.post("/twilio/status")
def message_status():
    app = current_app
    data = request.form.to_dict()
    app.logger.info("Message status update: %s", data)
    return ("", 204)


@webhooks_bp.post("/api/send-message")
def api_send_message():
    """
    Prosty REST endpoint do wysyłania wiadomości z Twojej aplikacji.
    Przyjmuje JSON:
    {
      "to": "...",
      "body": "...",
      "use_messaging_service": true/false
    }
    """
    payload = request.get_json(force=True, silent=True) or {}
    to = payload.get("to")
    body = payload.get("body")
    use_ms = bool(payload.get("use_messaging_service", False))

    if not to or not body:
        return (
            jsonify({"error": "Fields 'to' and 'body' are required."}),
            400,
        )

    twilio_service: TwilioService = current_app.config["TWILIO_SERVICE"]
    try:
        message = twilio_service.send_message(
            to=to,
            body=body,
            use_messaging_service=use_ms,
        )
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Error while sending message")
        return jsonify({"error": str(exc)}), 500

    return jsonify({"sid": message.sid, "status": message.status})
