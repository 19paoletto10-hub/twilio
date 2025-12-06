from flask import Flask
from .config import get_settings
from .twilio_client import TwilioService
from .webhooks import webhooks_bp
from .logger import configure_logging
from .database import init_app as init_database
from .ui import ui_bp


def create_app() -> Flask:
    app = Flask(__name__)

    configure_logging(app)

    app_settings, twilio_settings = get_settings()
    app.config["APP_SETTINGS"] = app_settings
    app.config["TWILIO_SETTINGS"] = twilio_settings

    # Inicjalizacja serwisu Twilio
    twilio_service = TwilioService(twilio_settings)
    app.config["TWILIO_SERVICE"] = twilio_service

    # Baza danych + blueprinty
    init_database(app)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(ui_bp)

    @app.get("/api/health")
    def api_health():
        return {
            "status": "ok",
            "message": "Twilio Chat App running",
            "env": app_settings.env,
        }

    return app
