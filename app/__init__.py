from flask import Flask
from .config import get_settings
from .twilio_client import TwilioService
from .webhooks import webhooks_bp
from .logger import configure_logging
from .database import init_app as init_database, apply_ai_env_defaults
from .ui import ui_bp
from .auto_reply import start_auto_reply_worker
from .reminder import start_reminder_worker
from .news_scheduler import start_news_scheduler


def create_app() -> Flask:
    app = Flask(__name__)

    configure_logging(app)

    app_settings, twilio_settings, openai_settings = get_settings()
    app.config["APP_SETTINGS"] = app_settings
    app.config["TWILIO_SETTINGS"] = twilio_settings
    app.config["OPENAI_SETTINGS"] = openai_settings

    # Inicjalizacja serwisu Twilio
    twilio_client = TwilioService(twilio_settings)
    app.config["TWILIO_CLIENT"] = twilio_client

    # Baza danych + blueprinty
    init_database(app)
    apply_ai_env_defaults(app)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(ui_bp)

    # Background worker: auto-reply on inbound messages (SMS-only)
    start_auto_reply_worker(app)
    # Background worker: scheduled reminders
    start_reminder_worker(app)
    # Background scheduler: News notifications
    start_news_scheduler(app)

    @app.get("/api/health")
    def api_health():
        return {
            "status": "ok",
            "message": "Twilio Chat App running",
            "env": app_settings.env,
            "openai_enabled": openai_settings.enabled,
        }

    return app
