"""RD (EPSG:28992) <-> WGS84 (EPSG:4326) conversie.

Niet in de aangeleverde spec vermeld, maar toegevoegd voor pariteit met de
RCE-MCP (die dezelfde tool heeft): KKG-geometrieen (geosparql:hasGeometry)
zijn voor Nederlandse kadastrale data doorgaans in RD. Gebruikt pyproj/PROJ
(authoritative transformatie, incl. NL-correctiegrid) in plaats van een
zelf getranscribeerde benaderingsformule.
"""

from __future__ import annotations

import re
from math import asin, cos, radians, sin, sqrt

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


_WKT_POINT_RE = re.compile(r"POINT\s*\(\s*(-?[0-9.]+)\s+(-?[0-9.]+)\s*\)", re.IGNORECASE)

_EARTH_RADIUS_M = 6_371_000.0

# Drempels uit de "geen_perceel_geschiedenis"-workaround (zie kkg_spec.json),
# gevalideerd tegen een steekproef van 80 monumenten (2026-07-05).
_SAME_PARCEL_THRESHOLD_M = 50.0
_AMBIGUOUS_THRESHOLD_M = 1000.0


class WktParseError(ValueError):
    pass


def parse_wkt_point(wkt: str) -> dict[str, float]:
    """Parseert 'POINT(lon lat)' (WGS84, zoals geosparql:asWKT teruggeeft
    voor ext:plaatscoordinaten in de KKG) naar {lon, lat}."""
    match = _WKT_POINT_RE.search(wkt)
    if not match:
        raise WktParseError(f"Kon geen POINT(lon lat) parsen uit WKT: {wkt!r}")
    return {"lon": float(match.group(1)), "lat": float(match.group(2))}


def haversine_distance_meters(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Afstand in meters tussen twee WGS84-punten (haversine, geen ellipsoide-correctie
    nodig voor de hier gebruikte drempels van 50m/1km)."""
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * _EARTH_RADIUS_M * asin(sqrt(a))


def classify_proximity(meters: float) -> str:
    """Classificeert een afstand volgens de perceel-geschiedenis-workaround:
    KKG kent geen expliciete opvolgingsrelatie tussen percelen, dus geometrische
    nabijheid is het enige aanknopingspunt om een 'oude' aanduiding aan een
    huidig perceel te koppelen."""
    if meters < _SAME_PARCEL_THRESHOLD_M:
        return "vrijwel zeker hetzelfde kavel/complex"
    if meters <= _AMBIGUOUS_THRESHOLD_M:
        return "twijfelgeval"
    return "vrijwel zeker een fout in de bron-registratie"
