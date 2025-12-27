"""
Input validation utilities for the Twilio Chat Application.

This module provides centralized validation functions for phone numbers,
message bodies, and other user inputs to ensure security and data integrity.

Design Principles:
- Fail-fast validation with descriptive errors
- Type safety with explicit return types
- Composable validators for complex inputs
- Immutable validation results
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generic, List, Optional, Tuple, TypeVar, Union

# =============================================================================
# Constants
# =============================================================================

# E.164 phone number format: +[country code][number] (7-15 digits after +)
E164_PATTERN = re.compile(r"^\+[1-9]\d{6,14}$")

# Common regex patterns
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-_]*[a-z0-9]$|^[a-z0-9]$")
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
URL_PATTERN = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)

# Type variable for generic validators
T = TypeVar("T")


# =============================================================================
# Validation Result Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class ValidationSuccess(Generic[T]):
    """Represents a successful validation."""
    value: T
    
    def is_valid(self) -> bool:
        return True
    
    def get_value(self) -> T:
        return self.value
    
    def get_error(self) -> None:
        return None


@dataclass(frozen=True, slots=True)
class ValidationFailure:
    """Represents a failed validation."""
    message: str
    field: Optional[str] = None
    code: Optional[str] = None
    
    def is_valid(self) -> bool:
        return False
    
    def get_value(self) -> None:
        return None
    
    def get_error(self) -> str:
        return self.message


# Union type for validation results
ValidationResult = Union[ValidationSuccess[T], ValidationFailure]


# =============================================================================
# Exception Classes
# =============================================================================
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


# =============================================================================
# Composable Validators (Builder Pattern)
# =============================================================================


@dataclass
class Validator(Generic[T]):
    """
    Composable validator using the Builder pattern.
    
    Allows chaining multiple validation rules:
        result = (Validator(phone_input)
            .not_empty("Phone is required")
            .matches(E164_PATTERN, "Invalid phone format")
            .max_length(15)
            .validate())
    """
    
    value: Any
    field_name: str = "value"
    _errors: List[str] = field(default_factory=list)
    _transformed: Any = None
    
    def __post_init__(self) -> None:
        self._transformed = self.value
    
    def not_empty(self, message: Optional[str] = None) -> "Validator[T]":
        """Validate that value is not empty/None."""
        if not self._transformed:
            self._errors.append(message or f"{self.field_name} is required")
        return self
    
    def not_none(self, message: Optional[str] = None) -> "Validator[T]":
        """Validate that value is not None."""
        if self._transformed is None:
            self._errors.append(message or f"{self.field_name} cannot be None")
        return self
    
    def min_length(self, length: int, message: Optional[str] = None) -> "Validator[T]":
        """Validate minimum length for strings."""
        if self._transformed and len(str(self._transformed)) < length:
            self._errors.append(
                message or f"{self.field_name} must be at least {length} characters"
            )
        return self
    
    def max_length(self, length: int, message: Optional[str] = None) -> "Validator[T]":
        """Validate maximum length for strings."""
        if self._transformed and len(str(self._transformed)) > length:
            self._errors.append(
                message or f"{self.field_name} cannot exceed {length} characters"
            )
        return self
    
    def matches(self, pattern: re.Pattern[str], message: Optional[str] = None) -> "Validator[T]":
        """Validate that value matches regex pattern."""
        if self._transformed and not pattern.match(str(self._transformed)):
            self._errors.append(
                message or f"{self.field_name} has invalid format"
            )
        return self
    
    def in_range(
        self, 
        min_val: Union[int, float], 
        max_val: Union[int, float],
        message: Optional[str] = None
    ) -> "Validator[T]":
        """Validate numeric range."""
        try:
            num = float(self._transformed)
            if not (min_val <= num <= max_val):
                self._errors.append(
                    message or f"{self.field_name} must be between {min_val} and {max_val}"
                )
        except (TypeError, ValueError):
            self._errors.append(f"{self.field_name} must be a number")
        return self
    
    def transform(self, fn: Callable[[Any], T]) -> "Validator[T]":
        """Apply transformation function to value."""
        try:
            self._transformed = fn(self._transformed)
        except Exception as e:
            self._errors.append(f"Transformation failed: {e}")
        return self
    
    def strip(self) -> "Validator[T]":
        """Strip whitespace from string values."""
        if isinstance(self._transformed, str):
            self._transformed = self._transformed.strip()
        return self
    
    def lowercase(self) -> "Validator[T]":
        """Convert to lowercase."""
        if isinstance(self._transformed, str):
            self._transformed = self._transformed.lower()
        return self
    
    def custom(
        self, 
        predicate: Callable[[Any], bool], 
        message: str
    ) -> "Validator[T]":
        """Apply custom validation predicate."""
        if self._transformed and not predicate(self._transformed):
            self._errors.append(message)
        return self
    
    def validate(self) -> ValidationResult[T]:
        """Execute validation and return result."""
        if self._errors:
            return ValidationFailure(
                message="; ".join(self._errors),
                field=self.field_name,
            )
        return ValidationSuccess(self._transformed)
    
    def validate_or_raise(self) -> T:
        """Execute validation and raise on failure."""
        result = self.validate()
        if isinstance(result, ValidationFailure):
            raise ValidationError(result.message, field=result.field)
        return result.value


# =============================================================================
# Specialized Validators
# =============================================================================


def validate_phone_numbers(
    numbers: List[str],
    *,
    skip_invalid: bool = False
) -> Tuple[List[str], List[str]]:
    """
    Validate a list of phone numbers.
    
    Args:
        numbers: List of phone numbers to validate
        skip_invalid: If True, return valid numbers and invalid separately
        
    Returns:
        Tuple of (valid_numbers, invalid_numbers)
    """
    valid: List[str] = []
    invalid: List[str] = []
    
    for number in numbers:
        try:
            validated = validate_e164_phone(number)
            valid.append(validated)
        except ValidationError:
            if skip_invalid:
                invalid.append(number)
            else:
                raise
    
    return valid, invalid


def validate_json_payload(
    data: Dict[str, Any],
    required_fields: List[str],
    optional_fields: Optional[List[str]] = None,
) -> ValidationResult[Dict[str, Any]]:
    """
    Validate JSON payload structure.
    
    Args:
        data: JSON data to validate
        required_fields: List of required field names
        optional_fields: List of allowed optional fields
        
    Returns:
        ValidationResult with validated data or error
    """
    if not isinstance(data, dict):
        return ValidationFailure("Payload must be a JSON object")
    
    missing = [f for f in required_fields if f not in data]
    if missing:
        return ValidationFailure(
            f"Missing required fields: {', '.join(missing)}",
            code="MISSING_FIELDS",
        )
    
    # Filter to allowed fields if optional_fields specified
    if optional_fields is not None:
        allowed = set(required_fields) | set(optional_fields)
        filtered = {k: v for k, v in data.items() if k in allowed}
        return ValidationSuccess(filtered)
    
    return ValidationSuccess(data)
