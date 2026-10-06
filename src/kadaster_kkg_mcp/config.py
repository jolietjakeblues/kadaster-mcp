"""Configuratie voor de kadaster-kkg-mcp server.

Standaardwaarden komen uit de spec (data/kkg_spec.json ->
endpoint / aanbevolen_instellingen) en kunnen per omgeving worden
overschreven via environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_ENDPOINT = "https://api.labs.kadaster.nl/datasets/kadaster/kkg/sparql"


@dataclass(frozen=True)
class Settings:
    sparql_endpoint: str = os.environ.get("KKG_SPARQL_ENDPOINT", DEFAULT_ENDPOINT)
    timeout_seconds: float = float(os.environ.get("KKG_TIMEOUT_SECONDS", "60"))
    sleep_between_requests_seconds: float = float(
        os.environ.get("KKG_SLEEP_SECONDS", "0.3")
    )
    max_retries: int = int(os.environ.get("KKG_MAX_RETRIES", "4"))
    retry_backoff_seconds: float = float(os.environ.get("KKG_RETRY_BACKOFF_SECONDS", "2.0"))
    default_limit: int = int(os.environ.get("KKG_DEFAULT_LIMIT", "20"))
    max_limit: int = int(os.environ.get("KKG_MAX_LIMIT", "500"))
    user_agent: str = os.environ.get(
        "KKG_USER_AGENT", "kadaster-kkg-mcp/0.1 (+https://github.com/jolietjakeblues/kadaster-mcp)"
    )


settings = Settings()
