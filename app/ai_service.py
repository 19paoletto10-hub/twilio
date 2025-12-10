from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional, Any

from flask import current_app
from openai import OpenAI

from .database import list_messages, normalize_contact
from .twilio_client import TwilioService


@dataclass
class AIResponder:
    api_key: str
    model: str
    system_prompt: str
    temperature: float
    history_limit: int = 20

    def _build_messages(self, participant: str, latest_user_message: Optional[str] = None) -> List[Dict[str, str]]:
        normalized_participant = normalize_contact(participant)
        history = list_messages(
            limit=self.history_limit,
            participant_normalized=normalized_participant,
            ascending=True,
        )
        messages: List[Dict[str, str]] = []

        prompt = (self.system_prompt or "").strip()
        if prompt:
            messages.append({"role": "system", "content": prompt})

        for item in history:
            body = (item.get("body") or "").strip()
            if not body:
                continue

            role = "assistant" if item.get("direction") == "outbound" else "user"
            messages.append({"role": role, "content": body})

        latest = (latest_user_message or "").strip()
        if latest:
            messages.append({"role": "user", "content": latest})

        return messages

    def build_reply(self, participant: str, latest_user_message: Optional[str] = None) -> str:
        messages = self._build_messages(participant, latest_user_message=latest_user_message)
        if not messages:
            current_app.logger.warning(
                "AIResponder: no conversation history available for %s", participant
            )
            return ""

        client = OpenAI(api_key=self.api_key)
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
            )
        except Exception as exc:  # noqa: BLE001
            current_app.logger.exception("AIResponder: OpenAI request failed: %s", exc)
            raise

        try:
            content = response.choices[0].message.content or ""
        except Exception:  # noqa: BLE001
            content = ""

        return (content or "").strip()


class AIReplyError(RuntimeError):
    """Raised for failures when generating or sending AI-driven SMS messages."""

    def __init__(self, message: str, *, reply_text: str = "", status_code: int = 502) -> None:
        super().__init__(message)
        self.reply_text = reply_text
        self.status_code = status_code


@dataclass
class AIMessageDispatchResult:
    reply_text: str
    to_number: str
    normalized_to: str
    twilio_message: Any
    origin_number: Optional[str]

    @property
    def sid(self) -> Optional[str]:
        return getattr(self.twilio_message, "sid", None)

    @property
    def status(self) -> Optional[str]:
        return getattr(self.twilio_message, "status", None)


def send_ai_generated_sms(
    *,
    responder: AIResponder,
    twilio_client: TwilioService,
    participant_number: str,
    latest_user_message: Optional[str] = None,
    reply_text_override: Optional[str] = None,
    origin_number: Optional[str] = None,
    logger=None,
) -> AIMessageDispatchResult:
    """Generate (or reuse) an AI reply and send it via Twilio."""

    log = logger or getattr(current_app, "logger", None)

    destination_raw = (participant_number or "").strip()
    normalized_to = normalize_contact(destination_raw)
    if not normalized_to:
        raise AIReplyError("Podaj poprawny numer odbiorcy.", status_code=400)

    if reply_text_override is None:
        try:
            reply_text = responder.build_reply(
                participant=participant_number,
                latest_user_message=latest_user_message,
            )
        except Exception as exc:  # noqa: BLE001
            if log:
                log.exception("AIResponder failed for %s", participant_number)
            raise AIReplyError(
                f"Generowanie odpowiedzi nie powiodło się: {exc}",
                status_code=502,
            ) from exc
    else:
        reply_text = reply_text_override

    reply_text = (reply_text or "").strip()
    if not reply_text:
        raise AIReplyError("OpenAI nie zwróciło treści odpowiedzi.", status_code=502)

    origin_number = (origin_number or "").strip()
    destination_for_twilio = destination_raw or normalized_to

    try:
        if origin_number:
            message = twilio_client.send_reply_to_inbound(
                inbound_from=destination_for_twilio,
                inbound_to=origin_number,
                body=reply_text,
            )
        else:
            message = twilio_client.send_message(
                to=destination_for_twilio,
                body=reply_text,
            )
    except Exception as exc:  # noqa: BLE001
        if log:
            log.exception("Twilio send failed for %s", participant_number)
        raise AIReplyError(
            f"Wysyłka SMS nie powiodło się: {exc}",
            reply_text=reply_text,
            status_code=502,
        ) from exc

    return AIMessageDispatchResult(
        reply_text=reply_text,
        to_number=participant_number,
        normalized_to=normalized_to,
        twilio_message=message,
        origin_number=origin_number or None,
    )
