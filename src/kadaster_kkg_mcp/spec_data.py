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
#
# imxgeo:naam (sinds 2026-07-05) en imxgeo:bevindtZichOpPerceel (sinds
# 2026-10-30) zijn allebei inmiddels bevestigd en staan daarom niet meer in
# deze lijst -- zie CLASS_RESTRICTED_PREDICATES voor de voorwaarde waaronder
# de bevestiging van imxgeo:naam geldt. Deze dict is bewust leeg gelaten
# i.p.v. verwijderd: toekomstige nieuwe/onbevestigde predicaten horen hier.
UNVERIFIED_PREDICATES: dict[str, str] = {}

# Predicaten die alleen bevestigd zijn op een specifieke class, en dus een
# class-restrictie in de query vereisen om betrouwbaar te zijn.
CLASS_RESTRICTED_PREDICATES = {
    "imxgeo:naam": {
        "vereiste_class": "imxgeo:Gemeentegebied",
        "toelichting": (
            "imxgeo:naam is bevestigd als de leesbare gemeentenaam op imxgeo:Gemeentegebied. "
            "Een perceel ligt via imxgeo:ligtInRegistratieveRuimte ook in imxgeo:Buurt en "
            "imxgeo:Woonplaats -- zonder de restrictie '?plaats a imxgeo:Gemeentegebied' kan "
            "de query de verkeerde 'plaats' (buurt- of woonplaatsnaam i.p.v. gemeentenaam) opleveren."
        ),
    },
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


def datatype_warnings() -> list[dict[str, Any]]:
    return list(load_spec()["datatype_waarschuwingen"])


def pagination_info() -> dict[str, Any]:
    return dict(load_spec()["paginering"])


def perceel_geschiedenis_info() -> dict[str, Any]:
    return dict(load_spec()["geen_perceel_geschiedenis"])


def prefix_header(prefixes: list[str] | None = None) -> str:
    """Bouwt PREFIX-regels voor gebruik bovenaan een SPARQL-query."""
    ns = namespaces()
    keys = prefixes if prefixes is not None else list(ns.keys())
    return "\n".join(f"PREFIX {p}: <{ns[p]}>" for p in keys if p in ns)
