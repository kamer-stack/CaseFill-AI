"""
Majority-vote consistency check for values that repeat across multiple
rows of a B-form (father_name, mother_name, father_cnic, mother_cnic are
printed once per sibling row by form design, so a multi-child B-form gives
us several independent readings of the same ground-truth value).

Why this exists: header_mapping.adapt_header_keyed_to_canonical() used to
trust row 0 alone for father/mother fields. If the VLM misreads that one
cell (confirmed failure mode: Urdu name misreads occur inconsistently
run-to-run), the whole case silently carries the wrong name with no
cross-row check to catch it. This module lets the adapter check ALL rows
against each other instead of trusting the first one blindly.

Follows NULL OVER GUESS: only resolves a value when there's a clear
majority; otherwise returns None and status="requires_human_review" so
the field gets flagged, never silently guessed.
"""

from __future__ import annotations

from difflib import SequenceMatcher

NAME_SIMILARITY_THRESHOLD = 0.6
CNIC_SIMILARITY_THRESHOLD = 0.85  # stricter: CNICs shouldn't fuzzy-merge on digit noise


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.strip(), b.strip()).ratio()


def _cluster_values(values: list[str], threshold: float) -> list[dict]:
    """Groups near-identical strings together (handles OCR/VLM corruption
    that won't match on exact string equality)."""
    clusters: list[dict] = []
    for v in values:
        if v is None or v == "":
            continue
        placed = False
        for c in clusters:
            if _similarity(v, c["value"]) >= threshold:
                c["members"].append(v)
                c["count"] += 1
                placed = True
                break
        if not placed:
            clusters.append({"value": v, "count": 1, "members": [v]})
    clusters.sort(key=lambda c: c["count"], reverse=True)
    return clusters


def resolve_repeated_field(
    values: list[str],
    field_name: str = "",
    threshold: float = NAME_SIMILARITY_THRESHOLD,
) -> dict:
    """
    Apply majority vote to one repeated field's occurrences across all
    rows of a document.

    Returns:
        {
            "resolved_value": str or None,
            "status": "consistent" | "corrected" | "requires_human_review",
            "clusters": [...],   # full breakdown for audit/debugging
        }

    Rules:
        - Zero non-empty values -> requires_human_review, value None.
        - All non-empty values agree (within `threshold`) -> "consistent".
        - One cluster is strictly larger than every other AND holds a true
          majority (> half of all non-empty occurrences) -> "corrected",
          resolved_value = that cluster's value.
        - Tie at the top, or no cluster reaches a true majority ->
          "requires_human_review", resolved_value None. Never guesses.
    """
    non_empty = [v for v in values if v not in (None, "")]
    if not non_empty:
        return {"resolved_value": None, "status": "requires_human_review", "clusters": []}

    clusters = _cluster_values(non_empty, threshold)

    if len(clusters) == 1:
        return {"resolved_value": clusters[0]["value"], "status": "consistent", "clusters": clusters}

    top, runner_up = clusters[0], clusters[1]

    if top["count"] == runner_up["count"]:
        return {"resolved_value": None, "status": "requires_human_review", "clusters": clusters}

    if top["count"] > len(non_empty) / 2:
        return {"resolved_value": top["value"], "status": "corrected", "clusters": clusters}

    return {"resolved_value": None, "status": "requires_human_review", "clusters": clusters}
