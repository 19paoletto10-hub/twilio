"""
Application configuration management.

This module handles loading and validation of application settings from
environment variables. It provides typed configuration objects for different
components (Twilio, OpenAI, general app settings).
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class TwilioSettings:
    """
    Twilio API credentials and configuration.
    
    Attributes:
        account_sid: Twilio Account SID (from TWILIO_ACCOUNT_SID)
        auth_token: Twilio Auth Token (from TWILIO_AUTH_TOKEN)
        default_from: Default sender phone number (from TWILIO_DEFAULT_FROM)
        messaging_service_sid: Optional Messaging Service SID for sender pool
    """

    account_sid: str
    auth_token: str
    default_from: str
    messaging_service_sid: Optional[str] = None
    
    def validate(self, *, strict: bool = True) -> None:
        """Validate Twilio settings and raise when critical data is missing.

        Args:
            strict: When False, relaxes SID format check (useful in dev when
                using test credentials or placeholders). Defaults to True.
        """
        if not self.account_sid:
            raise ValueError("TWILIO_ACCOUNT_SID is required")

        if strict and not self.account_sid.startswith("AC"):
            raise ValueError("Invalid TWILIO_ACCOUNT_SID format")

        if not self.auth_token:
            raise ValueError("TWILIO_AUTH_TOKEN is required")

        # default_from is optional if messaging_service_sid is set
        if not self.default_from and not self.messaging_service_sid:
            raise ValueError(
                "Either TWILIO_DEFAULT_FROM or TWILIO_MESSAGING_SERVICE_SID must be set"
            )


@dataclass
class AppSettings:
    """
    General application configuration.
    
    Attributes:
        env: Environment name ('dev', 'staging', 'production')
        debug: Enable debug mode (verbose logging, auto-reload)
        host: Server bind address
        port: Server bind port
        db_path: SQLite database file path
    """

    env: str
    debug: bool
    host: str
    port: int
    db_path: str
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.env.lower() in ("production", "prod")
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.env.lower() in ("dev", "development")


@dataclass
class OpenAISettings:
    """
    OpenAI API configuration for embeddings and chat completion.
    
    Attributes:
        api_key: OpenAI API key (SECOND_OPENAI env var)
        chat_model: Model for chat completions (SECOND_MODEL env var)
        embedding_model: Model for text embeddings (EMBEDDING_MODEL env var)
        enabled: Whether OpenAI integration is available
    """
    api_key: str | None
    chat_model: str
    embedding_model: str
    enabled: bool

    @classmethod
    def from_env(cls) -> OpenAISettings:
        """
        Load OpenAI settings from environment variables with sensible defaults.
        
        Environment variables:
            SECOND_OPENAI: Primary API key for OpenAI
            OPENAI_API_KEY: Fallback API key
            SECOND_MODEL: Chat completion model (default: gpt-4o-mini)
            EMBEDDING_MODEL: Text embedding model (default: text-embedding-3-large)
        
        Returns:
            OpenAISettings instance with validated configuration
        """
        # Try primary key first, then fallback
        api_key = os.getenv("SECOND_OPENAI", "").strip() or None
        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY", "").strip() or None
        
        chat_model = os.getenv("SECOND_MODEL", "gpt-4o-mini").strip()
        embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large").strip()
        
        # Validate models if API key is present
        enabled = bool(api_key)
        
        return cls(
            api_key=api_key,
            chat_model=chat_model,
            embedding_model=embedding_model,
            enabled=enabled,
        )

    def get_masked_key(self) -> str:
        """
        Return masked API key for logging/display (shows last 4 chars).
        
        Returns:
            Masked API key string safe for logging
            
        Examples:
            >>> settings = OpenAISettings(api_key="sk-1234567890", ...)
            >>> settings.get_masked_key()
            '••••••7890'
        """
        if not self.api_key:
            return "❌ Brak klucza"
        if len(self.api_key) <= 8:
            return "•" * len(self.api_key)
        return "•" * (len(self.api_key) - 4) + self.api_key[-4:]


def _env_bool(name: str, default: bool = False) -> bool:
    """
    Parse boolean from environment variable.
    
    Accepts: '1', 'true', 't', 'yes', 'y' (case-insensitive) as True
    
    Args:
        name: Environment variable name
        default: Default value if variable is not set
        
    Returns:
        Parsed boolean value
    """
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "t", "yes", "y"}


def get_settings() -> tuple[AppSettings, TwilioSettings, OpenAISettings]:
    """
    Load and validate all application settings from environment.
    
    Returns:
        Tuple of (AppSettings, TwilioSettings, OpenAISettings)
        
    Raises:
        RuntimeError: If required Twilio credentials are missing
    """
    missing = []
    for key in ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"]:
        if not os.getenv(key):
            missing.append(key)

    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Missing required environment variables: {joined}. "
            "Uzupełnij plik .env lub ustaw zmienne środowiskowe."
        )

    project_root = Path(__file__).resolve().parent.parent
    db_path_value = os.getenv("DB_PATH", "data/app.db")
    db_path = Path(db_path_value)
    if not db_path.is_absolute():
        db_path = project_root / db_path

    app_settings = AppSettings(
        env=os.getenv("APP_ENV", "dev"),
        debug=_env_bool("APP_DEBUG", True),
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "3000")),
        db_path=str(db_path),
    )

    twilio_settings = TwilioSettings(
        account_sid=os.environ["TWILIO_ACCOUNT_SID"],
        auth_token=os.environ["TWILIO_AUTH_TOKEN"],
        default_from=os.getenv("TWILIO_DEFAULT_FROM", "").strip(),
        messaging_service_sid=os.getenv("TWILIO_MESSAGING_SERVICE_SID"),
    )
    twilio_settings.validate(strict=not app_settings.debug)
    
    openai_settings = OpenAISettings.from_env()
    
    # Log OpenAI configuration status (dev/debug mode only)
    if app_settings.debug:
        import logging
        logger = logging.getLogger(__name__)
        if openai_settings.enabled:
            logger.info(
                "✅ OpenAI integration enabled | Model: %s | Embeddings: %s | Key: %s",
                openai_settings.chat_model,
                openai_settings.embedding_model,
                openai_settings.get_masked_key(),
            )
        else:
            logger.warning(
                "⚠️ OpenAI integration disabled (brak klucza SECOND_OPENAI). "
                "FAISS użyje fallback embeddings, a odpowiedzi LLM będą wyłączone."
            )

    return app_settings, twilio_settings, openai_settings


def reload_runtime_settings(app) -> dict:
    """Reload settings from environment and refresh runtime clients.

    Re-evaluates env vars, re-validates Twilio/OpenAI config and swaps
    objects stored in ``app.config``. Raises if required credentials
    are missing to avoid half-configured state.
    """

    from .twilio_client import TwilioService  # local import to avoid cycle

    app_settings, twilio_settings, openai_settings = get_settings()
    app.config["APP_SETTINGS"] = app_settings
    app.config["TWILIO_SETTINGS"] = twilio_settings
    app.config["OPENAI_SETTINGS"] = openai_settings
    app.config["TWILIO_CLIENT"] = TwilioService(twilio_settings)

    return {
        "app_env": app_settings.env,
        "twilio_account": twilio_settings.account_sid,
        "openai_enabled": openai_settings.enabled,
        "chat_model": openai_settings.chat_model,
        "embedding_model": openai_settings.embedding_model,
    }
