"""Application configuration.

All secrets are read from environment variables. Development works without external
API keys because integrations expose clean fallback/mock implementations.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # Allows non-API modules to import before dependencies are installed.
    def load_dotenv(*_args, **_kwargs):
        return False

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"

# Load .env if present. Missing file is fine.
load_dotenv(ROOT_DIR / ".env")


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "AI Travel Agent")
    environment: str = os.getenv("ENVIRONMENT", "development")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./travel_agent.sqlite3")
    base_currency: str = os.getenv("BASE_CURRENCY", "INR").upper()
    allow_anonymous: bool = _bool_env("ALLOW_ANONYMOUS", True)
    api_key: str | None = os.getenv("API_KEY") or None

    use_live_apis: bool = _bool_env("USE_LIVE_APIS", False)
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    google_maps_api_key: str | None = os.getenv("GOOGLE_MAPS_API_KEY") or None
    amadeus_api_key: str | None = os.getenv("AMADEUS_API_KEY") or None
    amadeus_api_secret: str | None = os.getenv("AMADEUS_API_SECRET") or None
    weather_api_key: str | None = os.getenv("WEATHER_API_KEY") or None
    places_api_key: str | None = os.getenv("PLACES_API_KEY") or None
    currency_api_key: str | None = os.getenv("CURRENCY_API_KEY") or None

    @property
    def sqlite_path(self) -> Path:
        """Resolve the SQLite file path from DATABASE_URL."""
        if self.database_url.startswith("sqlite:///"):
            raw = self.database_url.replace("sqlite:///", "", 1)
            path = Path(raw)
            return path if path.is_absolute() else ROOT_DIR / path
        # The app intentionally supports SQLite only by default. Other databases
        # can be added behind this property without changing business modules.
        return ROOT_DIR / "travel_agent.sqlite3"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
