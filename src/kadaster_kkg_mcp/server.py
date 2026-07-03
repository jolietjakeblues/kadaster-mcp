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
from .geo import RdBoundsError
from .geo import convert_rd_to_wgs84 as _convert_rd_to_wgs84
from .geo import convert_wgs84_to_rd as _convert_wgs84_to_rd
from .planner import plan_question as _plan_question
from .query_builder import QueryBuildError
from .sparql_client import SparqlClient, SparqlClientError, format_bindings_as_table
from .spec_data import endpoint_info, recommended_settings, sample_results
from .spec_data import known_pitfalls as _known_pitfalls
from .validator import validate_query as _validate_query

mcp = FastMCP("kadaster-kkg-mcp")
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
    """Geeft de lijst van classes die tegen het live KKG-endpoint bevestigd zijn,
    inclusief geschatte aantallen instances (bv. imxgeo:Perceel, imxgeo:Adres, imxgeo:Gebouw)."""
    return ontology.list_confirmed_classes()


@mcp.tool()
def describe_class(class_name: str) -> dict[str, Any]:
    """Beschrijft een bevestigde class: geschat aantal instances en bekende properties.

    Args:
        class_name: class-naam met of zonder prefix, bv. 'imxgeo:Perceel' of 'Perceel'.
    """
    return ontology.describe_class(class_name)


@mcp.tool()
def ontology_search(keyword: str) -> dict[str, Any]:
    """Doorzoekt bevestigde classes, properties en namespaces op een trefwoord.

    Gebruik dit voordat je een SPARQL-query schrijft om te bepalen welke
    class/property-namen daadwerkelijk bestaan in de KKG.
    """
    return ontology.ontology_search(keyword)


@mcp.tool()
def known_pitfalls() -> list[dict[str, Any]]:
    """Geeft de bekende valkuilen bij het bevragen van het KKG-endpoint,
    zoals timeouts bij brede FILTER(CONTAINS(...))-scans."""
    return _known_pitfalls()


@mcp.tool()
def sample_results_reference() -> dict[str, Any]:
    """Geeft voorbeeldresultaten en URI-patronen (perceel/beperking) ter referentie,
    zoals eerder daadwerkelijk opgehaald uit het KKG-endpoint."""
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

    Args:
        template_name: naam van de template (zie plan_question voor herkenning).
        params: parameters voor de template, bv. {"postcode": "1234AB", "huisnummer": 10}.
    """
    try:
        return query_builder.build_query(template_name, params)
    except QueryBuildError as exc:
        return {"error": str(exc)}


@mcp.tool()
def validate_query(sparql: str) -> dict[str, Any]:
    """Valideert een SPARQL-query syntactisch (zonder uit te voeren) en waarschuwt
    voor bekende valkuilen: brede CONTAINS-scans (timeout-risico), ontbrekende LIMIT,
    ASK- vs SELECT-resultaatvorm, en gebruik van nog niet los geverifieerde predicaten
    (imxgeo:bevindtZichOpPerceel, imxgeo:naam op registratieve-ruimte).
    """
    return _validate_query(sparql).to_dict()


@mcp.tool()
def query_sparql(sparql: str, max_rows: int = 200) -> str:
    """Stap 3 van de workflow: voert een SPARQL-query uit tegen het KKG-endpoint
    en geeft het resultaat als leesbare tabel terug (of 'ASK-resultaat: true/false').

    Voer bij twijfel eerst validate_query uit. Bij ASK-queries wordt het
    boolean-resultaat teruggegeven; SELECT-resultaten worden als tabel getoond.
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


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
