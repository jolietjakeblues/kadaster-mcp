"""Bevestigde ontologie-kennis over de KKG (classes, properties, namespaces).

Alle inhoud komt uit het live-geverifieerde onderzoek in data/kkg_spec.json.
Dit is bewust geen live SPARQL-introspectie: de spec bevat al bevestigde
tellingen en voorkomt dat elke ontology-vraag een dure query tegen de graph
triggert (zie bekende_valkuilen -> timeouts bij brede scans).
"""

from __future__ import annotations

from typing import Any

from .spec_data import UNVERIFIED_PREDICATES, confirmed_classes, confirmed_properties, namespaces


def list_namespaces() -> dict[str, str]:
    return namespaces()


def list_confirmed_classes() -> list[dict[str, Any]]:
    return confirmed_classes()


def describe_class(class_name: str) -> dict[str, Any]:
    """Geeft bevestigde info over een class: telling (indien bekend) en properties.

    class_name mag met of zonder prefix, bv. 'imxgeo:Perceel' of 'Perceel'.
    """
    classes = confirmed_classes()
    props_by_class = confirmed_properties()

    normalized = class_name if ":" in class_name else None
    match = None
    for c in classes:
        c_name = c["class"]
        if c_name == class_name or c_name.split(":")[-1].lower() == class_name.lower():
            match = c
            normalized = c_name
            break

    properties = props_by_class.get(normalized, []) if normalized else []
    flagged = [p for p in properties if p in UNVERIFIED_PREDICATES]

    if match is None and not properties:
        known = ", ".join(c["class"] for c in classes)
        return {
            "found": False,
            "message": (
                f"'{class_name}' staat niet in de bevestigde classes-lijst. "
                f"Bekende classes: {known}. Gebruik query_sparql met "
                f"'classes_met_aantallen' (zie build_query) om live te verkennen."
            ),
        }

    return {
        "found": True,
        "class": normalized or class_name,
        "aantal_ca": match.get("aantal_ca") if match else None,
        "bevestigd": match.get("bevestigd", match.get("aantal_ca") is not None) if match else None,
        "opmerking": match.get("opmerking") if match else None,
        "properties": properties,
        "properties_nog_te_verifieren": flagged,
    }


def ontology_search(keyword: str) -> dict[str, Any]:
    """Doorzoekt de bevestigde classes/properties op een trefwoord (case-insensitive)."""
    kw = keyword.lower()
    classes = [c for c in confirmed_classes() if kw in c["class"].lower()]

    matched_properties: dict[str, list[str]] = {}
    for cls_name, props in confirmed_properties().items():
        hits = [p for p in props if isinstance(p, str) and kw in p.lower()]
        if hits or kw in cls_name.lower():
            matched_properties[cls_name] = hits or props

    matched_namespaces = {p: uri for p, uri in namespaces().items() if kw in p.lower() or kw in uri.lower()}

    return {
        "keyword": keyword,
        "classes": classes,
        "properties": matched_properties,
        "namespaces": matched_namespaces,
    }
