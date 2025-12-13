"""
Twilio API client wrapper.

Provides a clean interface for sending SMS/MMS messages via Twilio,
with proper error handling and configuration management.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Optional, Dict, Any

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from .config import TwilioSettings
from .exceptions import TwilioAPIError, ConfigurationError


logger = logging.getLogger(__name__)


@dataclass
class TwilioService:
    """
    Twilio API service wrapper for sending messages.
    
    Handles message sending with automatic fallback between messaging
    service and direct number, proper error handling, and logging.
    
    Attributes:
        settings: Twilio configuration (credentials, default sender)
        client: Initialized Twilio REST API client
    """

    settings: TwilioSettings

    def __post_init__(self) -> None:
        """Initialize Twilio REST client after dataclass creation."""
        try:
            self.client = Client(self.settings.account_sid, self.settings.auth_token)
        except Exception as exc:
            raise ConfigurationError(
                f"Failed to initialize Twilio client: {exc}"
            ) from exc

    def send_message(
        self,
        to: str,
        body: str,
        use_messaging_service: Optional[bool] = None,
        messaging_service_sid: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ):
        """
        Send SMS/MMS message via Twilio.
        
        Automatically chooses between Messaging Service and direct number
        based on configuration and parameters.
        
        Args:
            to: Recipient phone number (E.164 format recommended)
            body: Message content (max 1600 chars for SMS)
            use_messaging_service: Force use of messaging service (optional)
            messaging_service_sid: Override messaging service SID (optional)
            extra_params: Additional Twilio API parameters (e.g., media_url)
            
        Returns:
            Twilio message instance
            
        Raises:
            ConfigurationError: If sender identity is not configured
            TwilioAPIError: If Twilio API call fails
            
        Examples:
            >>> service = TwilioService(settings)
            >>> message = service.send_message(
            ...     to="+48123456789",
            ...     body="Hello from Twilio!"
            ... )
        """
        extra_params = dict(extra_params or {})

        params: Dict[str, Any] = {
            "to": to,
            "body": body,
        }

        # Determine sender identity: messaging service or direct number
        should_use_ms = (
            use_messaging_service
            if use_messaging_service is not None
            else bool(self.settings.messaging_service_sid)
        )

        resolved_ms_sid = (
            messaging_service_sid
            or (self.settings.messaging_service_sid if should_use_ms else None)
        )

        if resolved_ms_sid:
            params["messaging_service_sid"] = resolved_ms_sid
        else:
            # Allow explicit from_ passed in extra_params to unblock cases where
            # default_from is not set but inbound To number is available.
            origin = extra_params.pop("from_", None) or self.settings.default_from
            if not origin:
                raise ConfigurationError(
                    "Brak TWILIO_DEFAULT_FROM. Ustaw numer nadawcy w .env "
                    "lub użyj TWILIO_MESSAGING_SERVICE_SID z use_messaging_service=True."
                )
            params["from_"] = origin

        params.update(extra_params)

        try:
            message = self.client.messages.create(**params)
            logger.info(
                "Sent message to %s with SID=%s (status=%s)",
                to,
                message.sid,
                message.status,
            )
            return message
        except TwilioRestException as exc:
            logger.exception("Twilio API error: %s", exc)
            raise TwilioAPIError(
                f"Failed to send message: {exc}",
                twilio_code=exc.code,
                twilio_status=exc.status,
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error sending message: %s", exc)
            raise TwilioAPIError(f"Unexpected error: {exc}") from exc

    def send_sms(
        self,
        *,
        to: str,
        body: str,
        from_: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Convenience wrapper returning a dict result.

        Used by News scheduler / manual News send. Hides raw Twilio
        exceptions behind a simple success/error structure.
        """
        logger = logging.getLogger(__name__)
        try:
            extra_params: Dict[str, Any] = {}
            if from_:
                extra_params["from_"] = from_

            message = self.send_message(
                to=to,
                body=body,
                extra_params=extra_params,
            )

            return {
                "success": True,
                "sid": getattr(message, "sid", None),
                "status": getattr(message, "status", None),
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("Twilio send_sms failed: %s", exc)
            return {
                "success": False,
                "error": str(exc),
            }

    def send_reply_to_inbound(self, *, inbound_from: str, inbound_to: str, body: str):
        """Send an SMS back to the sender of an inbound message.

        Prefers the messaging service when configured; otherwise uses the
        Twilio number that received the inbound message (``inbound_to``) as the
        origin to mirror the conversation thread.
        """

        sender_number = (inbound_from or "").strip()
        origin_number = (inbound_to or "").strip() or self.settings.default_from
        reply_text = body or ""

        if not sender_number:
            raise ValueError("Missing inbound sender number")
        if not origin_number:
            raise RuntimeError(
                "Brak numeru nadawcy Twilio. Ustaw TWILIO_DEFAULT_FROM lub Messaging Service SID."
            )

        extra_params: Dict[str, Any] = {}
        if not self.settings.messaging_service_sid:
            extra_params["from_"] = origin_number

        message = self.send_message(
            to=sender_number,
            body=reply_text,
            extra_params=extra_params,
        )

        return message

    def fetch_message(self, sid: str):
        return self.client.messages(sid).fetch()

    def list_messages(self, **filters):
        return self.client.messages.list(**filters)

    def redact_message(self, sid: str):
        return self.client.messages(sid).update(body="")

    def delete_message(self, sid: str) -> bool:
        """Delete message on Twilio and return bool flag."""
        result = self.client.messages(sid).delete()
        return bool(result)

    @staticmethod
    def _encode_content_variables(value: Dict[str, Any] | str) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value)

    def send_with_default_origin(self, *, to: str, body: str):
        """Send an SMS using default Twilio credentials and default_from number."""

        origin = (self.settings.default_from or "").strip()
        if not origin:
            raise RuntimeError(
                "Brak TWILIO_DEFAULT_FROM. Ustaw numer nadawcy w .env, aby wysyłać wiadomości.")

        message = self.client.messages.create(
            body=body,
            from_=origin,
            to=to,
        )

        return message
