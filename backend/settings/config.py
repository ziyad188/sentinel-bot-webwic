from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BASE_DIR / ".env"
APP_CONF = BASE_DIR / "conf" / "application.conf"

load_dotenv(dotenv_path=ENV_FILE, override=False)


def _parse_application_conf() -> dict[str, str]:
    if not APP_CONF.exists():
        return {}
    raw = APP_CONF.read_text(encoding="utf-8")
    expanded = os.path.expandvars(raw)
    data: dict[str, str] = {}
    for line in expanded.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not value or "${" in value:
            # Skip empty/unresolved values to allow defaults or env overrides
            continue
        data[key] = value
    return data


def _application_conf_settings(*_args, **_kwargs) -> dict[str, str]:
    return _parse_application_conf()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
    )

    # App
    APP_NAME: str
    APP_ENV: str
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_JWT_SECRET: str
    SUPABASE_SCHEMA: str = "public"
    SUPABASE_DB_HOST: str | None = None
    SUPABASE_DB_PORT: int = 5432
    SUPABASE_DB_NAME: str = "postgres"
    SUPABASE_DB_USER: str | None = None
    SUPABASE_DB_PASSWORD: str | None = None
    SUPABASE_DB_SSLMODE: str = "require"

    # Slack
    SLACK_BOT_TOKEN: str
    SLACK_SIGNING_SECRET: str
    SLACK_APP_TOKEN: str
    SLACK_DEFAULT_CHANNEL: str = "#alerts"

    # Storage (Supabase)
    STORAGE_BUCKET_SCREENSHOTS: str
    STORAGE_BUCKET_VIDEOS: str

    # Logging
    LOG_LEVEL: str = "INFO"

    # Test Service
    TEST_SERVICE_URL: str | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            _application_conf_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
