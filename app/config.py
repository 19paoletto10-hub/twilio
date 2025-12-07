from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


@dataclass
class TwilioSettings:
    account_sid: str | None
    auth_token: str | None
    default_from: str
    messaging_service_sid: str | None = None


@dataclass
class AppSettings:
    env: str
    debug: bool
    host: str
    port: int
    db_path: str
    api_key: str | None = None
    validate_twilio_signature: bool = True


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "t", "yes", "y"}


def get_settings() -> tuple[AppSettings, TwilioSettings]:
    # Note: TWILIO credentials are optional at startup to allow running the
    # application in a degraded/demo mode without real Twilio keys. Parts of
    # the app that require Twilio will be disabled and will log warnings.

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
        api_key=os.getenv("APP_API_KEY"),
        validate_twilio_signature=_env_bool("TWILIO_VALIDATE_SIGNATURE", True),
    )

    twilio_settings = TwilioSettings(
        account_sid=os.getenv("TWILIO_ACCOUNT_SID") or None,
        auth_token=os.getenv("TWILIO_AUTH_TOKEN") or None,
        default_from=os.getenv("TWILIO_DEFAULT_FROM", "").strip(),
        messaging_service_sid=os.getenv("TWILIO_MESSAGING_SERVICE_SID"),
    )

    return app_settings, twilio_settings
