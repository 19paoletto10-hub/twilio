"""
Exception hierarchy for the Twilio Chat Application.

Provides structured error handling with specific exception types for
different failure scenarios.
"""

from __future__ import annotations

from typing import Any, Optional


class TwilioChatError(Exception):
    """Base exception for all application-specific errors."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialize application error.

        Args:
            message: Human-readable error message
            status_code: HTTP status code for API responses
            details: Optional additional error details
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ValidationError(TwilioChatError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str,
        *,
        field: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize validation error.

        Args:
            message: Validation error description
            field: Field name that failed validation
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(message, status_code=400, **kwargs)
        self.field = field
        if field:
            self.details["field"] = field


class ConfigurationError(TwilioChatError):
    """Raised when application configuration is invalid or missing."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, status_code=500, **kwargs)


class DatabaseError(TwilioChatError):
    """Raised when database operations fail."""

    def __init__(
        self,
        message: str,
        *,
        operation: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize database error.

        Args:
            message: Error description
            operation: Database operation that failed (e.g., 'insert', 'update')
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(message, status_code=500, **kwargs)
        if operation:
            self.details["operation"] = operation


class TwilioAPIError(TwilioChatError):
    """Raised when Twilio API calls fail."""

    def __init__(
        self,
        message: str,
        *,
        twilio_code: Optional[int] = None,
        twilio_status: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize Twilio API error.

        Args:
            message: Error description
            twilio_code: Twilio error code
            twilio_status: HTTP status from Twilio
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(message, status_code=502, **kwargs)
        if twilio_code:
            self.details["twilio_code"] = twilio_code
        if twilio_status:
            self.details["twilio_status"] = twilio_status


class AIServiceError(TwilioChatError):
    """
    Raised when AI/OpenAI operations fail.
    
    This exception is used for all AI-related failures including:
    - OpenAI API connection errors
    - Token limit exceeded
    - Invalid API key
    - Model not available
    - Response generation failures
    
    Attributes:
        reply_text: Partially generated reply text (if available before failure)
    """

    reply_text: Optional[str]

    def __init__(
        self,
        message: str,
        *,
        reply_text: Optional[str] = None,
        status_code: int = 502,
        **kwargs: Any,
    ) -> None:
        """
        Initialize AI service error.

        Args:
            message: Human-readable error description
            reply_text: Partially generated reply (if available before failure)
            status_code: HTTP status code for API responses (default: 502 Bad Gateway)
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(message, status_code=status_code, **kwargs)
        self.reply_text = reply_text
        if reply_text:
            self.details["reply_text"] = reply_text


class AuthenticationError(TwilioChatError):
    """Raised when authentication/authorization fails."""

    def __init__(self, message: str = "Authentication required", **kwargs: Any) -> None:
        super().__init__(message, status_code=401, **kwargs)


class RateLimitError(TwilioChatError):
    """Raised when rate limits are exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        retry_after: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize rate limit error.

        Args:
            message: Error description
            retry_after: Seconds until retry is allowed
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(message, status_code=429, **kwargs)
        if retry_after:
            self.details["retry_after"] = retry_after


class ResourceNotFoundError(TwilioChatError):
    """Raised when requested resource doesn't exist."""

    def __init__(
        self,
        message: str = "Resource not found",
        *,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize not found error.

        Args:
            message: Error description
            resource_type: Type of resource (e.g., 'message', 'conversation')
            resource_id: ID of missing resource
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(message, status_code=404, **kwargs)
        if resource_type:
            self.details["resource_type"] = resource_type
        if resource_id:
            self.details["resource_id"] = resource_id


# Legacy aliases for backward compatibility
AIReplyError = AIServiceError
