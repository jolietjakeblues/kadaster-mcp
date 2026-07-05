"""Syntactische validatie + valkuil-detectie voor SPARQL-queries tegen het KKG-endpoint.

De valkuilen komen direct uit het onderzoeksdocument (kkg_spec.json ->
bekende_valkuilen): brede FILTER(CONTAINS(...))-scans zonder class-restrictie
gaven een read-timeout na 30s. Deze validator waarschuwt daarvoor voordat
een query uitgevoerd wordt, analoog aan hoe rce-cho-mcp waarschuwt voor
dure geof:sfWithin-patronen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

try:
    from rdflib.plugins.sparql import prepareQuery

    _HAS_RDFLIB = True
except ImportError:  # pragma: no cover
    _HAS_RDFLIB = False

from .spec_data import CLASS_RESTRICTED_PREDICATES, UNVERIFIED_PREDICATES, namespaces

_CONTAINS_RE = re.compile(r"FILTER\s*\(\s*CONTAINS\s*\(", re.IGNORECASE)
_TYPE_PATTERN_RE = re.compile(r"\?\w+\s+a\s+\?\w+", re.IGNORECASE)
_LIMIT_RE = re.compile(r"\bLIMIT\s+(\d+)", re.IGNORECASE)
_OFFSET_RE = re.compile(r"\bOFFSET\s+(\d+)", re.IGNORECASE)
_SELECT_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_MAX_LIMIT_PLUS_OFFSET = 10_000


@dataclass
class ValidationResult:
    valid_syntax: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    is_ask: bool = False

    def to_dict(self) -> dict:
        return {
            "valid_syntax": self.valid_syntax,
            "errors": self.errors,
            "warnings": self.warnings,
            "is_ask": self.is_ask,
        }


def _build_prefixed_query(sparql: str) -> str:
    """Voegt bekende prefixes toe zodat rdflib queries zonder expliciete PREFIX-regels
    ook geparsed kunnen worden (gebruikers laten prefixes soms weg)."""
    missing_header = "\n".join(f"PREFIX {p}: <{uri}>" for p, uri in namespaces().items())
    return f"{missing_header}\n{sparql}"


def validate_query(sparql: str) -> ValidationResult:
    result = ValidationResult(valid_syntax=True, is_ask=bool(re.match(r"^\s*ASK\b", sparql, re.IGNORECASE)))

    if not sparql or not sparql.strip():
        result.valid_syntax = False
        result.errors.append("Lege query.")
        return result

    if sparql.count("{") != sparql.count("}"):
        result.valid_syntax = False
        result.errors.append(
            f"Ongebalanceerde accolades: {sparql.count('{')} openende vs {sparql.count('}')} sluitende."
        )

    if _HAS_RDFLIB:
        try:
            prepareQuery(_build_prefixed_query(sparql))
        except Exception as exc:  # noqa: BLE001 - we willen elke parsefout tonen
            result.valid_syntax = False
            result.errors.append(f"SPARQL-syntaxfout: {exc}")
    else:  # pragma: no cover - fallback zonder rdflib
        if not re.search(r"\b(SELECT|ASK|CONSTRUCT|DESCRIBE)\b", sparql, re.IGNORECASE):
            result.valid_syntax = False
            result.errors.append("Geen SELECT/ASK/CONSTRUCT/DESCRIBE gevonden in de query.")

    # --- Bekende valkuil: brede CONTAINS-scan zonder class-restrictie ---
    if _CONTAINS_RE.search(sparql) and _TYPE_PATTERN_RE.search(sparql):
        result.warnings.append(
            "Brede FILTER(CONTAINS(...)) samen met een generiek '?x a ?type'-patroon "
            "gaf in eerdere sessies een read-timeout (>30s) op het KKG-endpoint. "
            "Gebruik eerst een ASK-query om het bestaan van de class/property te checken, "
            "of voeg een concrete class-restrictie toe voordat je filtert."
        )

    # --- ASK-resultaten hebben geen results.bindings ---
    if result.is_ask and re.search(r"results\s*\.\s*bindings", sparql, re.IGNORECASE):
        result.warnings.append(
            "Dit is een ASK-query; het resultaat heeft een top-level 'boolean' veld, "
            "geen 'results.bindings' (dat geldt alleen voor SELECT)."
        )

    # --- Ontbrekende LIMIT op een SELECT zonder sterke restrictie ---
    if _SELECT_RE.search(sparql) and not _LIMIT_RE.search(sparql):
        result.warnings.append(
            "Geen LIMIT gevonden op deze SELECT-query. Voeg een LIMIT toe om onbedoeld "
            "zware, trage queries op de volledige graph te voorkomen."
        )

    # --- Virtuoso-limiet: ORDER BY + OFFSET > 10.000 faalt hard ---
    offset_match = _OFFSET_RE.search(sparql)
    limit_match = _LIMIT_RE.search(sparql)
    if offset_match and int(offset_match.group(1)) + (int(limit_match.group(1)) if limit_match else 0) > _MAX_LIMIT_PLUS_OFFSET:
        result.warnings.append(
            "LIMIT + OFFSET > 10.000: Virtuoso (de triplestore achter KKG) weigert dit "
            "('Sorted TOP clause specifies more than 15000 rows to sort'). Gebruik "
            "keyset-paginering (FILTER(STR(?var) > \"<cursor>\") + ORDER BY STR(?var)) "
            "i.p.v. OFFSET -- zie build_paginated_query."
        )

    # --- Gebruik van nog niet los geverifieerde predicaten ---
    for predicate, note in UNVERIFIED_PREDICATES.items():
        local_name = predicate.split(":")[-1]
        if predicate in sparql or re.search(rf"[:#]{re.escape(local_name)}\b", sparql):
            result.warnings.append(
                f"Query gebruikt '{predicate}', dat nog niet los tegen het live endpoint "
                f"is geverifieerd. {note} Controleer het resultaat extra kritisch."
            )

    # --- Class-gerestricteerde predicaten zonder de vereiste class-restrictie ---
    for predicate, info in CLASS_RESTRICTED_PREDICATES.items():
        local_name = predicate.split(":")[-1]
        used = predicate in sparql or re.search(rf"[:#]{re.escape(local_name)}\b", sparql)
        if used and info["vereiste_class"] not in sparql:
            result.warnings.append(
                f"Query gebruikt '{predicate}' zonder de vereiste class-restrictie "
                f"'{info['vereiste_class']}'. {info['toelichting']}"
            )

    return result
