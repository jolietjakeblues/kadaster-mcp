import pytest

from kadaster_kkg_mcp.query_builder import QueryBuildError, build_query


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
