"""MCP-server voor de Kadaster Knowledge Graph (KKG).

Zelfde architectuur als rce-cho-mcp: een driestaps-workflow
(plan_question -> build_query -> query_sparql / query_sparql_json),
aangevuld met ontology-verkenning en validatie tegen bekende valkuilen.

Starten (stdio transport, voor Claude Desktop / Claude Code):
    python -m kadaster_kkg_mcp.server
of via het geinstalleerde console-script:
    kadaster-kkg-mcp
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from . import ontology, query_builder
from .geo import RdBoundsError, WktParseError
from .geo import classify_proximity as _classify_proximity
from .geo import convert_rd_to_wgs84 as _convert_rd_to_wgs84
from .geo import convert_wgs84_to_rd as _convert_wgs84_to_rd
from .geo import haversine_distance_meters as _haversine_distance_meters
from .geo import parse_wkt_point as _parse_wkt_point
from .planner import plan_question as _plan_question
from .prompts import WORKFLOW_INSTRUCTIONS
from .query_builder import QueryBuildError
from .sparql_client import SparqlClient, SparqlClientError, format_bindings_as_table
from .spec_data import endpoint_info, recommended_settings, sample_results
from .spec_data import datatype_warnings as _datatype_warnings
from .spec_data import known_pitfalls as _known_pitfalls
from .spec_data import pagination_info as _pagination_info
from .spec_data import perceel_geschiedenis_info as _perceel_geschiedenis_info
from .validator import validate_query as _validate_query

mcp = FastMCP("kadaster-kkg-mcp", instructions=WORKFLOW_INSTRUCTIONS)
_client = SparqlClient()


@mcp.tool()
def ping() -> dict[str, Any]:
    """Health-check tegen het KKG SPARQL-endpoint (ASK {?s ?p ?o}).

    Let op: de domeinroot van api.labs.kadaster.nl geeft bewust een 404 --
    gebruik altijd deze tool i.p.v. de root te benaderen.
    """
    return _client.ping()


@mcp.tool()
def endpoint_status() -> dict[str, Any]:
    """Geeft metadata over het geconfigureerde KKG-endpoint en de aanbevolen
    request-instellingen (timeout, retries, rate-limiting) uit de spec."""
    return {"endpoint": endpoint_info(), "aanbevolen_instellingen": recommended_settings()}


@mcp.tool()
def list_namespaces() -> dict[str, str]:
    """Geeft alle bevestigde namespace-prefixes van de KKG (imxgeo, ext, bag, bgt, ...)."""
    return ontology.list_namespaces()


@mcp.tool()
def list_confirmed_classes() -> list[dict[str, Any]]:
    """Geeft een totaaloverzicht van classes die tegen het live KKG-endpoint
    bevestigd zijn, inclusief geschatte aantallen instances (bv. imxgeo:Perceel,
    imxgeo:Adres, imxgeo:Gebouw). Start hier voor een overzicht; gebruik
    ontology_search() als je een specifieke class/property op trefwoord zoekt,
    of describe_class() zodra je de class-naam al kent."""
    return ontology.list_confirmed_classes()


@mcp.tool()
def describe_class(class_name: str) -> dict[str, Any]:
    """Beschrijft een bevestigde class: geschat aantal instances en bekende properties.

    Gebruik dit zodra je de class-naam kent; gebruik ontology_search() als je
    nog op trefwoord moet zoeken, of list_confirmed_classes() voor een
    totaaloverzicht.

    Args:
        class_name: class-naam met of zonder prefix, bv. 'imxgeo:Perceel' of 'Perceel'.
    """
    return ontology.describe_class(class_name)


@mcp.tool()
def ontology_search(keyword: str) -> dict[str, Any]:
    """Doorzoekt bevestigde classes, properties en namespaces op een trefwoord.

    Gebruik dit voordat je een SPARQL-query schrijft om te bepalen welke
    class/property-namen daadwerkelijk bestaan in de KKG -- vooral handig als
    je de exacte naam nog niet kent. Ken je de naam al, gebruik dan
    describe_class() direct; wil je een totaaloverzicht, gebruik
    list_confirmed_classes().
    """
    return ontology.ontology_search(keyword)


@mcp.tool()
def known_pitfalls() -> list[dict[str, Any]]:
    """Geeft de bekende valkuilen bij het bevragen van het KKG-endpoint,
    zoals timeouts bij brede FILTER(CONTAINS(...))-scans.

    Let op: dit is achtergrondinformatie op queryconstructieniveau. De
    meeste van deze valkuilen worden al automatisch gemeld door
    validate_query(); sommige (zoals GET vs POST bij grote VALUES-clauses)
    zijn al intern afgevangen door query_sparql() zelf en vragen geen actie
    van jou als tool-gebruiker.
    """
    return _known_pitfalls()


@mcp.tool()
def sample_results_reference() -> dict[str, Any]:
    """Geeft voorbeeldresultaten en URI-patronen (perceel/beperking) ter referentie,
    zoals eerder daadwerkelijk opgehaald uit het KKG-endpoint.

    Gebruik dit om te controleren of een resource_uri het verwachte patroon
    heeft (https://data.kkg.kadaster.nl/id/perceel/{identificatie}/{versie})
    voordat je 'm doorgeeft aan get_coordinates(), of om te zien welke velden
    een typische beperking-op-perceel-resultaat bevat.
    """
    return sample_results()


@mcp.tool()
def plan_question(question: str) -> dict[str, Any]:
    """Stap 1 van de workflow: zet een natuurlijke-taalvraag om in een queryplan.

    Herkent bekende vraagpatronen (adres->perceel, kadastrale aanduiding->perceel,
    beperkingen op een perceel, class-overzicht), haalt parameters uit de vraag
    (postcode, huisnummer, sectie, perceelnummer, gemeente, perceel-URI) en
    geeft aan welke template en parameters bij build_query gebruikt moeten worden.
    """
    return _plan_question(question)


@mcp.tool()
def build_query(template_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Stap 2 van de workflow: bouwt een concrete SPARQL-query uit een bekende template.

    Beschikbare templates: adres_naar_perceel (postcode, huisnummer[, limit]),
    kadastrale_aanduiding_naar_perceel (sectie, perceelnummer, gemeente[, limit]),
    beperking_op_perceel (perceel_uri[, limit]), classes_met_aantallen ([limit]).

    Dit is de standaard template-workflow (stap 2 na plan_question). Voor
    handgeschreven queries die potentieel meer dan 10.000 resultaten
    opleveren, gebruik in plaats daarvan build_paginated_query() -- dat is
    een aparte keyset-paginering-bouwer, geen onderdeel van deze workflow.

    Args:
        template_name: naam van de template (zie plan_question voor herkenning).
        params: parameters voor de template, bv. {"postcode": "1234AB", "huisnummer": 10}.
            Let op bij kadastrale_aanduiding_naar_perceel: sectie is niet per
            se één letter (bv. "A"), sommige gemeenten gebruiken twee letters
            (bv. "AD").
    """
    try:
        return query_builder.build_query(template_name, params)
    except QueryBuildError as exc:
        return {"error": str(exc)}


@mcp.tool()
def validate_query(sparql: str) -> dict[str, Any]:
    """Valideert een SPARQL-query syntactisch (zonder uit te voeren) en waarschuwt
    voor bekende valkuilen: brede CONTAINS-scans (timeout-risico), ontbrekende LIMIT,
    LIMIT+OFFSET > 10.000 (Virtuoso-limiet), ASK- vs SELECT-resultaatvorm, gebruik
    van imxgeo:bevindtZichOpPerceel (nog niet los geverifieerd) en gebruik van
    imxgeo:naam zonder de vereiste class-restrictie ('a imxgeo:Gemeentegebied').
    """
    return _validate_query(sparql).to_dict()


@mcp.tool()
def query_sparql(sparql: str, max_rows: int = 200) -> str:
    """Stap 3 van de workflow: voert een SPARQL-query uit tegen het KKG-endpoint
    en geeft het resultaat als leesbare tabel terug (of 'ASK-resultaat: true/false').

    Voer altijd eerst validate_query uit, tenzij het een simpele ASK-check is:
    validate_query is gratis en vangt bekende faalmodi (Virtuoso's
    OFFSET-limiet, CONTAINS-scan-timeout) af voordat ze optreden. Bij
    ASK-queries wordt het boolean-resultaat teruggegeven; SELECT-resultaten
    worden als tabel getoond.
    """
    try:
        result = _client.query(sparql)
    except SparqlClientError as exc:
        return f"Fout bij uitvoeren van de query: {exc}"
    return format_bindings_as_table(result, max_rows=max_rows)


@mcp.tool()
def query_sparql_json(sparql: str) -> dict[str, Any]:
    """Zelfde als query_sparql, maar geeft het ruwe SPARQL-JSON-resultaat terug
    (voor programmatische verwerking / batch-scripts). SELECT-resultaten hebben
    de vorm {head, results.bindings}; ASK-resultaten hebben {head, boolean}.

    Voer ook hier altijd eerst validate_query uit, tenzij het een simpele
    ASK-check is.
    """
    try:
        result = _client.query(sparql)
    except SparqlClientError as exc:
        return {"error": str(exc)}
    return result.raw


@mcp.tool()
def convert_rd_to_wgs84(x: float, y: float) -> dict[str, Any]:
    """Converteert een RD-coordinaat (EPSG:28992, gebruikt in KKG-geometrieen)
    naar WGS84 lon/lat, bv. voor visualisatie op een kaart."""
    try:
        return _convert_rd_to_wgs84(x, y)
    except RdBoundsError as exc:
        return {"error": str(exc)}


@mcp.tool()
def convert_wgs84_to_rd(lon: float, lat: float) -> dict[str, Any]:
    """Converteert WGS84 lon/lat naar een RD-coordinaat (EPSG:28992)."""
    return _convert_wgs84_to_rd(lon, lat)


@mcp.tool()
def build_paginated_query(
    select_vars: str,
    where_clause: str,
    order_var: str,
    cursor: str | None = None,
    limit: int = 5000,
) -> dict[str, Any]:
    """Bouwt een SELECT met keyset-paginering (omzeilt Virtuoso's harde limiet van
    LIMIT+OFFSET > 10.000). Sorteert op STR(order_var) i.p.v. de IRI zelf.

    Geen onderdeel van de plan_question/build_query-templateworkflow (stap 2)
    -- gebruik dit alleen voor een zelfgeschreven WHERE-clause die potentieel
    meer dan 10.000 resultaten oplevert.

    Roep dit herhaald aan: geef bij de eerste pagina geen cursor mee, en gebruik
    daarna de laatst geziene waarde van order_var uit de vorige pagina als cursor.

    Args:
        select_vars: bv. '?perceel'.
        where_clause: de WHERE-body zonder buitenste accolades, bv.
            '?beperking imxgeo:isBeperkingOpPerceel ?perceel ; imxgeo:grondslagcode "EWE" .'.
        order_var: variabele om op te pagineren, bv. '?perceel' (met vraagteken).
        cursor: laatst geziene waarde van order_var uit de vorige pagina, of None voor pagina 1.
    """
    try:
        sparql = query_builder.build_paginated_query(select_vars, where_clause, order_var, cursor, limit)
    except QueryBuildError as exc:
        return {"error": str(exc)}
    return {"sparql": sparql}


@mcp.tool()
def get_coordinates(resource_uri: str) -> dict[str, Any]:
    """Haalt het WGS84-punt (lon/lat) op van een perceel/adres via
    ext:plaatscoordinaten -> geosparql:asWKT en parseert de WKT-string.
    """
    try:
        sparql = query_builder.build_resource_coordinaten(resource_uri)
    except QueryBuildError as exc:
        return {"error": str(exc)}
    try:
        result = _client.query(sparql)
    except SparqlClientError as exc:
        return {"error": str(exc)}
    bindings = result.bindings
    if not bindings:
        return {"error": f"Geen coordinaten gevonden voor {resource_uri}."}
    wkt = bindings[0]["wkt"]["value"]
    try:
        return _parse_wkt_point(wkt)
    except WktParseError as exc:
        return {"error": str(exc)}


@mcp.tool()
def compare_locations(lon1: float, lat1: float, lon2: float, lat2: float) -> dict[str, Any]:
    """Vergelijkt twee WGS84-punten op afstand en classificeert die volgens de
    perceel-geschiedenis-workaround (KKG kent geen expliciete opvolgingsrelatie
    tussen percelen -- zie perceel_geschiedenis_workaround): <50m vrijwel zeker
    hetzelfde kavel/complex, 50m-1km twijfelgeval, >1km vrijwel zeker een fout
    in de bron-registratie.
    """
    meters = _haversine_distance_meters(lon1, lat1, lon2, lat2)
    return {"afstand_meters": round(meters, 1), "classificatie": _classify_proximity(meters)}


@mcp.tool()
def datatype_warnings() -> list[dict[str, Any]]:
    """Bekende datatype-verschillen tussen KKG en RCE voor semantisch vergelijkbare
    velden (bv. ext:perceelnummer is xsd:integer in KKG, ongetypeerd string in RCE) --
    belangrijk bij het bouwen van cross-endpoint vergelijkingen."""
    return _datatype_warnings()


@mcp.tool()
def pagination_help() -> dict[str, Any]:
    """Uitleg van de Virtuoso OFFSET-limiet (LIMIT+OFFSET > 10.000 faalt) en de
    keyset-paginering-oplossing. Gebruik build_paginated_query om dit patroon
    automatisch toe te passen."""
    return _pagination_info()


@mcp.tool()
def perceel_geschiedenis_workaround() -> dict[str, Any]:
    """Documenteert dat KKG geen expliciete opvolgingsrelatie tussen vervallen/
    hernummerde percelen kent, en de geometrische-proximiteit-workaround
    (zie get_coordinates + compare_locations) om een oude aanduiding toch aan
    een huidig perceel te koppelen."""
    return _perceel_geschiedenis_info()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
