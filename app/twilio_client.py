from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Optional, Dict, Any, Iterable

from twilio.rest import Client

from .config import TwilioSettings


@dataclass
class TwilioService:
    settings: TwilioSettings

    def __post_init__(self) -> None:
        self.client = Client(self.settings.account_sid, self.settings.auth_token)

    def send_message(
        self,
        to: str,
        body: str,
        use_messaging_service: Optional[bool] = None,
        messaging_service_sid: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ):
        extra_params = extra_params or {}

        params: Dict[str, Any] = {
            "to": to,
            "body": body,
        }

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
            if not self.settings.default_from:
                raise RuntimeError(
                    "Brak TWILIO_DEFAULT_FROM. Ustaw numer nadawcy w .env "
                    "lub użyj TWILIO_MESSAGING_SERVICE_SID z use_messaging_service=True."
                )
            params["from_"] = self.settings.default_from

        params.update(extra_params)

        message = self.client.messages.create(**params)
        return message

    def send_whatsapp_message(
        self,
        *,
        to: str,
        body: Optional[str] = None,
        media_urls: Optional[Iterable[str]] = None,
        messaging_service_sid: Optional[str] = None,
        content_sid: Optional[str] = None,
        content_variables: Optional[Dict[str, Any] | str] = None,
    ):
        from_number = self._normalize_whatsapp_address(self.settings.whatsapp_from)
        to_number = self._normalize_whatsapp_address(to)

        params: Dict[str, Any] = {
            "from_": from_number,
            "to": to_number,
        }

        if messaging_service_sid:
            params["messaging_service_sid"] = messaging_service_sid
        if body:
            params["body"] = body
        if media_urls:
            params["media_url"] = list(media_urls)
        if content_sid:
            params["content_sid"] = content_sid
        if content_variables:
            params["content_variables"] = self._encode_content_variables(content_variables)

        message = self.client.messages.create(**params)
        return message

    def fetch_message(self, sid: str):
        return self.client.messages(sid).fetch()

    def list_messages(self, **filters):
        return self.client.messages.list(**filters)

    def redact_message(self, sid: str):
        return self.client.messages(sid).update(body="")

    def delete_message(self, sid: str) -> None:
        self.client.messages(sid).delete()

    def _normalize_whatsapp_address(self, value: Optional[str]) -> str:
        if not value:
            raise RuntimeError(
                "Brak TWILIO_WHATSAPP_FROM. Ustaw whatsappowy numer nadawcy w .env."
            )
        trimmed = value.strip()
        return trimmed if trimmed.startswith("whatsapp:") else f"whatsapp:{trimmed}"

    @staticmethod
    def _encode_content_variables(value: Dict[str, Any] | str) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value)
