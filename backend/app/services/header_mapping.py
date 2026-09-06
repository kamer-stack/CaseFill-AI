"""Header normalization and adapter for the Step 9 experiment.

Two responsibilities:

1. NORMALIZE + MAP a verbatim Urdu header (as emitted by the VLM) to one of
   the known semantic keys: serial, child, father, mother, gender_relation,
   date_of_birth, remarks, or NEEDS_REVIEW.

2. ADAPT header-keyed extraction output into the existing CANONICAL flat
   schema (extraction_schemas.json b_form) WITHOUT inferring, swapping,
   reconstructing, or guessing any values. Raw values pass through verbatim.

Used by the Step 9 A/B runner and the Step 9 regression tests. Production
extraction does not call into this module.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from .consistency_check import (
    resolve_repeated_field,
    NAME_SIMILARITY_THRESHOLD,
    CNIC_SIMILARITY_THRESHOLD,
)


# ─── Canonical header → semantic key ──────────────────────────────────────

CANONICAL_HEADERS_BY_SEMANTIC = {
    "serial": "نمبر شمار",
    "child": "بچے کا نام اور رجسٹریشن نمبر",
    "father": "والد کا نام اور شناختی کارڈ نمبر",
    "mother": "والدہ کا نام اور شناختی کارڈ نمبر",
    "gender_relation": "جنس / رشتہ",
    "date_of_birth": "تاریخ پیدائش",
    "remarks": "معذوری",
}


def normalize_header(h: Any) -> str:
    """Deterministic Unicode normalization of a header string.

    Strips whitespace, collapses internal runs, applies NFKC. Returns ""
    for non-string / empty input. Never invents characters.
    """
    if h is None:
        return ""
    if not isinstance(h, str):
        h = str(h)
    h = unicodedata.normalize("NFKC", h).strip()
    # Collapse whitespace runs (some OCR renders add spaces between letters).
    parts = h.split()
    return " ".join(parts)


# Reverse: normalized canonical header → semantic key.
# Defined AFTER normalize_header so the comprehension resolves at import time.
_CANONICAL_BY_NORMALIZED: dict[str, str] = {
    normalize_header(h): k for k, h in CANONICAL_HEADERS_BY_SEMANTIC.items()
}

# ─── Character-level keywords for partial/variant matching ────────────────
#
# These are used only when an exact normalized match fails. They are
# distinctive multi-character Urdu substrings that uniquely identify a
# column's semantic role. If two keywords match, or none matches, the
# mapping is NEEDS_REVIEW.

_KEYWORD_HINTS: list[tuple[str, str]] = [
    ("بچے کا نام", "child"),
    ("بچےکا نام", "child"),
    ("والدہ کا نام", "mother"),
    ("والدہ کا", "mother"),
    ("والد کا نام", "father"),
    ("والد کا", "father"),
    ("نمبر شمار", "serial"),
    ("تاریخ پیدائش", "date_of_birth"),
    ("تاریخِ پیدائش", "date_of_birth"),
    ("جنس", "gender_relation"),
    ("رشتہ", "gender_relation"),
    ("معذوری", "remarks"),
]


def map_header_to_semantic(header: Any) -> str:
    """Map a verbatim Urdu header to a semantic key, or 'NEEDS_REVIEW'.

    Two-pass:
      1. Exact match against the canonical set (after normalization).
      2. Keyword-substring match against distinctive Urdu fragments.
    If keyword pass matches multiple different semantic keys, returns
    NEEDS_REVIEW (ambiguous). Never guesses.
    """
    norm = normalize_header(header)
    if not norm:
        return "NEEDS_REVIEW"

    # Pass 1 — exact canonical match
    if norm in _CANONICAL_BY_NORMALIZED:
        return _CANONICAL_BY_NORMALIZED[norm]

    # Pass 2 — keyword substring
    hits: set[str] = set()
    for keyword, semantic in _KEYWORD_HINTS:
        if keyword in norm:
            hits.add(semantic)

    if len(hits) == 1:
        return next(iter(hits))
    # 0 hits or >1 distinct semantic — ambiguous
    return "NEEDS_REVIEW"


def map_all_headers(headers: list[Any]) -> dict[str, str]:
    """Build the full {verbatim_header: semantic_key} map for a row.

    Enforces the no-duplicates rule: if two distinct verbatim headers map to
    the same semantic key, BOTH are demoted to NEEDS_REVIEW. This matches
    the Step 9 prompt's instruction to the model.
    """
    raw_map: dict[str, str] = {}
    for h in headers:
        verbatim = h if isinstance(h, str) else ("" if h is None else str(h))
        raw_map[verbatim] = map_header_to_semantic(verbatim)

    # Demote semantic keys that collide.
    semantic_to_verbatims: dict[str, list[str]] = {}
    for v, s in raw_map.items():
        if s == "NEEDS_REVIEW":
            continue
        semantic_to_verbatims.setdefault(s, []).append(v)
    for semantic, verbatims in semantic_to_verbatims.items():
        if len(verbatims) > 1:
            for v in verbatims:
                raw_map[v] = "NEEDS_REVIEW"
    return raw_map


# ─── Adapter: header-keyed → canonical ─────────────────────────────────────

def adapt_header_keyed_to_canonical(hk: dict) -> dict:
    """Convert header-keyed extraction output to the canonical flat schema.

    Rules:
      - Reads the verbatim header keys inside each table_rows entry.
      - Maps each verbatim header to a semantic key (deterministically).
      - Copies the corresponding name/cnic/reg/etc values into the flat
        canonical fields. Values are NEVER changed, reordered, swapped,
        inferred, or reconstructed.
      - A header whose semantic key is NEEDS_REVIEW does NOT populate any
        canonical field — those fields stay null with confidence 0. The raw
        verbatim text is preserved under _header_mapping and _raw_column_headers.
      - Only the first row is used for father/mother (they are repeated on
        every row by form design); per-row values populate children[].
    """
    result: dict[str, Any] = {
        "crc_number": hk.get("crc_number"),
        "applicant_name": hk.get("applicant_name"),
        "applicant_cnic_number": hk.get("applicant_cnic_number"),
        "father_name": None,
        "father_cnic_number": None,
        "mother_name": None,
        "mother_cnic_number": None,
        "children": [],
        "confidence": {
            "crc_number": 0,
            "applicant_name": 0,
            "applicant_cnic_number": 0,
            "father_name": 0,
            "father_cnic_number": 0,
            "mother_name": 0,
            "mother_cnic_number": 0,
            "children": [],
        },
    }

    # Top-level confidence (pass through as-is if provided)
    hk_conf = hk.get("confidence") or {}
    if isinstance(hk_conf, dict):
        for k in ("crc_number", "applicant_name", "applicant_cnic_number"):
            if k in hk_conf:
                result["confidence"][k] = hk_conf[k]

    # ── Locate the semantic→verbatim header mapping ──
    # Prefer the model's own _header_mapping; re-derive deterministically
    # so the adapter is independent of any model-side mistakes.
    raw_headers = hk.get("_raw_column_headers") or hk.get("table_headers") or []
    if not isinstance(raw_headers, list):
        raw_headers = []
    header_map = map_all_headers(raw_headers)

    # Reverse lookup: semantic key → verbatim header (first match only).
    semantic_to_header: dict[str, str] = {}
    for verbatim, semantic in header_map.items():
        if semantic == "NEEDS_REVIEW":
            continue
        if semantic not in semantic_to_header:
            semantic_to_header[semantic] = verbatim

    rows = hk.get("table_rows") or []
    if not isinstance(rows, list):
        rows = []

    # ── Father / mother (repeated on every row by form design) ──
    # A single-row form has nothing to vote on (falls through to
    # "consistent" with that one value). A multi-child form gives us
    # independent readings of the same ground-truth value per row —
    # majority-vote across them instead of trusting row 0 alone, since a
    # misread on row 0 would otherwise silently carry through unflagged.
    father_hdr = semantic_to_header.get("father")
    mother_hdr = semantic_to_header.get("mother")
    child_conf_list = hk_conf.get("children") if isinstance(hk_conf, dict) else []
    if not isinstance(child_conf_list, list):
        child_conf_list = []

    def _row_cell_values(hdr: str | None, key: str) -> list[Any]:
        values = []
        for row in rows:
            if not isinstance(row, dict) or not hdr or hdr not in row:
                values.append(None)
                continue
            cell = row[hdr]
            values.append(cell.get(key) if isinstance(cell, dict) else None)
        return values

    def _resolve_parent_field(hdr: str | None, cell_key: str, conf_key: str, is_cnic: bool):
        values = _row_cell_values(hdr, cell_key)
        threshold = CNIC_SIMILARITY_THRESHOLD if is_cnic else NAME_SIMILARITY_THRESHOLD
        report = resolve_repeated_field(values, field_name=conf_key, threshold=threshold)
        if report["status"] in ("consistent", "corrected"):
            resolved = report["resolved_value"]
            conf = 0
            for i, v in enumerate(values):
                if v == resolved and i < len(child_conf_list) and isinstance(child_conf_list[i], dict):
                    conf = max(conf, child_conf_list[i].get(conf_key, 0))
            return resolved, conf, report["status"]
        return None, 0, "requires_human_review"

    (result["father_name"], result["confidence"]["father_name"], father_name_status) = (
        _resolve_parent_field(father_hdr, "name", "father_name", is_cnic=False)
    )
    (result["father_cnic_number"], result["confidence"]["father_cnic_number"], father_cnic_status) = (
        _resolve_parent_field(father_hdr, "cnic", "father_cnic_number", is_cnic=True)
    )
    (result["mother_name"], result["confidence"]["mother_name"], mother_name_status) = (
        _resolve_parent_field(mother_hdr, "name", "mother_name", is_cnic=False)
    )
    (result["mother_cnic_number"], result["confidence"]["mother_cnic_number"], mother_cnic_status) = (
        _resolve_parent_field(mother_hdr, "cnic", "mother_cnic_number", is_cnic=True)
    )

    # Audit trail: which parent fields were auto-corrected via majority vote
    # vs. flagged for human review due to no clear majority (2-2 split etc).
    result["_parent_field_consensus"] = {
        "father_name": father_name_status,
        "father_cnic_number": father_cnic_status,
        "mother_name": mother_name_status,
        "mother_cnic_number": mother_cnic_status,
    }

    # Raw Urdu echoes — pass through unchanged
    result["_raw_father_name_urdu"] = hk.get("_raw_father_name_urdu")
    result["_raw_mother_name_urdu"] = hk.get("_raw_mother_name_urdu")

    # ── Children (per-row) ──
    child_hdr = semantic_to_header.get("child")
    gender_hdr = semantic_to_header.get("gender_relation")
    dob_hdr = semantic_to_header.get("date_of_birth")
    remarks_hdr = semantic_to_header.get("remarks")
    serial_hdr = semantic_to_header.get("serial")

    raw_child_names: list[Any] = hk.get("_raw_child_names_urdu") or []
    if not isinstance(raw_child_names, list):
        raw_child_names = []
    child_conf_list = hk_conf.get("children") if isinstance(hk_conf, dict) else []
    if not isinstance(child_conf_list, list):
        child_conf_list = []

    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue

        serial = row.get("serial_number")
        if serial is None and serial_hdr:
            serial = row.get(serial_hdr)
        if serial is None:
            serial = i + 1

        # Child cell
        child_name = None
        child_reg = None
        if child_hdr and child_hdr in row:
            cell = row[child_hdr]
            if isinstance(cell, dict):
                child_name = cell.get("name")
                child_reg = cell.get("registration_number")
            else:
                # Tolerate scalar — treat as name, reg stays null
                child_name = cell

        child: dict[str, Any] = {
            "serial_number": serial,
            "child_name": child_name,
            "child_registration_number": child_reg,
            "gender_relation": row.get(gender_hdr) if gender_hdr else None,
            "date_of_birth": row.get(dob_hdr) if dob_hdr else None,
            "remarks": row.get(remarks_hdr) if remarks_hdr else None,
        }
        result["children"].append(child)

        # Confidence for this child row
        row_conf = child_conf_list[i] if i < len(child_conf_list) else {}
        if not isinstance(row_conf, dict):
            row_conf = {}
        result["confidence"]["children"].append({
            "serial_number": row_conf.get("serial_number", 0),
            "child_name": row_conf.get("child_name", 0),
            "child_registration_number": row_conf.get("child_registration_number", 0),
            "gender_relation": row_conf.get("gender_relation", 0),
            "date_of_birth": row_conf.get("date_of_birth", 0),
            "remarks": row_conf.get("remarks", 0),
        })

    # Raw child names array — preserve verbatim
    result["_raw_child_names_urdu"] = list(raw_child_names) if raw_child_names else [
        None for _ in result["children"]
    ]

    # Diagnostic pass-through
    result["_raw_column_headers"] = list(raw_headers)
    result["_header_mapping"] = dict(header_map)
    if "_consistency_check" in hk:
        result["_consistency_check"] = hk["_consistency_check"]

    return result


def _normalize_reg_number(value: Any) -> str:
    """Strip everything but alphanumerics, lowercase — so '99-2024-333333',
    '99 2024 333333', and '99-2024-333333 ' all compare equal."""
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def match_target_child(result: dict, target_registration_number: str | None) -> dict:
    """Deterministically flag which child in a B-form is the case's target
    orphan, matched against the child's registration number the FSO reads
    directly off the physical document — instead of trusting the model to
    correctly guess a row from a serial-number instruction (which fails
    silently if the FSO miscounts, or if row order doesn't match intake
    order).

    Mutates children[].is_target_child and sets
    result["_target_child_match_status"] to one of:
      - "matched"       exactly one child's registration number matched
      - "no_match"      no child matched — FSO must select manually
      - "ambiguous"     more than one child matched (duplicate reg numbers
                         on the form — itself a red flag worth surfacing)
      - "not_provided"  no target registration number was given at all

    Never guesses which child is the target when the match isn't clean —
    this is the NULL OVER GUESS principle applied to target-child selection,
    not just individual field values.
    """
    children = result.get("children", [])
    if not isinstance(children, list):
        return result

    for child in children:
        if isinstance(child, dict):
            child["is_target_child"] = False

    if not target_registration_number:
        result["_target_child_match_status"] = "not_provided"
        return result

    target_norm = _normalize_reg_number(target_registration_number)
    matches = [
        child for child in children
        if isinstance(child, dict)
        and target_norm
        and _normalize_reg_number(child.get("child_registration_number")) == target_norm
    ]

    if len(matches) == 1:
        matches[0]["is_target_child"] = True
        result["_target_child_match_status"] = "matched"
    elif len(matches) > 1:
        result["_target_child_match_status"] = "ambiguous"
    else:
        result["_target_child_match_status"] = "no_match"

    return result
