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
        # Basic app info
        payload = {
            "status": "ok",
            "message": "Twilio Chat App running",
            "env": app_settings.env,
        }

        # Database health
        try:
            from .database import health_check

            db_health = health_check()
            payload["database"] = db_health
            if not db_health.get("ok"):
                payload["status"] = "degraded"
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("Error checking DB health: %s", exc)
            payload["database"] = {"ok": False, "details": str(exc)}
            payload["status"] = "degraded"

        # Redis health (optional)
        redis_url = app.config.get("RATELIMIT_STORAGE_URL") or None
        if redis_url and (redis_url.startswith("redis://") or redis_url.startswith("rediss://")):
            try:
                import redis as _redis  # type: ignore

                r = _redis.from_url(redis_url, socket_connect_timeout=2)
                pong = r.ping()
                payload["redis"] = {"ok": bool(pong), "url": redis_url}
                if not pong:
                    payload["status"] = "degraded"
            except Exception as exc:  # noqa: BLE001
                app.logger.exception("Redis health check failed: %s", exc)
                payload["redis"] = {"ok": False, "details": str(exc)}
                payload["status"] = "degraded"

        return payload

    return app
