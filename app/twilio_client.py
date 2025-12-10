from __future__ import annotations

from dataclasses import dataclass
import json
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
        use_messaging_service: Optional[bool] = None,
        messaging_service_sid: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ):
        extra_params = dict(extra_params or {})

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
            # Allow explicit from_ passed in extra_params to unblock cases where
            # default_from is not set but inbound To number is available.
            origin = extra_params.pop("from_", None) or self.settings.default_from
            if not origin:
                raise RuntimeError(
                    "Brak TWILIO_DEFAULT_FROM. Ustaw numer nadawcy w .env "
                    "lub użyj TWILIO_MESSAGING_SERVICE_SID z use_messaging_service=True."
                )
            params["from_"] = origin

        params.update(extra_params)

        message = self.client.messages.create(**params)
        return message

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

    def delete_message(self, sid: str) -> None:
        self.client.messages(sid).delete()

    @staticmethod
    def _encode_content_variables(value: Dict[str, Any] | str) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value)
