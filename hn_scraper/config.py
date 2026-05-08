"""Typed configuration loaded from environment / .env.

Lazy-loaded via :func:`get_settings` so importing this module never
crashes when ``ANTHROPIC_API_KEY`` is unset (e.g. during ``hn-scraper
version`` or ``--help``). Product code calls ``get_settings()`` only
in paths that actually need an API key.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    cheap_model: str = Field("claude-haiku-4-5-20251001", alias="CHEAP_MODEL")
    workhorse_model: str = Field("claude-sonnet-4-6", alias="WORKHORSE_MODEL")
    premium_model: str = Field("claude-opus-4-7", alias="PREMIUM_MODEL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings; first call reads .env / environment."""
    return Settings()  # type: ignore[call-arg]
