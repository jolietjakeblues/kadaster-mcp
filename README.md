# kadaster-kkg-mcp

MCP-server voor de **Kadaster Knowledge Graph (KKG)** SPARQL-endpoint, gebouwd
naar analogie van `rce-cho-mcp` (RCE CHO linked data). Zelfde driestaps-workflow:

```
plan_question  ->  build_query  ->  query_sparql / query_sparql_json
```

## Status

Deze server is opgezet op basis van `src/kadaster_kkg_mcp/data/kkg_spec.json`,
een onderzoeksdocument met tegen het live KKG-endpoint bevestigde classes,
properties en voorbeeldqueries (laatst bijgewerkt 2026-10-30). Alle eerder
als "nog niet los geverifieerd" gemarkeerde predicaten zijn inmiddels bevestigd:

- `imxgeo:bevindtZichOpPerceel` (gebouw -> perceel): bevestigd 2026-10-30
  via ASK en een steekproef van echte gebouw->perceel-koppelingen tegen het
  live endpoint.
- `imxgeo:naam`: bevestigd 2026-07-05, maar **alleen op `imxgeo:Gemeentegebied`**
  (een perceel ligt via `imxgeo:ligtInRegistratieveRuimte` ook in `imxgeo:Buurt`
  en `imxgeo:Woonplaats`). De query-template en `validate_query` dwingen daarom
  altijd de restrictie `?plaats a imxgeo:Gemeentegebied` af -- zie
  `spec_data.CLASS_RESTRICTED_PREDICATES`.

`spec_data.UNVERIFIED_PREDICATES` is nu leeg, maar blijft als mechanisme
bestaan voor een eventueel toekomstig nog-niet-bevestigd predicaat.

## Endpoint

- URL: `https://api.labs.kadaster.nl/datasets/kadaster/kkg/sparql`
- Methode: **POST** met form-data key `query`, header `Accept: application/sparql-results+json`.
  GET is bewust niet gebruikt: bij grote `VALUES`-clauses (querystring >~30-40KB, >~300-500 URI's)
  geeft GET een HTTP 431 "Request Header Fields Too Large" (bevestigd 2026-07-05).
  POST is getest tot 3000 URI's/255KB zonder problemen.
- De domeinroot geeft bewust een 404 -- gebruik altijd de `ping`-tool i.p.v. de root te benaderen.

## Bekende beperkingen van de graph

- **`ORDER BY` op een class-scan-variabele timet uit**: `ORDER BY ?x` waarbij
  `?x` alleen via `?x a imxgeo:Klasse` gebonden is (geen verdere selectieve
  restrictie) timet uit op grote classes zoals `imxgeo:Perceel` (~8,4 miljoen
  instances) -- bevestigd 2026-10-30, **onafhankelijk van `OPTIONAL`-joins**
  en ook met een op het oog restrictieve `FILTER` erbij (bv. `ext:sectie "A"`,
  dat landelijk nog honderdduizenden percelen omvat). Dit is dus een ander
  patroon dan de `ORDER BY + OPTIONAL`-504 die op het RCE CHO-endpoint is
  gevonden: op KKG is de class-scan zelf al het probleem. `validate_query`
  waarschuwt hiervoor. Gebruik keyset-paginering (`build_paginated_query`)
  of een vaste subject-URI.
- **Geen paginering > 10.000 rijen via OFFSET**: Virtuoso (de triplestore
  achter KKG) weigert `ORDER BY` + `OFFSET` zodra `LIMIT+OFFSET > 10.000`.
  Gebruik keyset-paginering (`build_paginated_query` / `pagination_help`):
  sorteer op `STR(?var)` en filter met `FILTER(STR(?var) > "<cursor>")`
  i.p.v. `OFFSET`.
- **Geen perceel-opvolgingsrelatie**: KKG bevat geen expliciete relatie tussen
  een vervallen/hernummerd perceel en zijn opvolger (o.a. `isVervangenDoor`,
  `opgegaanIn`, `opgevolgdDoor` bestaan niet -- bevestigd via ASK). Workaround:
  geometrische proximiteitscheck via `get_coordinates` + `compare_locations`
  (zie `perceel_geschiedenis_workaround`): <50m vrijwel zeker hetzelfde
  kavel/complex, 50m-1km twijfelgeval, >1km vrijwel zeker een fout in de bron.
- **Datatype-mismatch met RCE**: `ext:perceelnummer` is `xsd:integer` in KKG,
  maar een ongetypeerd string-literal in de vergelijkbare RCE-property. Zie
  `datatype_warnings` voordat je cross-endpoint vergelijkingen bouwt.

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
| `known_pitfalls` | Bekende valkuilen (o.a. CONTAINS-timeout, GET-431, OFFSET-limiet) |
| `sample_results_reference` | Referentievoorbeelden + URI-patronen |
| `datatype_warnings` | Datatype-verschillen KKG vs. RCE (bv. perceelnummer) |
| `pagination_help` | Uitleg Virtuoso OFFSET-limiet + keyset-oplossing |
| `perceel_geschiedenis_workaround` | Uitleg ontbrekende perceel-opvolging + proximiteits-workaround |
| `plan_question` | **Stap 1**: NL-vraag -> queryplan |
| `build_query` | **Stap 2**: plan/template -> concrete SPARQL |
| `build_paginated_query` | Keyset-gepagineerde SELECT bouwen (omzeilt OFFSET-limiet) |
| `validate_query` | Syntax + valkuil-check zonder uit te voeren |
| `query_sparql` | **Stap 3**: query uitvoeren, leesbare tabel |
| `query_sparql_json` | Query uitvoeren, ruwe JSON |
| `get_coordinates` | WGS84 lon/lat ophalen voor een resource (via WKT) |
| `compare_locations` | Afstand + classificatie tussen twee WGS84-punten |
| `convert_rd_to_wgs84` | RD (EPSG:28992) -> lon/lat |
| `convert_wgs84_to_rd` | lon/lat -> RD (EPSG:28992) |

### Query-templates (`build_query`)

| Template | Parameters | Status |
|---|---|---|
| `adres_naar_perceel` | `postcode`, `huisnummer`, `limit?` | bevestigd werkend (incl. `imxgeo:bevindtZichOpPerceel`, 2026-10-30) |
| `kadastrale_aanduiding_naar_perceel` | `sectie`, `perceelnummer`, `gemeente`, `limit?` | bevestigd; forceert class-restrictie op `imxgeo:Gemeentegebied` |
| `beperking_op_perceel` | `perceel_uri`, `limit?` | bevestigd werkend |
| `classes_met_aantallen` | `limit?` | bevestigd werkend |
| `resource_coordinaten` | `resource_uri` | bevestigd werkend (2026-07-05) |

`build_paginated_query` is losstaand (geen vaste template): `select_vars`,
`where_clause`, `order_var`, optioneel `cursor` en `limit`.

## Architectuur

```
src/kadaster_kkg_mcp/
  server.py         MCP-tools (FastMCP)
  sparql_client.py  HTTP-client (POST): retry/backoff, ASK/SELECT-parsing
  planner.py         plan_question: NL -> queryplan
  query_builder.py   build_query / build_paginated_query: template + params -> SPARQL
  validator.py        validate_query: syntax + bekende valkuilen
  ontology.py          bevestigde classes/properties/namespaces
  geo.py                RD <-> WGS84 (pyproj), WKT-parsing, haversine-afstand
  config.py             instellingen (env-overrides)
  spec_data.py          laadt data/kkg_spec.json
  data/kkg_spec.json     bronbestand: bevestigde onderzoeksdata
```
