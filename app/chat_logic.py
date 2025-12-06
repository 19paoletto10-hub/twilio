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
        return f"{self.prefix}{body}"


@dataclass
class KeywordChatEngine(BaseChatEngine):
    """
    Prosty silnik słów kluczowych – łatwo go rozbudujesz.
    """

    responses: Dict[str, str]
    default_response: str = (
        "Nie rozumiem jeszcze tej komendy. Napisz HELP, aby zobaczyć dostępne opcje."
    )

    def build_reply(self, from_number: str, body: str) -> str:
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
    Fabryka silnika czatu. W oparciu o zmienną środowiskową CHAT_MODE
    wybiera tryb bota.
    """
    mode = os.getenv("CHAT_MODE", "echo").lower()

    if mode == "keywords":
        return KeywordChatEngine(
            responses={
                "help": "Pomoc...",
            }
        )

    # domyślnie: echo
    return EchoChatEngine()
