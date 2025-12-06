from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import os
from typing import Dict


class BaseChatEngine(ABC):
    @abstractmethod
    def build_reply(self, from_number: str, body: str) -> str:
        ...


@dataclass
class EchoChatEngine(BaseChatEngine):
    prefix: str = "Echo: "

    def build_reply(self, from_number: str, body: str) -> str:
        """
        Echo the received message back to the sender with a prefix.
        This is the default auto-reply mode for SMS messages.
        """
        if not body or not body.strip():
            return "Received your message."
        return f"{self.prefix}{body}"


@dataclass
class KeywordChatEngine(BaseChatEngine):
    """
    Simple keyword-based chat engine for SMS auto-replies.
    Responds to common commands like HELP, START, STOP.
    """

    responses: Dict[str, str]
    default_response: str = (
        "Nie rozumiem jeszcze tej komendy. Napisz HELP, aby zobaczyć dostępne opcje."
    )

    def build_reply(self, from_number: str, body: str) -> str:
        """Generate a reply based on keywords in the message body."""
        if not body or not body.strip():
            return self.default_response
            
        text = body.strip().lower()
        
        if text == "help":
            return "Dostępne komendy: HELP, START, STOP."
        if text == "start":
            return "Witaj! Bot został aktywowany."
        if text == "stop":
            return "OK, nie będę więcej wysyłać wiadomości (logika do zaimplementowania)."

        return self.default_response


def build_chat_engine() -> BaseChatEngine:
    """
    Factory function for creating the chat engine based on CHAT_MODE environment variable.
    
    Supported modes:
    - 'echo': Echo back received messages (default)
    - 'keywords': Respond to specific keywords (HELP, START, STOP)
    
    Returns:
        BaseChatEngine: The configured chat engine instance
    """
    mode = os.getenv("CHAT_MODE", "echo").lower()

    if mode == "keywords":
        return KeywordChatEngine(
            responses={
                "help": "Pomoc...",
            }
        )

    # Default: echo mode for SMS auto-replies
    return EchoChatEngine()
