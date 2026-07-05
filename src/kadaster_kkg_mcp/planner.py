"""plan_question: zet een natuurlijke-taal vraag om in een gestructureerd queryplan.

Dit is bewust een lichtgewicht, keyword-gebaseerde herkenner (geen LLM-call) --
de MCP-tool geeft een plan terug; het taalmodel dat de tool aanroept (Claude)
maakt op basis daarvan de uiteindelijke keuze en vult build_query verder in.
Dit volgt dezelfde driestaps-workflow als rce-cho-mcp: plan_question ->
build_query -> query_sparql.
"""

from __future__ import annotations

import re
from typing import Any

from .query_builder import available_templates
from .spec_data import UNVERIFIED_PREDICATES

_POSTCODE_RE = re.compile(r"\b(\d{4}\s?[A-Za-z]{2})\b")
_HUISNUMMER_RE = re.compile(r"\bhuisnummer\s+(\d+)\b", re.IGNORECASE)
_SECTIE_RE = re.compile(r"\bsectie\s+([A-Za-z])\b", re.IGNORECASE)
_PERCEELNUMMER_RE = re.compile(r"\bperceel(?:nummer)?\s+(\d+)\b", re.IGNORECASE)
_URI_RE = re.compile(r"https?://\S+")

_INTENTS: list[dict[str, Any]] = [
    {
        "template": "beperking_op_perceel",
        "keywords": ["beperking", "grondslag", "bodembescherming", "brk-pb", "last onder"],
        "classes": ["imxgeo:Beperking", "imxgeo:Perceel"],
        "properties": ["imxgeo:isBeperkingOpPerceel", "imxgeo:grondslagcode", "imxgeo:grondslag"],
        "required_params": ["perceel_uri"],
    },
    {
        "template": "adres_naar_perceel",
        "keywords": ["adres", "postcode", "huisnummer", "straat"],
        "classes": ["imxgeo:Adres", "imxgeo:Gebouw", "imxgeo:Perceel"],
        "properties": [
            "imxgeo:postcode",
            "imxgeo:huisnummer",
            "imxgeo:isAdresVanGebouw",
            "imxgeo:bevindtZichOpPerceel",
        ],
        "required_params": ["postcode", "huisnummer"],
    },
    {
        "template": "kadastrale_aanduiding_naar_perceel",
        "keywords": ["sectie", "kadastrale aanduiding", "kadastraal nummer", "gemeente"],
        "classes": ["imxgeo:Perceel"],
        "properties": ["ext:sectie", "ext:perceelnummer", "imxgeo:ligtInRegistratieveRuimte", "imxgeo:naam"],
        "required_params": ["sectie", "perceelnummer", "gemeente"],
    },
    {
        "template": "classes_met_aantallen",
        "keywords": ["hoeveel", "aantal", "overzicht", "welke soorten", "welke classes", "verken"],
        "classes": [],
        "properties": [],
        "required_params": [],
    },
    {
        "template": "resource_coordinaten",
        "keywords": ["coordinaat", "coördinaat", "locatie", "waar ligt", "kaart", "lon", "lat", "wgs84"],
        "classes": ["geosparql:Geometry"],
        "properties": ["ext:plaatscoordinaten", "geosparql:asWKT"],
        "required_params": ["resource_uri"],
    },
]


def _score(question: str, keywords: list[str]) -> int:
    q = question.lower()
    return sum(1 for kw in keywords if kw in q)


def _extract_params(question: str) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if m := _POSTCODE_RE.search(question):
        params["postcode"] = m.group(1).upper().replace(" ", "")
    if m := _HUISNUMMER_RE.search(question):
        params["huisnummer"] = int(m.group(1))
    if m := _SECTIE_RE.search(question):
        params["sectie"] = m.group(1).upper()
    if m := _PERCEELNUMMER_RE.search(question):
        params["perceelnummer"] = int(m.group(1))
    if m := _URI_RE.search(question):
        uri = m.group(0)
        params["perceel_uri"] = uri
        params["resource_uri"] = uri
    return params


def plan_question(question: str) -> dict[str, Any]:
    scored = [(intent, _score(question, intent["keywords"])) for intent in _INTENTS]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    best_intent, best_score = scored[0]

    extracted = _extract_params(question)

    if best_score == 0:
        return {
            "vraag": question,
            "herkend_template": None,
            "toelichting": (
                "Geen bekende template herkend op basis van trefwoorden. Gebruik "
                "ontology_search of describe_class om relevante classes/properties te vinden, "
                "en bouw daarna zelf een SPARQL-query (query_sparql/validate_query), of kies "
                f"handmatig een template uit: {', '.join(available_templates())}."
            ),
            "beschikbare_templates": available_templates(),
            "geextraheerde_parameters": extracted,
        }

    required = best_intent["required_params"]
    missing = [p for p in required if p not in extracted]

    warnings = []
    for prop in best_intent["properties"]:
        if prop in UNVERIFIED_PREDICATES:
            warnings.append(
                f"'{prop}' is nog niet los geverifieerd tegen het live endpoint: "
                f"{UNVERIFIED_PREDICATES[prop]}"
            )

    return {
        "vraag": question,
        "herkend_template": best_intent["template"],
        "relevante_classes": best_intent["classes"],
        "relevante_properties": best_intent["properties"],
        "geextraheerde_parameters": extracted,
        "ontbrekende_parameters": missing,
        "waarschuwingen": warnings,
        "vervolgstap": (
            f"Roep build_query aan met template_name='{best_intent['template']}' en de "
            f"parameters {list(extracted.keys()) or '(nog aan te vullen: ' + ', '.join(missing) + ')'}."
            if not missing
            else f"Vraag de gebruiker om: {', '.join(missing)} voordat build_query wordt aangeroepen."
        ),
    }
