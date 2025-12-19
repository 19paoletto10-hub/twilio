"""Centralized helpers for managing API secrets at runtime.

This module provides a thin abstraction over environment-backed secrets
with optional persistence to a local .env file. It keeps responsibilities
small: validation, masking, safe writes, and lightweight connectivity tests.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv, set_key
from openai import OpenAI, OpenAIError
from twilio.rest import Client as TwilioClient

load_dotenv()


@dataclass
class SecretStatus:
    key: str
    value: Optional[str]
    masked: Optional[str]
    source: str
    exists: bool


class SecretsManager:
    """Manage supported secrets with optional .env persistence."""

    SUPPORTED_KEYS = {
        "TWILIO_ACCOUNT_SID": "Twilio Account SID",
        "TWILIO_AUTH_TOKEN": "Twilio Auth Token",
        "TWILIO_DEFAULT_FROM": "Twilio default sender",
        "TWILIO_MESSAGING_SERVICE_SID": "Twilio Messaging Service SID",
        "OPENAI_API_KEY": "OpenAI primary key (chat)",
        "SECOND_OPENAI": "OpenAI secondary key (RAG)",
    }

    def __init__(self, env_path: Optional[str | Path] = None) -> None:
        self.env_path = Path(env_path) if env_path else Path(__file__).resolve().parent.parent / ".env"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def list_statuses(self) -> Dict[str, SecretStatus]:
        return {name: self.get_status(name) for name in self.SUPPORTED_KEYS}

    def get_status(self, key_name: str) -> SecretStatus:
        if key_name not in self.SUPPORTED_KEYS:
            raise ValueError(f"Unsupported secret: {key_name}")
        raw = os.getenv(key_name, "")
        trimmed = raw.strip()
        return SecretStatus(
            key=key_name,
            value=trimmed or None,
            masked=self._mask(trimmed) if trimmed else None,
            source="env" if trimmed else "unset",
            exists=bool(trimmed),
        )

    def set(self, key_name: str, value: str, *, persist_env: bool = False) -> SecretStatus:
        if key_name not in self.SUPPORTED_KEYS:
            raise ValueError(f"Unsupported secret: {key_name}")
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("Secret value cannot be empty")

        self._validate(key_name, normalized)

        os.environ[key_name] = normalized
        if persist_env:
            self._ensure_env_file()
            set_key(str(self.env_path), key_name, normalized)
            load_dotenv(override=True)
        return self.get_status(key_name)

    def test(self, key_name: str, value: Optional[str] = None) -> Dict[str, str]:
        value_to_use = (value or os.getenv(key_name, "")).strip()
        if not value_to_use:
            raise ValueError(f"Secret {key_name} is empty; cannot test")

        if key_name in {"OPENAI_API_KEY", "SECOND_OPENAI"}:
            return self._test_openai(value_to_use)
        if key_name in {"TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_DEFAULT_FROM", "TWILIO_MESSAGING_SERVICE_SID"}:
            return self._test_twilio(value_to_use)

        raise ValueError(f"Testing not supported for {key_name}")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _ensure_env_file(self) -> None:
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.env_path.exists():
            self.env_path.touch(mode=0o600, exist_ok=True)

    @staticmethod
    def _mask(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 4:
            return "•" * len(value)
        return "•" * (len(value) - 4) + value[-4:]

    @staticmethod
    def _validate(key_name: str, value: str) -> None:
        if key_name == "TWILIO_ACCOUNT_SID" and not value.startswith("AC"):
            raise ValueError("TWILIO_ACCOUNT_SID should start with 'AC'")
        if key_name == "TWILIO_AUTH_TOKEN" and len(value) < 16:
            raise ValueError("TWILIO_AUTH_TOKEN looks too short")
        if key_name in {"OPENAI_API_KEY", "SECOND_OPENAI"} and not value.startswith("sk-"):
            raise ValueError("OpenAI key should start with 'sk-'")

    @staticmethod
    def _test_openai(api_key: str) -> Dict[str, str]:
        client = OpenAI(api_key=api_key)
        try:
            response = client.models.list()
        except OpenAIError as exc:
            raise ValueError(f"OpenAI test failed: {exc}") from exc
        first_id = response.data[0].id if response and getattr(response, "data", None) else ""
        return {"ok": "true", "details": f"models.list ok ({first_id or 'no models returned'})"}

    @staticmethod
    def _test_twilio(auth_value: str) -> Dict[str, str]:
        # We need both SID and token to meaningfully test; try to read the counterpart from env.
        sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
        token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()

        if not sid and auth_value.startswith("AC"):
            sid = auth_value
        elif not token and not auth_value.startswith("AC"):
            token = auth_value

        if not sid or not token:
            raise ValueError("Provide both TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN to test Twilio credentials")

        client = TwilioClient(sid, token)
        try:
            account = client.api.accounts(sid).fetch()
        except Exception as exc:  # pragma: no cover - network
            raise ValueError(f"Twilio credentials test failed: {exc}") from exc

        return {
            "ok": "true",
            "details": f"account {getattr(account, 'friendly_name', sid)} verified",
        }
