from flask import Flask
from .config import get_settings
from .twilio_client import TwilioService
from .webhooks import webhooks_bp
from .logger import configure_logging
from .database import init_app as init_database
from .ui import ui_bp
from .auto_reply import start_auto_reply_worker


def create_app() -> Flask:
    app = Flask(__name__)

    configure_logging(app)

    app_settings, twilio_settings = get_settings()
    app.config["APP_SETTINGS"] = app_settings
    app.config["TWILIO_SETTINGS"] = twilio_settings

    # Inicjalizacja serwisu Twilio (opcjonalna)
    if twilio_settings.account_sid and twilio_settings.auth_token:
        try:
            twilio_service = TwilioService(twilio_settings)
            app.config["TWILIO_SERVICE"] = twilio_service
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("Failed to initialize TwilioService: %s", exc)
            app.config["TWILIO_SERVICE"] = None
    else:
        app.logger.warning(
            "TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN not provided; Twilio features disabled"
        )
        app.config["TWILIO_SERVICE"] = None

    # Baza danych + blueprinty
    init_database(app)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(ui_bp)

    # Initialize rate limiter (use Redis when RATELIMIT_STORAGE_URL is provided)
    from .limiter import init_limiter
    init_limiter(app)

    # Background worker: auto-reply on inbound messages (SMS-only)
    # Start worker only if Twilio service is available
    if app.config.get("TWILIO_SERVICE"):
        start_auto_reply_worker(app)
    else:
        app.logger.info("Auto-reply worker not started (Twilio not configured)")

    @app.get("/api/health")
    def api_health():
        return {
            "status": "ok",
            "message": "Twilio Chat App running",
            "env": app_settings.env,
        }

    return app
