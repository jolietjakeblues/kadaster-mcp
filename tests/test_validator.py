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


def test_unverified_predicate_warns():
    q = (
        "PREFIX imxgeo: <http://modellen.geostandaarden.nl/def/imx-geo#>\n"
        "SELECT ?per WHERE { ?geb imxgeo:bevindtZichOpPerceel ?per } LIMIT 5"
    )
    result = validate_query(q)
    assert any("bevindtZichOpPerceel" in w for w in result.warnings)


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
