"""HTTP-client voor het KKG SPARQL-endpoint.

Volgt de bevestigde aanroepwijze uit de spec: POST met form-data key 'query'
en header Accept: application/sparql-results+json. GET is bewust NIET
gebruikt: bij VALUES-clauses met >~300-500 URI's (querystring >~30-40KB)
geeft GET een HTTP 431 'Request Header Fields Too Large' (bevestigd
2026-07-05); POST is getest tot 3000 URI's/255KB zonder problemen. Retry/
backoff en rate-limiting-instellingen komen uit config.settings (overgenomen
uit het bestaande productiescript build_csv_landelijk.py, zie kkg_spec.json).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from .config import settings


class SparqlClientError(RuntimeError):
    """Fout bij het uitvoeren van een SPARQL-query tegen het KKG-endpoint."""


@dataclass
class SparqlResult:
    raw: dict[str, Any]
    is_ask: bool
    elapsed_seconds: float

    @property
    def boolean(self) -> bool | None:
        return self.raw.get("boolean") if self.is_ask else None

    @property
    def variables(self) -> list[str]:
        return list(self.raw.get("head", {}).get("vars", []))

    @property
    def bindings(self) -> list[dict[str, Any]]:
        return list(self.raw.get("results", {}).get("bindings", []))


class SparqlClient:
    """Kleine, robuuste client voor het KKG-endpoint (GET-only, JSON-resultaten)."""

    def __init__(
        self,
        endpoint: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        retry_backoff: float | None = None,
        sleep_between_requests: float | None = None,
    ) -> None:
        self.endpoint = endpoint or settings.sparql_endpoint
        self.timeout = timeout if timeout is not None else settings.timeout_seconds
        self.max_retries = max_retries if max_retries is not None else settings.max_retries
        self.retry_backoff = (
            retry_backoff if retry_backoff is not None else settings.retry_backoff_seconds
        )
        self.sleep_between_requests = (
            sleep_between_requests
            if sleep_between_requests is not None
            else settings.sleep_between_requests_seconds
        )
        self._last_request_ts: float | None = None

    def _throttle(self) -> None:
        if self._last_request_ts is None:
            return
        elapsed = time.monotonic() - self._last_request_ts
        remaining = self.sleep_between_requests - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def query(self, sparql: str) -> SparqlResult:
        """Voert een SPARQL-query (SELECT/ASK/CONSTRUCT/DESCRIBE) uit.

        Retried met exponentiele backoff bij netwerk- of 5xx-fouten;
        4xx-fouten (o.a. syntaxfouten) worden direct doorgegeven.
        """
        is_ask = _looks_like_ask(sparql)
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            self._throttle()
            start = time.monotonic()
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        self.endpoint,
                        data={"query": sparql},
                        headers={
                            "Accept": "application/sparql-results+json",
                            "User-Agent": settings.user_agent,
                        },
                    )
                self._last_request_ts = time.monotonic()
                elapsed = self._last_request_ts - start

                if response.status_code == 400:
                    raise SparqlClientError(
                        f"KKG-endpoint gaf 400 Bad Request (waarschijnlijk syntaxfout in de "
                        f"SPARQL-query): {response.text[:500]}"
                    )
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"server error {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                data = response.json()
                return SparqlResult(raw=data, is_ask=is_ask, elapsed_seconds=elapsed)

            except SparqlClientError:
                raise
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                self._last_request_ts = time.monotonic()
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff * (2**attempt))
                    continue
                break

        raise SparqlClientError(
            f"KKG-endpoint niet bereikbaar na {self.max_retries + 1} pogingen: {last_error}"
        ) from last_error

    def ask(self, sparql: str) -> bool:
        result = self.query(sparql)
        if not result.is_ask:
            raise SparqlClientError("query() gebruikt voor ask() bevat geen ASK-query")
        return bool(result.boolean)

    def ping(self) -> dict[str, Any]:
        """Health-check: ASK {?s ?p ?o} tegen het SPARQL-pad zelf (niet de domeinroot,
        die geeft bewust een 404 -- zie bekende_valkuilen in de spec)."""
        try:
            result = self.query("ASK { ?s ?p ?o }")
            return {
                "ok": True,
                "reachable": True,
                "boolean": result.boolean,
                "elapsed_seconds": round(result.elapsed_seconds, 3),
                "endpoint": self.endpoint,
            }
        except SparqlClientError as exc:
            return {"ok": False, "reachable": False, "error": str(exc), "endpoint": self.endpoint}


def _looks_like_ask(sparql: str) -> bool:
    stripped = _strip_prefixes_and_comments(sparql).lstrip()
    return stripped[:3].upper() == "ASK"


def _strip_prefixes_and_comments(sparql: str) -> str:
    lines = []
    for line in sparql.splitlines():
        s = line.strip()
        if not s or s.upper().startswith("PREFIX") or s.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def format_bindings_as_table(result: SparqlResult, max_rows: int = 200) -> str:
    """Zet een SELECT-resultaat om naar een leesbare Markdown-achtige tabel."""
    if result.is_ask:
        return f"ASK-resultaat: {result.boolean}"

    variables = result.variables
    bindings = result.bindings
    if not variables:
        return "(geen resultaatvariabelen)"
    if not bindings:
        return "(geen resultaten)"

    header = " | ".join(variables)
    sep = " | ".join(["---"] * len(variables))
    rows = []
    for b in bindings[:max_rows]:
        row = []
        for v in variables:
            cell = b.get(v, {})
            value = cell.get("value", "")
            cell_type = cell.get("type", "")
            if cell_type == "uri":
                row.append(f"<{value}>")
            else:
                row.append(value)
        rows.append(" | ".join(row))

    table = "\n".join([header, sep, *rows])
    if len(bindings) > max_rows:
        table += f"\n... ({len(bindings) - max_rows} rijen niet getoond, totaal {len(bindings)})"
    return table
