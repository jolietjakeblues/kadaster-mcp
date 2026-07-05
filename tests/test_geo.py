import pytest

from kadaster_kkg_mcp.geo import (
    RdBoundsError,
    WktParseError,
    classify_proximity,
    convert_rd_to_wgs84,
    convert_wgs84_to_rd,
    haversine_distance_meters,
    parse_wkt_point,
)


def test_amersfoort_origin_roundtrip():
    # RD-referentiepunt (Onze Lieve Vrouwetoren, Amersfoort).
    result = convert_rd_to_wgs84(155000, 463000)
    assert result["lon"] == pytest.approx(5.387203, abs=1e-3)
    assert result["lat"] == pytest.approx(52.155172, abs=1e-3)


def test_roundtrip_rd_wgs84_rd():
    original = (121397.0, 487325.0)
    wgs = convert_rd_to_wgs84(*original)
    back = convert_wgs84_to_rd(wgs["lon"], wgs["lat"])
    assert back["x"] == pytest.approx(original[0], abs=0.01)
    assert back["y"] == pytest.approx(original[1], abs=0.01)


def test_out_of_bounds_raises():
    with pytest.raises(RdBoundsError):
        convert_rd_to_wgs84(52.1, 5.3)  # lon/lat per ongeluk als x/y


def test_parse_wkt_point():
    result = parse_wkt_point("POINT(5.387203 52.155172)")
    assert result == {"lon": 5.387203, "lat": 52.155172}


def test_parse_wkt_point_negative_lon():
    result = parse_wkt_point("POINT(-3.5 51.2)")
    assert result["lon"] == -3.5


def test_parse_wkt_point_invalid_raises():
    with pytest.raises(WktParseError):
        parse_wkt_point("not a wkt point")


def test_haversine_distance_zero_for_identical_points():
    assert haversine_distance_meters(5.0, 52.0, 5.0, 52.0) == pytest.approx(0.0, abs=1e-6)


def test_haversine_distance_known_short_hop():
    # Twee dicht bij elkaar gelegen punten (~11m uit elkaar op deze breedtegraad).
    d = haversine_distance_meters(5.387203, 52.155172, 5.387350, 52.155172)
    assert 5 < d < 20


def test_classify_proximity_thresholds():
    assert classify_proximity(10) == "vrijwel zeker hetzelfde kavel/complex"
    assert classify_proximity(49.9) == "vrijwel zeker hetzelfde kavel/complex"
    assert classify_proximity(500) == "twijfelgeval"
    assert classify_proximity(1000) == "twijfelgeval"
    assert classify_proximity(1000.1) == "vrijwel zeker een fout in de bron-registratie"
    assert classify_proximity(9000) == "vrijwel zeker een fout in de bron-registratie"
