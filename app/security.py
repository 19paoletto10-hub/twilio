"""
Security utilities for the Twilio Chat Application.

Provides request validation, security headers, and webhook signature verification.
"""

from __future__ import annotations

import hmac
import os
from typing import Callable, Optional

from flask import Request, abort, current_app, request
from twilio.request_validator import RequestValidator


class TwilioWebhookValidator:
    """
    Validates incoming Twilio webhook requests using signature verification.

    This prevents unauthorized parties from spoofing Twilio webhooks and
    ensures that requests genuinely originate from Twilio's servers.
    """

    def __init__(self, auth_token: str) -> None:
        """
        Initialize webhook validator.

        Args:
            auth_token: Twilio account auth token for signature validation

        Raises:
            ValueError: If the auth token is missing
        """
        if not auth_token:
            raise ValueError("Twilio auth_token is required for webhook validation.")

        self.validator = RequestValidator(auth_token)

    def validate_request(
        self,
        req: Request,
        *,
        url_override: Optional[str] = None,
    ) -> bool:
        """
        Validate Twilio webhook signature.

        Args:
            req: Flask request object
            url_override: Optional URL override (useful for proxied requests)

        Returns:
            True if signature is valid, False otherwise
        """
        signature = req.headers.get("X-Twilio-Signature", "")
        url = url_override or req.url
        params = req.form.to_dict(flat=True)

        return bool(self.validator.validate(url, params, signature))


def add_security_headers(response):
    """
    Add security headers to Flask response.

    Implements defense-in-depth security practices:
    - Content Security Policy (CSP)
    - XSS Protection
    - Frame Options (clickjacking prevention)
    - Content Type Options (MIME sniffing prevention)
    - Referrer Policy

    Args:
        response: Flask response object

    Returns:
        Modified response with security headers
    """
    # Content Security Policy - restrict resource loading
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https:; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )

    # Prevent browsers from MIME-sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Enable XSS filter (legacy browsers)
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"

    # Control referrer information
    response.headers["Referrer-Policy"] = "no-referrer"

    # HSTS only when request is served over HTTPS
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response


def require_webhook_signature(f: Callable) -> Callable:
    """
    Decorator to require valid Twilio webhook signature.

    Usage:
        @app.route('/twilio/webhook', methods=['POST'])
        @require_webhook_signature
        def handle_webhook():
            ...

    Args:
        f: Flask view function to wrap

    Returns:
        Wrapped function with signature validation
    """
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Allow explicit opt-out via env or debug flag (for local dev only)
        skip_env = os.getenv("TWILIO_VALIDATE_SIGNATURE", "true").lower() in {"0", "false", "f", "no", "n"}
        skip_debug = current_app.config.get("APP_SETTINGS") and current_app.config["APP_SETTINGS"].debug and current_app.config.get("SKIP_WEBHOOK_VALIDATION", False)

        if not (skip_env or skip_debug):
            settings = current_app.config.get("TWILIO_SETTINGS")
            if not settings or not getattr(settings, "auth_token", None):
                current_app.logger.error("Missing Twilio auth_token for webhook validation.")
                abort(503, description="Webhook validation unavailable")

            validator = TwilioWebhookValidator(settings.auth_token)
            if not validator.validate_request(request):
                current_app.logger.warning(
                    "Invalid Twilio webhook signature from IP: %s",
                    request.remote_addr,
                )
                return {"error": "invalid signature"}, 403

        return f(*args, **kwargs)

    return decorated_function


def mask_sensitive_value(
    value: Optional[str],
    *,
    visible_chars: int = 4,
    mask_char: str = "•",
) -> str:
    """
    Mask sensitive string values for logging/display.

    Args:
        value: Value to mask (API key, token, etc.)
        visible_chars: Number of trailing characters to show
        mask_char: Character to use for masking

    Returns:
        Masked string showing only last N characters

    Examples:
        >>> mask_sensitive_value("sk-1234567890abcdef")
        '••••••••••••cdef'
        >>> mask_sensitive_value(None)
        '❌ Not set'
    """
    if not value:
        return "❌ Not set"

    if len(value) <= visible_chars:
        return mask_char * len(value)

    masked_length = len(value) - visible_chars
    return (mask_char * masked_length) + value[-visible_chars:]


def sanitize_error_message(error: Exception) -> str:
    """
    Sanitize error messages to prevent information leakage.

    Removes sensitive details like file paths, internal IPs, and credentials
    from error messages before displaying to users.

    Args:
        error: Exception to sanitize

    Returns:
        Sanitized error message safe for display
    """
    message = str(error)

    # Remove file system paths
    import re

    message = re.sub(r"/[\w/.-]+", "[PATH]", message)

    # Remove potential credentials
    message = re.sub(
        r"(api[_-]?key|token|password|secret)[=:]\s*\S+",
        r"\1=[REDACTED]",
        message,
        flags=re.IGNORECASE,
    )

    # Remove IP addresses
    message = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[IP]", message)

    # Explicitly mask known secrets from environment
    for env_key in ("TWILIO_AUTH_TOKEN", "OPENAI_API_KEY"):
        secret = os.getenv(env_key)
        if secret and secret in message:
            message = message.replace(secret, "[REDACTED]")

    return message


def generate_csrf_token() -> str:
    """
    Generate CSRF token for form protection.

    Returns:
        Random CSRF token string
    """
    import secrets

    return secrets.token_urlsafe(32)


def verify_csrf_token(token: str, session_token: str) -> bool:
    """
    Verify CSRF token matches session token.

    Args:
        token: Token from form submission
        session_token: Token stored in session

    Returns:
        True if tokens match, False otherwise
    """
    if not token or not session_token:
        return False

    return hmac.compare_digest(token, session_token)
