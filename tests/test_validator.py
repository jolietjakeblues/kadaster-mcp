from kadaster_kkg_mcp.validator import validate_query


def test_valid_select_with_limit():
    q = "SELECT ?s WHERE { ?s a <http://example.org/Foo> } LIMIT 10"
    result = validate_query(q)
    assert result.valid_syntax
    assert not result.errors


def test_unbalanced_braces_is_invalid():
    q = "SELECT ?s WHERE { ?s a <http://example.org/Foo>"
    result = validate_query(q)
    assert not result.valid_syntax
    assert result.errors


def test_contains_scan_pitfall_warns():
    q = (
        "SELECT DISTINCT ?type (COUNT(?s) as ?cnt) WHERE { "
        '?s a ?type . FILTER(CONTAINS(LCASE(STR(?type)), "beperking")) } GROUP BY ?type'
    )
    result = validate_query(q)
    assert any("timeout" in w.lower() or "CONTAINS" in w for w in result.warnings)


def test_missing_limit_warns():
    q = "SELECT ?s ?p ?o WHERE { ?s ?p ?o }"
    result = validate_query(q)
    assert any("LIMIT" in w for w in result.warnings)


def test_ask_query_detected():
    q = "ASK { ?s ?p ?o }"
    result = validate_query(q)
    assert result.is_ask
    assert result.valid_syntax


def test_bevindtzichopperceel_no_longer_warns():
    # imxgeo:bevindtZichOpPerceel is bevestigd (2026-10-30, ASK + steekproef
    # tegen het live endpoint) en staat niet meer in UNVERIFIED_PREDICATES.
    q = (
        "PREFIX imxgeo: <http://modellen.geostandaarden.nl/def/imx-geo#>\n"
        "SELECT ?per WHERE { ?geb imxgeo:bevindtZichOpPerceel ?per } LIMIT 5"
    )
    result = validate_query(q)
    assert not any("bevindtZichOpPerceel" in w for w in result.warnings)


def test_offset_over_10000_warns():
    q = "SELECT ?s WHERE { ?s a <http://example.org/Foo> } ORDER BY ?s LIMIT 5000 OFFSET 8000"
    result = validate_query(q)
    assert any("10.000" in w or "Virtuoso" in w for w in result.warnings)


def test_offset_under_10000_no_pagination_warning():
    q = "SELECT ?s WHERE { ?s a <http://example.org/Foo> } ORDER BY ?s LIMIT 100 OFFSET 200"
    result = validate_query(q)
    assert not any("Virtuoso" in w for w in result.warnings)


def test_imxgeo_naam_without_class_restriction_warns():
    q = (
        "PREFIX imxgeo: <http://modellen.geostandaarden.nl/def/imx-geo#>\n"
        "SELECT ?naam WHERE { ?plaats imxgeo:naam ?naam } LIMIT 5"
    )
    result = validate_query(q)
    assert any("Gemeentegebied" in w for w in result.warnings)


def test_imxgeo_naam_with_class_restriction_no_warning():
    q = (
        "PREFIX imxgeo: <http://modellen.geostandaarden.nl/def/imx-geo#>\n"
        "SELECT ?naam WHERE { ?plaats a imxgeo:Gemeentegebied ; imxgeo:naam ?naam } LIMIT 5"
    )
    result = validate_query(q)
    assert not any("Gemeentegebied" in w for w in result.warnings)


def test_order_by_class_scan_warns():
    # Bevestigd (2026-10-30): ORDER BY op een class-scan-variabele timet uit
    # op grote classes zoals imxgeo:Perceel (~8,4 miljoen instances),
    # onafhankelijk van OPTIONAL.
    q = (
        "PREFIX imxgeo: <http://modellen.geostandaarden.nl/def/imx-geo#>\n"
        "SELECT ?per WHERE { ?per a imxgeo:Perceel . } ORDER BY ?per LIMIT 5"
    )
    result = validate_query(q)
    assert any("class-scan" in w or "ORDER BY" in w for w in result.warnings)


def test_order_by_class_scan_warns_even_with_extra_filter():
    # Een extra FILTER (hier: sectie) is op landelijke schaal niet selectief
    # genoeg om de class-scan-waarschuwing te onderdrukken.
    q = (
        "PREFIX imxgeo: <http://modellen.geostandaarden.nl/def/imx-geo#>\n"
        "PREFIX ext: <https://modellen.kkg.kadaster.nl/def/imxgeo-ext#>\n"
        'SELECT ?per WHERE { ?per a imxgeo:Perceel ; ext:sectie "A" . } ORDER BY ?per LIMIT 5'
    )
    result = validate_query(q)
    assert any("class-scan" in w or "ORDER BY" in w for w in result.warnings)


def test_order_by_on_fixed_subject_does_not_warn():
    # ORDER BY op een variabele die via een vaste subject-URI gebonden is
    # (smalle resultset) is bevestigd snel en triggert deze check niet.
    q = (
        "PREFIX imxgeo: <http://modellen.geostandaarden.nl/def/imx-geo#>\n"
        "SELECT ?grondslagcode WHERE {\n"
        "  ?beperking imxgeo:isBeperkingOpPerceel <https://data.kkg.kadaster.nl/id/perceel/1/1> ;\n"
        "    imxgeo:grondslagcode ?grondslagcode .\n"
        "} ORDER BY ?grondslagcode LIMIT 5"
    )
    result = validate_query(q)
    assert not any("class-scan" in w for w in result.warnings)


def test_order_by_with_keyset_cursor_does_not_warn():
    q = (
        "PREFIX imxgeo: <http://modellen.geostandaarden.nl/def/imx-geo#>\n"
        "SELECT ?per WHERE {\n"
        "  ?per a imxgeo:Perceel .\n"
        '  FILTER(STR(?per) > "https://data.kkg.kadaster.nl/id/perceel/1/1")\n'
        "} ORDER BY STR(?per) LIMIT 5000"
    )
    result = validate_query(q)
    assert not any("class-scan" in w for w in result.warnings)
