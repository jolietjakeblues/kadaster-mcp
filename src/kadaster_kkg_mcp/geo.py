"""RD (EPSG:28992) <-> WGS84 (EPSG:4326) conversie.

Niet in de aangeleverde spec vermeld, maar toegevoegd voor pariteit met de
RCE-MCP (die dezelfde tool heeft): KKG-geometrieen (geosparql:hasGeometry)
zijn voor Nederlandse kadastrale data doorgaans in RD. Gebruikt pyproj/PROJ
(authoritative transformatie, incl. NL-correctiegrid) in plaats van een
zelf getranscribeerde benaderingsformule.
"""

from __future__ import annotations

from pyproj import Transformer

_TO_WGS84 = Transformer.from_crs("EPSG:28992", "EPSG:4326", always_xy=True)
_TO_RD = Transformer.from_crs("EPSG:4326", "EPSG:28992", always_xy=True)


class RdBoundsError(ValueError):
    pass


def _check_rd_bounds(x: float, y: float) -> None:
    if not (0 <= x <= 300000 and 300000 <= y <= 650000):
        raise RdBoundsError(
            f"RD-coordinaat ({x}, {y}) valt buiten het geldige bereik voor Nederland "
            "(x: 0-300000, y: 300000-650000). Controleer of x/y niet verwisseld zijn."
        )


def convert_rd_to_wgs84(x: float, y: float) -> dict[str, float]:
    """Converteert RD (EPSG:28992) x/y naar WGS84 (lon, lat) in decimale graden."""
    _check_rd_bounds(x, y)
    lon, lat = _TO_WGS84.transform(x, y)
    return {"lon": round(lon, 7), "lat": round(lat, 7)}


def convert_wgs84_to_rd(lon: float, lat: float) -> dict[str, float]:
    """Converteert WGS84 (lon, lat) naar RD (EPSG:28992) x/y."""
    x, y = _TO_RD.transform(lon, lat)
    return {"x": round(x, 3), "y": round(y, 3)}
