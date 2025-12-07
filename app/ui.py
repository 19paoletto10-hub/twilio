from __future__ import annotations

from urllib.parse import unquote

from flask import Blueprint, current_app, render_template

ui_bp = Blueprint("ui", __name__)


@ui_bp.get("/")
def dashboard():
    app_settings = current_app.config["APP_SETTINGS"]
    twilio_settings = current_app.config["TWILIO_SETTINGS"]

    has_sender_identity = bool(
        (twilio_settings.default_from and twilio_settings.default_from.strip())
        or (twilio_settings.messaging_service_sid and twilio_settings.messaging_service_sid.strip())
    )

    return render_template(
        "dashboard.html",
        app_env=app_settings.env,
        app_debug=app_settings.debug,
        has_sender_identity=has_sender_identity,
    )


@ui_bp.get("/chat/<path:participant>")
def chat_view(participant: str):
    app_settings = current_app.config["APP_SETTINGS"]
    twilio_settings = current_app.config["TWILIO_SETTINGS"]

    normalized = unquote(participant).strip()
    display_number = normalized.replace("whatsapp:", "", 1)

    return render_template(
        "chat.html",
        participant=normalized,
        display_number=display_number,
        app_env=app_settings.env,
    )
