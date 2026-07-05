"""Bouwt concrete SPARQL-queries uit de bevestigde templates in de spec.

Elke template is een geparametriseerde versie van een 'werkende_voorbeeldquery'
uit data/kkg_spec.json. De originele voorbeeldquery (met status: bevestigd/
nog te testen) blijft opvraagbaar via spec_data.example_query_by_name voor
referentie en documentatie.
"""

from __future__ import annotations

import inspect
import re
from typing import Any, Callable

from .spec_data import UNVERIFIED_PREDICATES, example_query_by_name, prefix_header

_POSTCODE_RE = re.compile(r"^\d{4}\s?[A-Za-z]{2}$")


class QueryBuildError(ValueError):
    pass


def _validate_postcode(postcode: str) -> str:
    postcode = postcode.strip().upper().replace(" ", "")
    if not _POSTCODE_RE.match(postcode):
        raise QueryBuildError(f"'{postcode}' is geen geldige NL-postcode (verwacht bv. '1234AB').")
    return postcode


def _validate_int(value: Any, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise QueryBuildError(f"'{field_name}' moet een geheel getal zijn, kreeg: {value!r}") from exc


def _as_uri(value: str) -> str:
    value = value.strip()
    if value.startswith("<") and value.endswith(">"):
        return value
    if value.startswith("http://") or value.startswith("https://"):
        return f"<{value}>"
    raise QueryBuildError(f"'{value}' ziet er niet uit als een geldige URI.")


def build_adres_naar_perceel(postcode: str, huisnummer: Any, limit: int = 5) -> str:
    postcode = _validate_postcode(postcode)
    huisnummer = _validate_int(huisnummer, "huisnummer")
    limit = _validate_int(limit, "limit")
    return (
        f"{prefix_header(['imxgeo'])}\n"
        "SELECT ?per ?sectie ?perceelnummer WHERE {\n"
        f'  ?adres a imxgeo:Adres ;\n'
        f'    imxgeo:postcode "{postcode}" ;\n'
        f"    imxgeo:huisnummer {huisnummer} ;\n"
        "    imxgeo:isAdresVanGebouw ?geb .\n"
        "  ?geb imxgeo:bevindtZichOpPerceel ?per .\n"
        "  ?per <https://modellen.kkg.kadaster.nl/def/imxgeo-ext#sectie> ?sectie ;\n"
        "       <https://modellen.kkg.kadaster.nl/def/imxgeo-ext#perceelnummer> ?perceelnummer .\n"
        f"}} LIMIT {limit}"
    )


def build_kadastrale_aanduiding_naar_perceel(
    sectie: str, perceelnummer: Any, gemeente: str, limit: int = 5
) -> str:
    """imxgeo:naam is alleen bevestigd op imxgeo:Gemeentegebied (2026-07-05); een
    perceel ligt via imxgeo:ligtInRegistratieveRuimte ook in imxgeo:Buurt en
    imxgeo:Woonplaats, dus de class-restrictie hieronder is verplicht om de
    gemeentenaam te pakken i.p.v. een buurt-/woonplaatsnaam."""
    sectie = sectie.strip().upper().replace('"', "")
    perceelnummer = _validate_int(perceelnummer, "perceelnummer")
    gemeente = gemeente.strip().replace('"', "")
    limit = _validate_int(limit, "limit")
    return (
        f"{prefix_header(['imxgeo', 'ext'])}\n"
        "SELECT ?per WHERE {\n"
        "  ?per a imxgeo:Perceel ;\n"
        f'    ext:sectie "{sectie}" ;\n'
        f"    ext:perceelnummer {perceelnummer} ;\n"
        "    imxgeo:ligtInRegistratieveRuimte ?plaats .\n"
        "  ?plaats a imxgeo:Gemeentegebied ;\n"
        "    imxgeo:naam ?plaatsnaam .\n"
        f'  FILTER(CONTAINS(LCASE(?plaatsnaam), LCASE("{gemeente}")))\n'
        f"}} LIMIT {limit}"
    )


def build_beperking_op_perceel(perceel_uri: str, limit: int = 5) -> str:
    uri = _as_uri(perceel_uri)
    limit = _validate_int(limit, "limit")
    return (
        f"{prefix_header(['imxgeo'])}\n"
        "SELECT ?grondslagcode ?grondslag WHERE {\n"
        f"  ?beperking imxgeo:isBeperkingOpPerceel {uri} ;\n"
        "    imxgeo:grondslagcode ?grondslagcode ;\n"
        "    imxgeo:grondslag ?grondslag .\n"
        f"}} LIMIT {limit}"
    )


def build_classes_met_aantallen(limit: int = 20) -> str:
    limit = _validate_int(limit, "limit")
    return (
        "SELECT DISTINCT ?type (COUNT(?s) as ?cnt) WHERE {\n"
        "  ?s a ?type .\n"
        f"}} GROUP BY ?type ORDER BY DESC(?cnt) LIMIT {limit}"
    )


def build_resource_coordinaten(resource_uri: str) -> str:
    """Haalt het WGS84-punt (WKT) op van een resource via ext:plaatscoordinaten.
    Bevestigd werkend 2026-07-05: geosparql:asWKT geeft 'POINT(lon lat)'."""
    uri = _as_uri(resource_uri)
    return (
        f"{prefix_header(['ext', 'geosparql'])}\n"
        "SELECT ?wkt WHERE {\n"
        f"  {uri} ext:plaatscoordinaten ?geom .\n"
        "  ?geom geosparql:asWKT ?wkt .\n"
        "} LIMIT 1"
    )


_BUILDERS: dict[str, Callable[..., str]] = {
    "adres_naar_perceel": build_adres_naar_perceel,
    "kadastrale_aanduiding_naar_perceel": build_kadastrale_aanduiding_naar_perceel,
    "beperking_op_perceel": build_beperking_op_perceel,
    "classes_met_aantallen": build_classes_met_aantallen,
    "resource_coordinaten": build_resource_coordinaten,
}

_TEMPLATE_UNVERIFIED_PREDICATES: dict[str, list[str]] = {
    "adres_naar_perceel": ["imxgeo:bevindtZichOpPerceel"],
    "kadastrale_aanduiding_naar_perceel": [],
    "beperking_op_perceel": [],
    "classes_met_aantallen": [],
    "resource_coordinaten": [],
}


def build_paginated_query(
    select_vars: str,
    where_clause: str,
    order_var: str,
    cursor: str | None = None,
    limit: int = 5000,
    prefixes: list[str] | None = None,
) -> str:
    """Bouwt een SELECT met keyset-paginering, om Virtuoso's OFFSET-limiet
    (LIMIT+OFFSET > 10.000 faalt hard) te omzeilen. Sorteert op STR(order_var)
    i.p.v. de IRI zelf -- IRI-vergelijking met '>' bleek geen consistente
    lexicografische volgorde te geven (overlappende pagina's).

    Args:
        select_vars: bv. '?perceel'.
        where_clause: de WHERE-body zonder buitenste accolades, bv.
            '?beperking imxgeo:isBeperkingOpPerceel ?perceel ; imxgeo:grondslagcode "EWE" .'
        order_var: variabele om op te pagineren, bv. '?perceel' (met vraagteken).
        cursor: laatst geziene waarde van order_var uit de vorige pagina (None voor pagina 1).
    """
    limit = _validate_int(limit, "limit")
    if not order_var.startswith("?"):
        raise QueryBuildError(f"order_var moet met '?' beginnen, kreeg: {order_var!r}")

    cursor_filter = ""
    if cursor:
        cursor_escaped = cursor.replace("\\", "\\\\").replace('"', '\\"')
        cursor_filter = f'  FILTER(STR({order_var}) > "{cursor_escaped}")\n'

    header = prefix_header(prefixes) if prefixes else prefix_header()
    return (
        f"{header}\n"
        f"SELECT {select_vars} WHERE {{\n"
        f"  {where_clause}\n"
        f"{cursor_filter}"
        f"}} ORDER BY STR({order_var}) LIMIT {limit}"
    )


def available_templates() -> list[str]:
    return list(_BUILDERS.keys())


def build_query(template_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Bouwt een query op basis van een bekende template + parameters.

    Retourneert de query plus metadata: welke voorbeeldquery hij vervangt,
    de bevestigingsstatus daarvan uit de spec, en waarschuwingen over
    predicaten die nog niet los geverifieerd zijn.
    """
    params = params or {}
    builder = _BUILDERS.get(template_name)
    if builder is None:
        raise QueryBuildError(
            f"Onbekende template '{template_name}'. Beschikbaar: {', '.join(available_templates())}."
        )

    # plan_question kan extra, voor deze template irrelevante parameters
    # meegeven (bv. zowel perceel_uri als resource_uri) -- filter op wat de
    # builder daadwerkelijk accepteert.
    accepted = set(inspect.signature(builder).parameters)
    filtered_params = {k: v for k, v in params.items() if k in accepted}

    try:
        sparql = builder(**filtered_params)
    except TypeError as exc:
        raise QueryBuildError(f"Ontbrekende of onjuiste parameters voor '{template_name}': {exc}") from exc
    example = example_query_by_name(template_name)
    warnings = [
        f"Predicaat '{p}' is nog niet los tegen het live endpoint geverifieerd: "
        f"{UNVERIFIED_PREDICATES.get(p, '')}"
        for p in _TEMPLATE_UNVERIFIED_PREDICATES.get(template_name, [])
    ]

    return {
        "template": template_name,
        "sparql": sparql,
        "gebaseerd_op_voorbeeldquery_status": example.get("status") if example else None,
        "waarschuwingen": warnings,
    }
