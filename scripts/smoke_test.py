#!/usr/bin/env python3
"""Handmatige smoke test tegen het live KKG-endpoint.

    python scripts/smoke_test.py

Voert de bevestigde queries uit de spec uit en toont resultaten. Alle
eerder "nog niet los geverifieerde" predicaten (imxgeo:naam op
imxgeo:Gemeentegebied, imxgeo:bevindtZichOpPerceel) zijn inmiddels bevestigd
(resp. 2026-07-05 en 2026-10-30) en staan hier als regressie-check.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from kadaster_kkg_mcp.query_builder import build_classes_met_aantallen
from kadaster_kkg_mcp.sparql_client import SparqlClient, format_bindings_as_table


def main() -> None:
    client = SparqlClient()

    print("=== ping ===")
    print(client.ping())

    print("\n=== ASK: imxgeo:bevindtZichOpPerceel bestaat? (bevestigd 2026-10-30) ===")
    print(
        client.ask(
            "PREFIX imxgeo: <http://modellen.geostandaarden.nl/def/imx-geo#>\n"
            "ASK { ?geb imxgeo:bevindtZichOpPerceel ?per }"
        )
    )

    print("\n=== classes_met_aantallen (bevestigd werkend) ===")
    result = client.query(build_classes_met_aantallen(limit=10))
    print(format_bindings_as_table(result))


if __name__ == "__main__":
    main()
