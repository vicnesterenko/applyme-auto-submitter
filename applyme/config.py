"""Runtime configuration, loaded from environment variables / ``.env``.

All values are optional and have sane defaults. Secrets (Postings API keys) are
never hard-coded — they are read from the environment so they can be injected by
a secret manager in production.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings (prefix ``APPLYME_``).

    Example::

        APPLYME_LEVER_API_KEY=xxxxx
        APPLYME_LEVER_API_KEYS='{"leverdemo": "site-specific-key"}'
        APPLYME_SILENT=true
    """

    model_config = SettingsConfigDict(
        env_prefix="APPLYME_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Official Lever Postings API base URLs (global + EU instances).
    lever_api_base: str = "https://api.lever.co/v0/postings"
    lever_api_base_eu: str = "https://api.eu.lever.co/v0/postings"

    # The Postings *apply* endpoint requires a key the site owner generates in
    # Lever and shares with the integration. A single default key plus an
    # optional per-site override map are supported.
    lever_api_key: str | None = None
    lever_api_keys: dict[str, str] = Field(default_factory=dict)

    # HTTP behaviour.
    request_timeout: float = 30.0
    max_retries: int = 3
    backoff_base: float = 0.5  # seconds; exponential per attempt

    # Politeness delay between consecutive submissions (randomised in range, to
    # respect rate limits — not to evade detection).
    min_delay: float = 1.0
    max_delay: float = 3.0

    # If True, Lever suppresses the confirmation email sent to the candidate.
    silent: bool = False

    def key_for(self, site: str) -> str | None:
        """Return the Postings API key for ``site`` (per-site overrides default)."""
        return self.lever_api_keys.get(site) or self.lever_api_key


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
