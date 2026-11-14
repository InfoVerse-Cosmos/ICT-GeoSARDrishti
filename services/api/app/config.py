"""Environment configuration for the GeoSAR Drishti FastAPI server.

All external integrations are optional. When a token/key is absent the server
runs in deterministic local-cache mode (SRS §6, §7.2) and never crashes.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# services/api/  (data_store lives here)
API_ROOT = Path(__file__).resolve().parent.parent
DATA_STORE = API_ROOT / "data_store"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # NASA Earthdata live connector (blank -> cached CMR fallback)
    earthdata_token: str = ""

    # CORS: "*" for demo, or comma-separated origins
    cors_origins: str = "*"

    # Optional LLM narrator (blank -> deterministic templates only)
    llm_api_key: str = ""
    llm_api_base: str = ""
    llm_model: str = ""

    # Strict timeout on every external call (SRS §7.2)
    external_timeout_seconds: float = 3.5

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key and self.llm_api_base and self.llm_model)

    @property
    def earthdata_enabled(self) -> bool:
        return bool(self.earthdata_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()
