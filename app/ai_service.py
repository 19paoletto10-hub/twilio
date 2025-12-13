"""
AI-powered message generation and dispatch.

Provides OpenAI-based conversational AI for generating context-aware
SMS responses using chat history and configurable prompts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional, Any

from flask import current_app
from openai import OpenAI
from openai import OpenAIError

from .database import list_messages, normalize_contact
from .twilio_client import TwilioService
from .exceptions import AIServiceError, ConfigurationError


@dataclass
class AIResponder:
    """
    OpenAI-powered conversational AI responder.
    
    Generates context-aware responses based on conversation history
    using OpenAI's chat completion API.
    
    Attributes:
        api_key: OpenAI API key
        model: Model name (e.g., 'gpt-4o-mini', 'gpt-4')
        system_prompt: System message defining AI behavior
        temperature: Response randomness (0.0-2.0)
        history_limit: Max conversation messages to include
    """

    api_key: str
    model: str
    system_prompt: str
    temperature: float
    history_limit: int = 20

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.api_key:
            raise ConfigurationError("OpenAI API key is required")
        
        if not 0.0 <= self.temperature <= 2.0:
            raise ConfigurationError(
                f"Temperature must be 0.0-2.0, got {self.temperature}"
            )
        
        if self.history_limit < 1:
            raise ConfigurationError(
                f"History limit must be >= 1, got {self.history_limit}"
            )

    def _build_messages(
        self,
        participant: str,
        latest_user_message: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Build OpenAI chat messages from conversation history.
        
        Retrieves recent messages with the participant and formats them
        as OpenAI chat messages (system, user, assistant roles).
        
        Args:
            participant: Phone number of conversation participant
            latest_user_message: Optional new message to append
            
        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        normalized_participant = normalize_contact(participant)
        history = list_messages(
            limit=self.history_limit,
            participant_normalized=normalized_participant,
            ascending=True,
        )
        messages: List[Dict[str, str]] = []

        # Add system prompt if configured
        prompt = (self.system_prompt or "").strip()
        if prompt:
            messages.append({"role": "system", "content": prompt})

        # Convert message history to chat format
        for item in history:
            body = (item.get("body") or "").strip()
            if not body:
                continue

            role = "assistant" if item.get("direction") == "outbound" else "user"
            messages.append({"role": role, "content": body})

        # Append latest user message if provided
        latest = (latest_user_message or "").strip()
        if latest:
            messages.append({"role": "user", "content": latest})

        return messages

    def build_reply(
        self,
        participant: str,
        latest_user_message: Optional[str] = None,
    ) -> str:
        """
        Generate AI response for conversation participant.
        
        Uses OpenAI chat completion API with conversation history
        to generate contextually relevant responses.
        
        Args:
            participant: Phone number of conversation participant
            latest_user_message: Optional new message from user
            
        Returns:
            Generated response text
            
        Raises:
            AIServiceError: If OpenAI API call fails
            
        Examples:
            >>> responder = AIResponder(api_key="...", model="gpt-4o-mini", ...)
            >>> reply = responder.build_reply("+48123456789", "Hello!")
            >>> print(reply)
            'Hi there! How can I help you today?'
        """
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
        except OpenAIError as exc:
            current_app.logger.exception("AIResponder: OpenAI API error: %s", exc)
            raise AIServiceError(f"OpenAI API request failed: {exc}") from exc
        except Exception as exc:
            current_app.logger.exception("AIResponder: Unexpected error: %s", exc)
            raise AIServiceError(f"Unexpected error: {exc}") from exc

        try:
            content = response.choices[0].message.content or ""
        except (IndexError, AttributeError):
            content = ""

        return (content or "").strip()


# Legacy alias for backward compatibility
AIReplyError = AIServiceError


@dataclass
class AIMessageDispatchResult:
    """
    Result of AI message generation and dispatch.
    
    Contains the generated message, recipient info, and Twilio response.
    
    Attributes:
        reply_text: Generated AI response
        to_number: Recipient phone number
        normalized_to: Normalized recipient phone
        twilio_message: Twilio message instance
        origin_number: Sender phone number (optional)
    """

    reply_text: str
    to_number: str
    normalized_to: str
    twilio_message: Any
    origin_number: Optional[str]

    @property
    def sid(self) -> Optional[str]:
        """Get Twilio message SID."""
        return getattr(self.twilio_message, "sid", None)

    @property
    def status(self) -> Optional[str]:
        """Get Twilio message status."""
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
    """
    Generate (or reuse) an AI reply and send it via Twilio.
    
    This is the main entry point for AI-powered SMS sending. It either
    generates a new response using AIResponder or uses a provided override,
    then sends via Twilio.
    
    Args:
        responder: Configured AIResponder instance
        twilio_client: Configured TwilioService instance
        participant_number: Recipient phone number
        latest_user_message: Optional new message from user (for context)
        reply_text_override: Optional pre-generated reply (skip AI generation)
        origin_number: Optional sender number (for replies to inbound)
        logger: Optional logger instance
        
    Returns:
        AIMessageDispatchResult with dispatch details
        
    Raises:
        AIServiceError: If AI generation or sending fails
        ValidationError: If participant number is invalid
    """
    from .validators import ValidationError, validate_e164_phone
    
    log = logger or getattr(current_app, "logger", None)

    destination_raw = (participant_number or "").strip()
    
    try:
        normalized_to = normalize_contact(destination_raw)
        if not normalized_to:
            raise ValidationError(
                "Podaj poprawny numer odbiorcy.",
                field="participant_number",
            )
    except Exception as exc:
        raise AIServiceError(
            f"Invalid participant number: {exc}",
            status_code=400,
        ) from exc

    # Generate AI response if not provided
    if reply_text_override is None:
        try:
            reply_text = responder.build_reply(
                participant=participant_number,
                latest_user_message=latest_user_message,
            )
        except Exception as exc:
            if log:
                log.exception("AIResponder failed for %s", participant_number)
            raise AIServiceError(
                f"Generowanie odpowiedzi nie powiodło się: {exc}",
                status_code=502,
            ) from exc
    else:
        reply_text = reply_text_override

    reply_text = (reply_text or "").strip()
    if not reply_text:
        raise AIServiceError(
            "OpenAI nie zwróciło treści odpowiedzi.",
            status_code=502,
        )

    origin_number = (origin_number or "").strip()
    destination_for_twilio = destination_raw or normalized_to

    # Send via Twilio
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
    except Exception as exc:
        if log:
            log.exception("Twilio send failed for %s", participant_number)
        raise AIServiceError(
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
