"""
Chat engine implementations for automated SMS responses.

Provides different strategies for generating automated replies:
- EchoChatEngine: Simple echo back with prefix (default)
- KeywordChatEngine: Command-based responses (HELP, START, STOP)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import os
from typing import Dict


class BaseChatEngine(ABC):
    """
    Abstract base class for chat engines.
    
    Implementations should provide context-aware or rule-based
    responses to incoming SMS messages.
    """

    @abstractmethod
    def build_reply(self, from_number: str, body: str) -> str:
        """
        Generate reply for incoming message.
        
        Args:
            from_number: Sender's phone number
            body: Message content
            
        Returns:
            Reply text to send back
        """
        ...


@dataclass
class EchoChatEngine(BaseChatEngine):
    """
    Simple echo chat engine for testing and demos.
    
    Echoes back the received message with a configurable prefix.
    This is the default auto-reply mode for SMS messages.
    
    Attributes:
        prefix: Text prepended to echoed message (default: "Echo: ")
        
    Examples:
        >>> engine = EchoChatEngine(prefix="You said: ")
        >>> reply = engine.build_reply("+48123456789", "Hello")
        >>> print(reply)
        'You said: Hello'
    """

    prefix: str = "Echo: "

    def build_reply(self, from_number: str, body: str) -> str:
        """
        Echo the received message back to the sender with a prefix.
        
        Args:
            from_number: Sender's phone number (unused)
            body: Message content to echo
            
        Returns:
            Prefixed echo of the original message
        """
        if not body or not body.strip():
            return "Otrzymałem Twoją wiadomość."
        return f"{self.prefix}{body}"


@dataclass
class KeywordChatEngine(BaseChatEngine):
    """
    Keyword-based chat engine for SMS auto-replies.
    
    Responds to common commands like HELP, START, STOP with
    predefined messages. Useful for simple interactive bots.
    
    Attributes:
        responses: Mapping of keywords to responses
        default_response: Fallback message for unknown commands
        
    Examples:
        >>> engine = KeywordChatEngine(responses={"hello": "Hi there!"})
        >>> reply = engine.build_reply("+48123456789", "hello")
        >>> print(reply)
        'Hi there!'
    """

    responses: Dict[str, str]
    default_response: str = (
        "Nie rozumiem jeszcze tej komendy. Napisz HELP, aby zobaczyć dostępne opcje."
    )

    def build_reply(self, from_number: str, body: str) -> str:
        """
        Generate a reply based on keywords in the message body.
        
        Checks for case-insensitive keyword matches and returns
        corresponding responses. Built-in commands: HELP, START, STOP.
        
        Args:
            from_number: Sender's phone number (unused)
            body: Message content containing potential keywords
            
        Returns:
            Response for matched keyword or default message
        """
        if not body or not body.strip():
            return self.default_response
            
        text = body.strip().lower()
        
        # Built-in commands
        if text == "help":
            return "Dostępne komendy: HELP, START, STOP."
        if text == "start":
            return "Witaj! Bot został aktywowany."
        if text == "stop":
            return (
                "OK, nie będę więcej wysyłać wiadomości. "
                "Aby wznowić, napisz START."
            )

        # Custom keyword responses
        if text in self.responses:
            return self.responses[text]

        return self.default_response


def build_chat_engine() -> BaseChatEngine:
    """
    Factory function for creating the chat engine based on CHAT_MODE env var.
    
    Supported modes:
    - 'echo': Echo back received messages (default)
    - 'keywords': Respond to specific keywords (HELP, START, STOP)
    
    Returns:
        Configured chat engine instance
        
    Environment Variables:
        CHAT_MODE: Engine type ('echo' or 'keywords')
        
    Examples:
        >>> import os
        >>> os.environ['CHAT_MODE'] = 'echo'
        >>> engine = build_chat_engine()
        >>> isinstance(engine, EchoChatEngine)
        True
    """
    mode = os.getenv("CHAT_MODE", "echo").lower()

    if mode == "keywords":
        return KeywordChatEngine(
            responses={
                "pomoc": "Dostępne komendy: POMOC, START, STOP.",
                "info": "To jest automatyczny bot SMS.",
            }
        )

    # Default: echo mode for SMS auto-replies
    return EchoChatEngine()
