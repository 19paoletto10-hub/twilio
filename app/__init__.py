from flask import Flask
from .config import get_settings
from .twilio_client import TwilioService
from .webhooks import webhooks_bp
from .logger import configure_logging


def create_app() -> Flask:
    app = Flask(__name__)

    configure_logging(app)

    app_settings, twilio_settings = get_settings()
    app.config["APP_SETTINGS"] = app_settings
    app.config["TWILIO_SETTINGS"] = twilio_settings

    # Inicjalizacja serwisu Twilio
    twilio_service = TwilioService(twilio_settings)
    app.config["TWILIO_SERVICE"] = twilio_service

    # Blueprint z webhookami
    app.register_blueprint(webhooks_bp)

    @app.get("/")
    def index():
        return {
            "status": "ok",
            "message": "Twilio Chat App running",
            "env": app_settings.env,
        }

    return app
