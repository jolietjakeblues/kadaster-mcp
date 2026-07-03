# kadaster-kkg-mcp

MCP-server voor de **Kadaster Knowledge Graph (KKG)** SPARQL-endpoint, gebouwd
naar analogie van `rce-cho-mcp` (RCE CHO linked data). Zelfde driestaps-workflow:

```
plan_question  ->  build_query  ->  query_sparql / query_sparql_json
```

## Status

Deze server is opgezet op basis van `src/kadaster_kkg_mcp/data/kkg_spec.json`,
een onderzoeksdocument met tegen het live KKG-endpoint bevestigde classes,
properties en voorbeeldqueries (sessie 2026-07-03). Twee predicaten zijn in
dat document expliciet als **nog niet los geverifieerd** gemarkeerd:

- `imxgeo:bevindtZichOpPerceel` (gebouw -> perceel)
- `imxgeo:naam` op de registratieve-ruimte (plaats)

Bij het bouwen van deze MCP is geprobeerd dit alsnog te verifieren via curl
tegen `api.labs.kadaster.nl`, maar dat werd geblokkeerd door het
netwerkbeleid van de bouw-sandbox (403 op de CONNECT). Beide predicaten zijn
daarom als `unverified` opgenomen in `spec_data.UNVERIFIED_PREDICATES`:
`plan_question`, `build_query` en `validate_query` geven hier een expliciete
waarschuwing bij wanneer je de templates `adres_naar_perceel` of
`kadastrale_aanduiding_naar_perceel` gebruikt. Draai `scripts/smoke_test.py`
vanaf een omgeving met toegang tot `api.labs.kadaster.nl` om ze alsnog te
bevestigen en werk dan `kkg_spec.json` bij.

## Endpoint

- URL: `https://api.labs.kadaster.nl/datasets/kadaster/kkg/services/kkg/sparql`
- Methode: GET met query-param `query`, header `Accept: application/sparql-results+json`
- De domeinroot geeft bewust een 404 -- gebruik altijd de `ping`-tool i.p.v. de root te benaderen.

## Installatie

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Tests draaien

```bash
pytest
```

Alle tests zijn offline (geen live endpoint nodig). Voor een echte
end-to-end-check tegen het KKG-endpoint: `python scripts/smoke_test.py`.

## Als MCP-server registreren

`.mcp.json` (in de root van dit project) registreert de server al voor
Claude Code / Claude Desktop:

```json
{
  "mcpServers": {
    "kadaster-kkg": {
      "command": "python",
      "args": ["-m", "kadaster_kkg_mcp.server"]
    }
  }
}
```

Of los starten (stdio transport):

```bash
python -m kadaster_kkg_mcp.server
# of, na installatie:
kadaster-kkg-mcp
```

## Configuratie

Alle instellingen zijn te overschrijven via environment variables (zie
`.env.example`): endpoint-URL, timeout, retries, backoff en rate-limiting
tussen requests. Standaardwaarden komen uit het productiescript
`build_csv_landelijk.py` dat als referentie diende voor deze spec.

## Tools

| Tool | Doel |
|---|---|
| `ping` | Health-check (ASK) tegen het endpoint |
| `endpoint_status` | Endpoint-metadata + aanbevolen instellingen |
| `list_namespaces` | Bevestigde prefixes (imxgeo, ext, bag, bgt, ...) |
| `list_confirmed_classes` | Classes met geschatte aantallen (Perceel, Adres, Gebouw, ...) |
| `describe_class` | Properties + telling voor een class |
| `ontology_search` | Zoek classes/properties/namespaces op trefwoord |
| `known_pitfalls` | Bekende valkuilen (o.a. CONTAINS-timeout) |
| `sample_results_reference` | Referentievoorbeelden + URI-patronen |
| `plan_question` | **Stap 1**: NL-vraag -> queryplan |
| `build_query` | **Stap 2**: plan/template -> concrete SPARQL |
| `validate_query` | Syntax + valkuil-check zonder uit te voeren |
| `query_sparql` | **Stap 3**: query uitvoeren, leesbare tabel |
| `query_sparql_json` | Query uitvoeren, ruwe JSON |
| `convert_rd_to_wgs84` | RD (EPSG:28992) -> lon/lat |
| `convert_wgs84_to_rd` | lon/lat -> RD (EPSG:28992) |

### Query-templates (`build_query`)

| Template | Parameters | Status |
|---|---|---|
| `adres_naar_perceel` | `postcode`, `huisnummer`, `limit?` | gebruikt `imxgeo:bevindtZichOpPerceel` (**unverified**) |
| `kadastrale_aanduiding_naar_perceel` | `sectie`, `perceelnummer`, `gemeente`, `limit?` | gebruikt `imxgeo:naam` op registratieve-ruimte (**unverified**) |
| `beperking_op_perceel` | `perceel_uri`, `limit?` | bevestigd werkend |
| `classes_met_aantallen` | `limit?` | bevestigd werkend |

## Architectuur

```
src/kadaster_kkg_mcp/
  server.py         MCP-tools (FastMCP)
  sparql_client.py  HTTP-client: retry/backoff, ASK/SELECT-parsing
  planner.py         plan_question: NL -> queryplan
  query_builder.py   build_query: template + params -> SPARQL
  validator.py        validate_query: syntax + bekende valkuilen
  ontology.py          bevestigde classes/properties/namespaces
  geo.py                RD <-> WGS84 (pyproj)
  config.py             instellingen (env-overrides)
  spec_data.py          laadt data/kkg_spec.json
  data/kkg_spec.json     bronbestand: bevestigde onderzoeksdata
```
