from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any

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
        use_messaging_service: bool = False,
        extra_params: Optional[Dict[str, Any]] = None,
    ):
        extra_params = extra_params or {}

        params: Dict[str, Any] = {
            "to": to,
            "body": body,
        }

        if use_messaging_service and self.settings.messaging_service_sid:
            params["messaging_service_sid"] = self.settings.messaging_service_sid
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
