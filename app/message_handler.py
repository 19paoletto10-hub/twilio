"""
Message Handler Module - Clean Architecture Implementation.

This module implements the Command pattern for message handling with:
- Single Responsibility Principle (SRP)
- Dependency Injection
- Clean separation of concerns
- Type-safe message routing
- Centralized error handling

Design Patterns Used:
- Command Pattern: Each handler is a self-contained command
- Chain of Responsibility: Handlers are tried in priority order
- Strategy Pattern: Different reply strategies (AI, template, listener)
- Repository Pattern: Database access abstracted away

This replaces the monolithic worker loop in auto_reply.py with
composable, testable handlers.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from .patterns import Result, Success, Failure, RetryConfig, retry, utc_now_iso

logger = logging.getLogger(__name__)


# =============================================================================
# Value Objects
# =============================================================================


class MessageDirection(Enum):
    """Message direction enum."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class ReplyStatus(Enum):
    """Reply status enum."""
    SENT = auto()
    FAILED = auto()
    SKIPPED = auto()
    DUPLICATE = auto()
    DISABLED = auto()


@dataclass(frozen=True, slots=True)
class PhoneNumber:
    """
    Value object for phone numbers with validation.
    
    Implements E.164 format validation with immutability.
    """
    
    value: str
    
    # E.164: + followed by 1-15 digits, starting with non-zero
    E164_PATTERN = re.compile(r"^\+[1-9]\d{6,14}$")
    
    def __post_init__(self) -> None:
        if not self.is_valid():
            raise ValueError(f"Invalid phone number: {self.value}")
    
    def is_valid(self) -> bool:
        """Check if number matches E.164 format."""
        return bool(self.E164_PATTERN.match(self.value))
    
    @classmethod
    def try_parse(cls, value: Optional[str]) -> Optional["PhoneNumber"]:
        """Try to parse phone number, return None if invalid."""
        if not value:
            return None
        try:
            return cls(value.strip())
        except ValueError:
            return None
    
    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class InboundMessage:
    """
    Immutable inbound message value object.
    
    All validation is done at construction time.
    """
    
    sid: Optional[str]
    from_number: PhoneNumber
    to_number: PhoneNumber
    body: str
    received_at: datetime
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Result["InboundMessage", str]:
        """Create InboundMessage from dictionary, returning Result."""
        from_num = PhoneNumber.try_parse(data.get("from_number"))
        to_num = PhoneNumber.try_parse(data.get("to_number"))
        
        if not from_num:
            return Failure("Invalid or missing from_number")
        if not to_num:
            return Failure("Invalid or missing to_number")
        
        received_at_str = data.get("received_at")
        try:
            received_at = datetime.fromisoformat(received_at_str) if received_at_str else datetime.utcnow()
        except ValueError:
            received_at = datetime.utcnow()
        
        return Success(cls(
            sid=data.get("sid"),
            from_number=from_num,
            to_number=to_num,
            body=data.get("body", ""),
            received_at=received_at,
        ))


@dataclass(frozen=True, slots=True)
class ReplyResult:
    """Result of sending a reply."""
    
    status: ReplyStatus
    sid: Optional[str] = None
    to_number: Optional[str] = None
    body: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Handler Protocol and Base Class
# =============================================================================


class MessageHandler(Protocol):
    """Protocol for message handlers."""
    
    @property
    def priority(self) -> int:
        """Handler priority (lower = higher priority)."""
        ...
    
    def can_handle(self, message: InboundMessage) -> bool:
        """Check if this handler can process the message."""
        ...
    
    def handle(self, message: InboundMessage) -> ReplyResult:
        """Process the message and return result."""
        ...


class BaseHandler(ABC):
    """
    Abstract base class for message handlers.
    
    Provides common functionality:
    - Logging
    - Error handling
    - Deduplication check delegation
    """
    
    def __init__(
        self,
        dedup_checker: Callable[[Optional[str], str], bool],
        logger: Optional[logging.Logger] = None,
    ):
        self._dedup_checker = dedup_checker
        self._logger = logger or logging.getLogger(self.__class__.__name__)
    
    @property
    @abstractmethod
    def priority(self) -> int:
        """Handler priority."""
        pass
    
    @abstractmethod
    def can_handle(self, message: InboundMessage) -> bool:
        """Check if handler can process message."""
        pass
    
    @abstractmethod
    def _process(self, message: InboundMessage) -> ReplyResult:
        """Internal processing logic."""
        pass
    
    def handle(self, message: InboundMessage) -> ReplyResult:
        """Handle message with deduplication and error handling."""
        # Check deduplication
        if message.sid and self._dedup_checker(message.sid, str(message.from_number)):
            self._logger.debug(
                "Skipping duplicate SID=%s for %s",
                message.sid, message.from_number
            )
            return ReplyResult(status=ReplyStatus.DUPLICATE)
        
        try:
            return self._process(message)
        except Exception as e:
            self._logger.exception("Handler error: %s", e)
            return ReplyResult(
                status=ReplyStatus.FAILED,
                error=str(e),
            )


