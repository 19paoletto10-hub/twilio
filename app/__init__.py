"""
Twilio Chat Application - Main application factory.

This module provides the Flask application factory and initializes
all components including database, background workers, and routes.
"""

from __future__ import annotations

import os

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
from .multi_sms import start_multi_sms_worker
from .security import add_security_headers


def _should_start_workers(app_settings) -> bool:
    """Return True only for the main process to avoid double-start in reloader."""
    if not app_settings.debug:
        return True

    # Werkzeug reloader sets these flags for the "real" process.
    return os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("RUN_MAIN") == "true"


def create_app() -> Flask:
    """
    Create and configure Flask application instance.
    
    This factory function:
    1. Initializes Flask app
    2. Configures logging
    3. Loads settings from environment
    4. Sets up Twilio client
    5. Initializes database
    6. Registers blueprints (routes)
    7. Starts background workers
    8. Adds security headers
    
    Returns:
        Configured Flask application ready to run
        
    Raises:
        RuntimeError: If required environment variables are missing
    """
    app = Flask(__name__)

    # Configure logging first for early error visibility
    configure_logging(app)

    # Load configuration from environment
    app_settings, twilio_settings, openai_settings = get_settings()
    app.config["APP_SETTINGS"] = app_settings
    app.config["TWILIO_SETTINGS"] = twilio_settings
    app.config["OPENAI_SETTINGS"] = openai_settings

    # Initialize Twilio service
    twilio_client = TwilioService(twilio_settings)
    app.config["TWILIO_CLIENT"] = twilio_client

    # Initialize database and apply environment defaults
    init_database(app)
    apply_ai_env_defaults(app)
    
    # Register route blueprints
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(ui_bp)

    # Start background workers for automated tasks (only in the main process)
    if _should_start_workers(app_settings):
        start_auto_reply_worker(app)  # Auto-reply on inbound SMS
        start_reminder_worker(app)     # Scheduled reminders
        start_news_scheduler(app)      # News notifications
        start_multi_sms_worker(app)    # Batch SMS sending
    else:
        app.logger.info("Skipping background workers in reloader bootstrap process")

    # Add security headers to all responses
    @app.after_request
    def apply_security_headers(response):
        """Add security headers to every response."""
        return add_security_headers(response)

    @app.get("/api/health")
    def api_health():
        """
        Health check endpoint for monitoring and load balancers.
        
        Returns:
            JSON with application status and configuration summary
        """
        return {
            "status": "ok",
            "message": "Twilio Chat App running",
            "env": app_settings.env,
            "openai_enabled": openai_settings.enabled,
            "debug": app_settings.debug,
        }

    return app
