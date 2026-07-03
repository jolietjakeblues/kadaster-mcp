import pytest

from kadaster_kkg_mcp.geo import RdBoundsError, convert_rd_to_wgs84, convert_wgs84_to_rd


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
