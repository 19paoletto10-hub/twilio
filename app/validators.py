"""
Input validation utilities for the Twilio Chat Application.

This module provides centralized validation functions for phone numbers,
message bodies, and other user inputs to ensure security and data integrity.
"""

from __future__ import annotations

import re
from typing import Optional


# E.164 phone number format: +[country code][number] (7-15 digits after +)
E164_PATTERN = re.compile(r"^\+[1-9]\d{6,14}$")


class ValidationError(ValueError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: Optional[str] = None) -> None:
        """
        Initialize validation error.

        Args:
            message: Human-readable error description
            field: Optional field name that failed validation
        """
        super().__init__(message)
        self.field = field
        self.message = message


def validate_e164_phone(phone: str, field_name: str = "phone") -> str:
    """
    Validate and return E.164 formatted phone number.

    Args:
        phone: Phone number to validate
        field_name: Field name for error messages

    Returns:
        Validated phone number in E.164 format

    Raises:
        ValidationError: If phone number format is invalid

    Examples:
        >>> validate_e164_phone("+48123456789")
        '+48123456789'
        >>> validate_e164_phone("invalid")
        Traceback (most recent call last):
        ...
        ValidationError: Invalid phone format
    """
    if not phone or not isinstance(phone, str):
        raise ValidationError(
            f"{field_name} is required and must be a string",
            field=field_name,
        )

    phone = phone.strip()

    if not E164_PATTERN.match(phone):
        raise ValidationError(
            f"{field_name} must be in E.164 format (+[country][number], 7-15 digits)",
            field=field_name,
        )

    return phone


def validate_message_body(
    body: str,
    *,
    max_length: int = 1600,
    allow_empty: bool = False,
    field_name: str = "body",
) -> str:
    """
    Validate SMS/WhatsApp message body.

    Args:
        body: Message content to validate
        max_length: Maximum allowed length (Twilio limit is 1600)
        allow_empty: Whether to allow empty/whitespace-only messages
        field_name: Field name for error messages

    Returns:
        Stripped message body

    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(body, str):
        raise ValidationError(
            f"{field_name} must be a string",
            field=field_name,
        )

    body = body.strip()

    if not allow_empty and not body:
        raise ValidationError(
            f"{field_name} cannot be empty",
            field=field_name,
        )

    if len(body) > max_length:
        raise ValidationError(
            f"{field_name} exceeds maximum length of {max_length} characters",
            field=field_name,
        )

    return body


def validate_interval_seconds(
    interval: int,
    *,
    min_value: int = 60,
    max_value: int = 86400 * 7,  # 7 days
    field_name: str = "interval_seconds",
) -> int:
    """
    Validate scheduling interval in seconds.

    Args:
        interval: Interval value to validate
        min_value: Minimum allowed interval (default: 60 seconds)
        max_value: Maximum allowed interval (default: 7 days)
        field_name: Field name for error messages

    Returns:
        Validated interval value

    Raises:
        ValidationError: If interval is out of allowed range
    """
    try:
        interval = int(interval)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            f"{field_name} must be an integer",
            field=field_name,
        ) from exc

    if interval < min_value:
        raise ValidationError(
            f"{field_name} must be at least {min_value} seconds",
            field=field_name,
        )

    if interval > max_value:
        raise ValidationError(
            f"{field_name} cannot exceed {max_value} seconds",
            field=field_name,
        )

    return interval


def sanitize_sql_identifier(identifier: str) -> str:
    """
    Sanitize SQL table/column identifier to prevent injection.

    Args:
        identifier: SQL identifier to sanitize

    Returns:
        Sanitized identifier (alphanumeric + underscore only)

    Raises:
        ValidationError: If identifier contains invalid characters
    """
    if not identifier or not isinstance(identifier, str):
        raise ValidationError("SQL identifier cannot be empty")

    # Allow only alphanumeric and underscore
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", identifier):
        raise ValidationError(
            f"Invalid SQL identifier: {identifier}. "
            "Only alphanumeric characters and underscores allowed."
        )

    return identifier


def validate_temperature(
    temperature: float,
    *,
    min_value: float = 0.0,
    max_value: float = 2.0,
) -> float:
    """
    Validate OpenAI temperature parameter.

    Args:
        temperature: Temperature value to validate
        min_value: Minimum allowed value (default: 0.0)
        max_value: Maximum allowed value (default: 2.0)

    Returns:
        Validated temperature value

    Raises:
        ValidationError: If temperature is out of range
    """
    try:
        temperature = float(temperature)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            "Temperature must be a number",
            field="temperature",
        ) from exc

    if not (min_value <= temperature <= max_value):
        raise ValidationError(
            f"Temperature must be between {min_value} and {max_value}",
            field="temperature",
        )

    return temperature
