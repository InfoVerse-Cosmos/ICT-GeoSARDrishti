"""Environment configuration for the GeoSAR Drishti FastAPI server.

All external integrations are optional. When a token/key is absent the server
runs in deterministic local-cache mode (SRS §6, §7.2) and never crashes.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# services/api/  (default data_store lives here). Analysed packs are generated on the user's
# machine from the NISAR granules they drop in DATA/ -- they are never shipped in the repo.
# GEOSAR_DATA_STORE (env var or services/api/.env) points the server at another pack folder,
# e.g. on a bigger drive:  GEOSAR_DATA_STORE=D:/geosar_packs
API_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = API_ROOT.parent.parent
ENV_FILES = (str(API_ROOT / ".env"), str(REPO_ROOT / ".env"))


def _dotenv_value(name: str) -> str:
    """Tiny .env reader so DATA_STORE can honour the file at import time."""
    for f in ENV_FILES:
        try:
            for line in Path(f).read_text(encoding="utf-8").splitlines():
                key, sep, val = line.partition("=")
                if sep and key.strip() == name:
                    val = val.split(" #")[0].strip().strip('"').strip("'")
                    if val:
                        return val
        except OSError:
            continue
    return ""


DATA_STORE = Path(
    os.environ.get("GEOSAR_DATA_STORE") or _dotenv_value("GEOSAR_DATA_STORE") or API_ROOT / "data_store"
).expanduser()

DEFAULT_LLM_API_BASE = "https://api.openai.com/v1"
DEFAULT_LLM_MODEL = "gpt-4o-mini"  # cheap + fast + good enough for 3-4 sentence narration


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILES, extra="ignore")

    # NASA Earthdata live connector (blank -> cached CMR fallback)
    earthdata_token: str = ""

    # CORS: "*" for demo, or comma-separated origins
    cors_origins: str = "*"

    # Optional LLM narrator. Only the key is needed: blank key -> deterministic templates only.
    # Base URL / model default to OpenAI (gpt-4o-mini); override for any
    # other OpenAI-style provider (Groq, OpenRouter, ...).
    llm_api_key: str = ""
    llm_api_base: str = ""
    # Tried in order when the primary model is out of quota / overloaded (each model has its own rate limit / quota).
    llm_fallback_models: str = "gpt-4.1-mini"
    llm_model: str = ""

    # LLM narration runs AFTER the instant deterministic card is shown (non-blocking), so it may take
    # longer than the 3.5s used for blocking calls. gpt-4o-mini answers in ~1-3s.
    llm_timeout_seconds: float = 15.0

    # Strict timeout on every external call (SRS §7.2)
    external_timeout_seconds: float = 3.5

    # CMR collection short_name(s), comma-separated. ASF keeps the maturity levels in separate
    # collections: NISAR_L2_GCOV_PROVISIONAL_V1 (PROVISIONAL) and NISAR_L2_GCOV_V1 (VALIDATED).
    nisar_cmr_short_name: str = "NISAR_L2_GCOV_PROVISIONAL_V1,NISAR_L2_GCOV_V1"

    # PROVISIONAL -> VALIDATED transition (21-23 Oct 2026, SRS §3.2); dates >= this are VALIDATED
    # when the catalogue entry does not state the maturity explicitly.
    validated_from: str = "2026-10-23"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_base_url(self) -> str:
        return (self.llm_api_base or DEFAULT_LLM_API_BASE).rstrip("/")

    @property
    def llm_model_name(self) -> str:
        return self.llm_model or DEFAULT_LLM_MODEL

    @property
    def llm_fallback_model_list(self) -> list[str]:
        return [m.strip() for m in self.llm_fallback_models.split(",") if m.strip()]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key.strip())

    @property
    def earthdata_enabled(self) -> bool:
        return bool(self.earthdata_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()
