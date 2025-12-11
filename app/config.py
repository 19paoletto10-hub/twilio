from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


@dataclass
class TwilioSettings:
    account_sid: str
    auth_token: str
    default_from: str
    messaging_service_sid: str | None = None


@dataclass
class AppSettings:
    env: str
    debug: bool
    host: str
    port: int
    db_path: str


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
    def from_env(cls) -> "OpenAISettings":
        """
        Load OpenAI settings from environment variables with sensible defaults.
        
        Returns:
            OpenAISettings instance with validated configuration
        """
        api_key = os.getenv("SECOND_OPENAI", "").strip() or None
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
        """Return masked API key for logging/display (shows last 4 chars)."""
        if not self.api_key:
            return "❌ Brak klucza"
        if len(self.api_key) <= 8:
            return "•" * len(self.api_key)
        return "•" * (len(self.api_key) - 4) + self.api_key[-4:]


def _env_bool(name: str, default: bool = False) -> bool:
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