# =============================================================================
# Concrete Handlers
# =============================================================================


class CommandHandler(BaseHandler):
    """
    Handler for command-based messages (e.g., /news, /help).
    
    Commands are identified by prefix and routed to specific handlers.
    """
    
    def __init__(
        self,
        command: str,
        processor: Callable[[InboundMessage, str], ReplyResult],
        enabled_checker: Callable[[], bool],
        disabled_response: Optional[str] = None,
        dedup_checker: Callable[[Optional[str], str], bool] = lambda s, f: False,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(dedup_checker, logger)
        self._command = command.lower()
        self._processor = processor
        self._enabled_checker = enabled_checker
        self._disabled_response = disabled_response
    
    @property
    def priority(self) -> int:
        return 10  # Highest priority for commands
    
    def can_handle(self, message: InboundMessage) -> bool:
        return message.body.strip().lower().startswith(self._command)
    
    def _extract_query(self, message: InboundMessage) -> str:
        """Extract query part after command."""
        return message.body.strip()[len(self._command):].strip()
    
    def _process(self, message: InboundMessage) -> ReplyResult:
        if not self._enabled_checker():
            self._logger.info("Command %s is disabled", self._command)
            return ReplyResult(
                status=ReplyStatus.DISABLED,
                body=self._disabled_response,
            )
        
        query = self._extract_query(message)
        self._logger.info(
            "Processing command %s from %s: %s",
            self._command, message.from_number, query[:50]
        )
        
        return self._processor(message, query)


class AIReplyHandler(BaseHandler):
    """
    Handler for AI-powered replies.
    
    Uses OpenAI to generate contextual responses based on conversation history.
    """
    
    def __init__(
        self,
        ai_responder_factory: Callable[[], Any],
        sms_sender: Callable[[str, str, str], Result[Dict[str, Any], Exception]],
        config_getter: Callable[[], Dict[str, Any]],
        dedup_checker: Callable[[Optional[str], str], bool] = lambda s, f: False,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(dedup_checker, logger)
        self._ai_factory = ai_responder_factory
        self._sms_sender = sms_sender
        self._config_getter = config_getter
    
    @property
    def priority(self) -> int:
        return 20  # After commands
    
    def can_handle(self, message: InboundMessage) -> bool:
        config = self._config_getter()
        return bool(config.get("enabled"))
    
    def _process(self, message: InboundMessage) -> ReplyResult:
        config = self._config_getter()
        
        # Validate API key
        api_key = (config.get("api_key") or "").strip()
        if not api_key:
            self._logger.error("AI enabled but API key missing")
            return ReplyResult(
                status=ReplyStatus.FAILED,
                error="Missing OpenAI API key",
            )
        
        try:
            responder = self._ai_factory()
            
            # Generate reply
            reply_text = responder.build_reply(
                participant=str(message.from_number),
                latest_user_message=message.body,
            )
            
            if not reply_text:
                return ReplyResult(
                    status=ReplyStatus.FAILED,
                    error="Empty AI response",
                )
            
            # Send SMS
            result = self._sms_sender(
                str(message.to_number),
                str(message.from_number),
                reply_text,
            )
            
            if result.is_success():
                data = result.unwrap()
                return ReplyResult(
                    status=ReplyStatus.SENT,
                    sid=data.get("sid"),
                    to_number=str(message.from_number),
                    body=reply_text,
                    metadata={"model": responder.model},
                )
            else:
                return ReplyResult(
                    status=ReplyStatus.FAILED,
                    error=str(result.error),
                )
            
        except Exception as e:
            self._logger.exception("AI reply error: %s", e)
            return ReplyResult(
                status=ReplyStatus.FAILED,
                error=str(e),
            )


class TemplateReplyHandler(BaseHandler):
    """
    Handler for template-based auto-replies.
    
    Sends a configured static message when AI is not enabled.
    """
    
    def __init__(
        self,
        config_getter: Callable[[], Dict[str, Any]],
        sms_sender: Callable[[str, str, str], Result[Dict[str, Any], Exception]],
        dedup_checker: Callable[[Optional[str], str], bool] = lambda s, f: False,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(dedup_checker, logger)
        self._config_getter = config_getter
        self._sms_sender = sms_sender
    
    @property
    def priority(self) -> int:
        return 30  # After AI
    
    def can_handle(self, message: InboundMessage) -> bool:
        config = self._config_getter()
        return bool(config.get("enabled"))
    
    def _check_timestamp_filter(self, message: InboundMessage) -> bool:
        """Check if message should be skipped due to timestamp filter."""
        config = self._config_getter()
        enabled_since_str = config.get("enabled_since")
        
        if not enabled_since_str:
            return False
        
        try:
            enabled_since = datetime.fromisoformat(enabled_since_str)
            return message.received_at < enabled_since
        except ValueError:
            return False
    
    def _process(self, message: InboundMessage) -> ReplyResult:
        if self._check_timestamp_filter(message):
            self._logger.info(
                "Skipping auto-reply: message predates enabled toggle"
            )
            return ReplyResult(status=ReplyStatus.SKIPPED)
        
        config = self._config_getter()
        template = (config.get("message") or "").strip()
        
        if not template:
            self._logger.warning("Auto-reply enabled but template is empty")
            return ReplyResult(
                status=ReplyStatus.SKIPPED,
                error="Empty template",
            )
        
        result = self._sms_sender(
            str(message.to_number),
            str(message.from_number),
            template,
        )
        
        if result.is_success():
            data = result.unwrap()
            return ReplyResult(
                status=ReplyStatus.SENT,
                sid=data.get("sid"),
                to_number=str(message.from_number),
                body=template,
            )
        else:
            return ReplyResult(
                status=ReplyStatus.FAILED,
                error=str(result.error),
            )


# =============================================================================
# Handler Chain
# =============================================================================


class HandlerChain:
    """
    Chain of message handlers with priority-based routing.
    
    Handlers are tried in priority order (lower number = higher priority).
    First handler that can_handle() the message processes it.
    """
    
    def __init__(self):
        self._handlers: List[MessageHandler] = []
    
    def add_handler(self, handler: MessageHandler) -> "HandlerChain":
        """Add handler and maintain priority order."""
        self._handlers.append(handler)
        self._handlers.sort(key=lambda h: h.priority)
        return self
    
    def process(self, message: InboundMessage) -> ReplyResult:
        """Process message through handler chain."""
        for handler in self._handlers:
            if handler.can_handle(message):
                return handler.handle(message)
        
        logger.debug("No handler found for message")
        return ReplyResult(status=ReplyStatus.SKIPPED)
    
    def process_dict(self, data: Dict[str, Any]) -> ReplyResult:
        """Process message from dictionary."""
        result = InboundMessage.from_dict(data)
        
        if result.is_failure():
            logger.warning("Invalid message data: %s", result.error)
            return ReplyResult(
                status=ReplyStatus.FAILED,
                error=str(result.error),
            )
        
        return self.process(result.unwrap())


# =============================================================================
# Factory Functions
# =============================================================================


def create_default_handler_chain(
    dedup_checker: Callable[[Optional[str], str], bool],
    ai_config_getter: Callable[[], Dict[str, Any]],
    auto_reply_config_getter: Callable[[], Dict[str, Any]],
    news_processor: Optional[Callable[[InboundMessage, str], ReplyResult]] = None,
    news_enabled_checker: Optional[Callable[[], bool]] = None,
    ai_responder_factory: Optional[Callable[[], Any]] = None,
    sms_sender: Optional[Callable[[str, str, str], Result[Dict[str, Any], Exception]]] = None,
) -> HandlerChain:
    """
    Create default handler chain with all standard handlers.
    
    This is the main entry point for setting up message processing.
    """
    chain = HandlerChain()
    
    # Add /news command handler if provided
    if news_processor and news_enabled_checker:
        chain.add_handler(CommandHandler(
            command="/news",
            processor=news_processor,
            enabled_checker=news_enabled_checker,
            disabled_response="Funkcja /news jest chwilowo niedostępna.",
            dedup_checker=dedup_checker,
        ))
    
    # Add AI handler if factory provided
    if ai_responder_factory and sms_sender:
        chain.add_handler(AIReplyHandler(
            ai_responder_factory=ai_responder_factory,
            sms_sender=sms_sender,
            config_getter=ai_config_getter,
            dedup_checker=dedup_checker,
        ))
    
    # Add template handler if sender provided
    if sms_sender:
        chain.add_handler(TemplateReplyHandler(
            config_getter=auto_reply_config_getter,
            sms_sender=sms_sender,
            dedup_checker=dedup_checker,
        ))
    
    return chain
