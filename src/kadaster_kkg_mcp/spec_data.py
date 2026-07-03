"""Laadt de bevestigde KKG-spec (data/kkg_spec.json) als in-memory kennisbron.

Dit bestand is de vertaling van het door de gebruiker aangeleverde
onderzoeksdocument (kadasterkkgmcpspec.json) naar bruikbare Python-structuren
voor de MCP-tools. Het JSON-bestand blijft de bron van waarheid; wijzig bij
voorkeur data/kkg_spec.json en niet de structuren hieronder.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_SPEC_PATH = Path(__file__).parent / "data" / "kkg_spec.json"

# Predicaten die het onderzoek expliciet als "nog niet los geverifieerd" markeert.
# Zie mcp_build_meta in kkg_spec.json: ook Claude Code kon dit niet alsnog
# bevestigen omdat het sandbox-netwerkbeleid uitgaand verkeer naar
# api.labs.kadaster.nl blokkeerde.
UNVERIFIED_PREDICATES = {
    "imxgeo:bevindtZichOpPerceel": (
        "Gebruikt in template 'adres_naar_perceel' (gebouw -> perceel). "
        "Nog niet los getest tegen het live endpoint."
    ),
    "imxgeo:naam": (
        "Gebruikt in template 'kadastrale_aanduiding_naar_perceel' op de "
        "registratieve-ruimte (plaats). Nog niet los getest tegen het live endpoint."
    ),
}


@lru_cache(maxsize=1)
def load_spec() -> dict[str, Any]:
    with _SPEC_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def namespaces() -> dict[str, str]:
    return dict(load_spec()["namespaces_gebruikt"])


def confirmed_classes() -> list[dict[str, Any]]:
    return list(load_spec()["bevestigde_classes"])


def confirmed_properties() -> dict[str, Any]:
    return dict(load_spec()["bevestigde_properties"])


def example_queries() -> list[dict[str, Any]]:
    return list(load_spec()["werkende_voorbeeldqueries"])


def example_query_by_name(name: str) -> dict[str, Any] | None:
    for q in example_queries():
        if q["naam"] == name:
            return q
    return None


def known_pitfalls() -> list[dict[str, Any]]:
    return list(load_spec()["bekende_valkuilen"])


def recommended_settings() -> dict[str, Any]:
    return dict(load_spec()["aanbevolen_instellingen"])


def endpoint_info() -> dict[str, Any]:
    return dict(load_spec()["endpoint"])


def sample_results() -> dict[str, Any]:
    return dict(load_spec()["voorbeeld_resultaten_ter_referentie"])


def prefix_header(prefixes: list[str] | None = None) -> str:
    """Bouwt PREFIX-regels voor gebruik bovenaan een SPARQL-query."""
    ns = namespaces()
    keys = prefixes if prefixes is not None else list(ns.keys())
    return "\n".join(f"PREFIX {p}: <{ns[p]}>" for p in keys if p in ns)
