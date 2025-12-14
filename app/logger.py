"""
Logging configuration for the Twilio Chat Application.

Provides structured logging with request context, IP resolution,
and proper formatting for both development and production environments.
"""

import logging
from typing import Optional
from flask import Flask, request, has_request_context


def configure_logging(app: Flask) -> None:
    """
    Configure application-wide logging with structured format.
    
    Sets up:
    - Consistent log formatting across all loggers
    - Request logging middleware
    - Client IP resolution (proxy-aware)
    - Different log levels for dev vs production
    
    Args:
        app: Flask application instance
    """
    # Create formatter with timestamp, level, and logger name
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Configure stream handler for console output
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    
    # Set log level based on environment
    app_settings = app.config.get("APP_SETTINGS")
    if app_settings and app_settings.debug:
        root_logger.setLevel(logging.DEBUG)
    else:
        root_logger.setLevel(logging.INFO)
    
    # Add handler if not already present (avoid duplicates)
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        root_logger.addHandler(handler)
    
    # Suppress verbose third-party loggers in production
    if app_settings and not app_settings.debug:
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("twilio").setLevel(logging.WARNING)

    def _client_ip() -> str:
        """
        Resolve caller IP respecting common proxy headers.
        
        Checks in order:
        1. X-Forwarded-For (first IP in chain)
        2. X-Real-IP
        3. Direct request.remote_addr
        
        Returns:
            Client IP address or 'unknown'
        """
        if not has_request_context():
            return "unknown"

        # Check X-Forwarded-For header (proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if forwarded_for:
            return forwarded_for

        # Check X-Real-IP header (nginx)
        real_ip = request.headers.get("X-Real-IP", "").strip()
        if real_ip:
            return real_ip

        # Fall back to direct connection
        return request.remote_addr or "unknown"

    @app.before_request
    def log_request() -> None:
        """Log incoming HTTP requests with method, path, and client IP."""
        app.logger.info(
            "Incoming %s %s from %s",
            request.method,
            request.path,
            _client_ip(),
        )
