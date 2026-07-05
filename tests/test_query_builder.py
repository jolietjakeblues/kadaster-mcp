import pytest

from kadaster_kkg_mcp.query_builder import QueryBuildError, build_paginated_query, build_query


def test_adres_naar_perceel_valid():
    result = build_query("adres_naar_perceel", {"postcode": "1234ab", "huisnummer": "10"})
    assert '"1234AB"' in result["sparql"]
    assert "imxgeo:huisnummer 10" in result["sparql"]
    assert result["waarschuwingen"]  # bevindtZichOpPerceel is unverified


def test_adres_naar_perceel_invalid_postcode():
    with pytest.raises(QueryBuildError):
        build_query("adres_naar_perceel", {"postcode": "not-a-postcode", "huisnummer": 10})


def test_kadastrale_aanduiding_naar_perceel():
    result = build_query(
        "kadastrale_aanduiding_naar_perceel",
        {"sectie": "a", "perceelnummer": 123, "gemeente": "Utrecht"},
    )
    assert 'ext:sectie "A"' in result["sparql"]
    assert 'CONTAINS(LCASE(?plaatsnaam), LCASE("Utrecht"))' in result["sparql"]
    # imxgeo:naam is bevestigd, maar alleen op imxgeo:Gemeentegebied -- de
    # class-restrictie moet altijd meegebouwd worden.
    assert "?plaats a imxgeo:Gemeentegebied" in result["sparql"]
    assert result["waarschuwingen"] == []


def test_beperking_op_perceel_wraps_uri():
    result = build_query(
        "beperking_op_perceel",
        {"perceel_uri": "https://data.kkg.kadaster.nl/id/perceel/1/1"},
    )
    assert "<https://data.kkg.kadaster.nl/id/perceel/1/1>" in result["sparql"]
    assert result["waarschuwingen"] == []


def test_beperking_op_perceel_rejects_bad_uri():
    with pytest.raises(QueryBuildError):
        build_query("beperking_op_perceel", {"perceel_uri": "not-a-uri"})


def test_classes_met_aantallen_default_limit():
    result = build_query("classes_met_aantallen")
    assert "LIMIT 20" in result["sparql"]


def test_unknown_template_raises():
    with pytest.raises(QueryBuildError):
        build_query("does_not_exist", {})


def test_resource_coordinaten():
    result = build_query(
        "resource_coordinaten",
        {"resource_uri": "https://data.kkg.kadaster.nl/id/perceel/1/1"},
    )
    assert "ext:plaatscoordinaten" in result["sparql"]
    assert "geosparql:asWKT" in result["sparql"]
    assert "<https://data.kkg.kadaster.nl/id/perceel/1/1>" in result["sparql"]


def test_build_query_filters_extra_params():
    # plan_question kan meerdere kandidaat-parameters teruggeven (bv. zowel
    # perceel_uri als resource_uri); build_query moet alleen doorgeven wat de
    # gekozen template accepteert, i.p.v. een TypeError te geven.
    result = build_query(
        "beperking_op_perceel",
        {
            "perceel_uri": "https://data.kkg.kadaster.nl/id/perceel/1/1",
            "resource_uri": "https://data.kkg.kadaster.nl/id/perceel/1/1",
            "postcode": "1234AB",
        },
    )
    assert "<https://data.kkg.kadaster.nl/id/perceel/1/1>" in result["sparql"]


def test_build_paginated_query_first_page_no_cursor():
    sparql = build_paginated_query(
        select_vars="?perceel",
        where_clause='?beperking imxgeo:isBeperkingOpPerceel ?perceel ; imxgeo:grondslagcode "EWE" .',
        order_var="?perceel",
    )
    assert "FILTER(STR(" not in sparql
    assert "ORDER BY STR(?perceel)" in sparql
    assert "LIMIT 5000" in sparql


def test_build_paginated_query_with_cursor():
    sparql = build_paginated_query(
        select_vars="?perceel",
        where_clause="?perceel a imxgeo:Perceel .",
        order_var="?perceel",
        cursor="https://data.kkg.kadaster.nl/id/perceel/1/1",
        limit=100,
    )
    assert 'FILTER(STR(?perceel) > "https://data.kkg.kadaster.nl/id/perceel/1/1")' in sparql
    assert "LIMIT 100" in sparql


def test_build_paginated_query_requires_question_mark_var():
    with pytest.raises(QueryBuildError):
        build_paginated_query("perceel", "?perceel a imxgeo:Perceel .", "perceel")
