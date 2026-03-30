from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root (parent of the `mindcare` package); `.env` is loaded here so imports work from any cwd.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"
load_dotenv(_ENV_FILE)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    anthropic_api_key: str = ""
    # Use an id from your Anthropic console / https://docs.anthropic.com/en/docs/about-claude/models
    anthropic_model: str = "claude-sonnet-4-20250514"
    anthropic_max_tokens: int = Field(default=1024, ge=1, le=128_000)

    # Aligns with docs/API_CONTRACT.md and docs/DESIGN_DOC.md (8–10 turns).
    max_message_length: int = Field(default=2000, ge=1, le=50_000)
    max_session_turns: int = Field(default=10, ge=1, le=100)

    # When the model returns empty reply_text after stripping.
    empty_reply_fallback: str = Field(default="I'm here with you.", min_length=1, max_length=500)

    mindcare_cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.mindcare_cors_origins.split(",") if o.strip()]

    @property
    def max_session_messages(self) -> int:
        """User + assistant messages retained (two per turn)."""
        return self.max_session_turns * 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
