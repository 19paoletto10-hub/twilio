from dataclasses import dataclass
import os
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


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "t", "yes", "y"}


def get_settings() -> tuple[AppSettings, TwilioSettings]:
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

    app_settings = AppSettings(
        env=os.getenv("APP_ENV", "dev"),
        debug=_env_bool("APP_DEBUG", True),
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "3000")),
    )

    twilio_settings = TwilioSettings(
        account_sid=os.environ["TWILIO_ACCOUNT_SID"],
        auth_token=os.environ["TWILIO_AUTH_TOKEN"],
        default_from=os.getenv("TWILIO_DEFAULT_FROM", "").strip(),
        messaging_service_sid=os.getenv("TWILIO_MESSAGING_SERVICE_SID"),
    )

    return app_settings, twilio_settings
