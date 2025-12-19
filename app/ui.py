from __future__ import annotations

from urllib.parse import unquote

from flask import Blueprint, current_app, render_template, jsonify

from .webhooks import ALL_CATEGORIES_PROMPT, DEFAULT_NEWS_PROMPT

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
        news_default_prompt=DEFAULT_NEWS_PROMPT,
        news_all_categories_prompt=ALL_CATEGORIES_PROMPT,
    )


@ui_bp.get("/secrets")
def secrets_view():
    app_settings = current_app.config["APP_SETTINGS"]

    return render_template(
        "secrets.html",
        app_env=app_settings.env,
        app_debug=app_settings.debug,
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


@ui_bp.get("/api/openai/status")
def openai_status():
    """
    Endpoint do sprawdzenia statusu konfiguracji OpenAI.
    Używany przez frontend do wyświetlenia informacji o dostępności RAG/embeddings.
    """
    openai_settings = current_app.config.get("OPENAI_SETTINGS")
    if not openai_settings:
        return jsonify({
            "enabled": False,
            "error": "OpenAI settings not loaded"
        }), 503

    return jsonify({
        "enabled": openai_settings.enabled,
        "chat_model": openai_settings.chat_model,
        "embedding_model": openai_settings.embedding_model,
        "api_key_masked": openai_settings.get_masked_key(),
    })
