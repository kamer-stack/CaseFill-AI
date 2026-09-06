"""
Cross-document validation engine.
Ported from the original prototype's server.py cross-check logic.

Handles case-insensitive comparison (AHMED TARIQ == ahmed tariq).
Cross-script (Urdu vs Roman) name comparisons are soft-flagged as
DIFFERENT_SCRIPT for human review rather than auto-resolved — see
compare_names() below.
"""

import re
from difflib import SequenceMatcher

from .validation import compare_father_mother_cnic_extractions

# Eastern Arabic numeral normalization
EASTERN_ARABIC = {chr(0x0660 + i): str(i) for i in range(10)}  # ۰-۹ → 0-9

SIMILAR_THRESHOLD = 0.75

# Unicode range detection for script identification
_ARABIC_RANGE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
_ROMAN_RANGE = re.compile(r"[A-Za-z]")


def normalize_numerals(text: str | None) -> str | None:
    """Convert Eastern Arabic numerals (۰-۹) to Western digits (0-9)."""
    if text is None:
        return None
    return "".join(EASTERN_ARABIC.get(ch, ch) for ch in text)


def normalize_for_comparison(text: str | None) -> str | None:
    """Normalize a string for cross-check comparison."""
    if text is None:
        return None
    text = normalize_numerals(text)
    return text.strip().lower()


def _is_urdu_script(text: str) -> bool:
    """Return True if the string contains Urdu/Arabic characters."""
    return bool(_ARABIC_RANGE.search(text))


def _is_roman_script(text: str) -> bool:
    """Return True if the string contains Latin/Roman characters."""
    return bool(_ROMAN_RANGE.search(text))


def compare_values(val1, val2) -> dict:
    """
    Compare two values and return status: MATCH, SIMILAR, MISMATCH, or NEEDS_REVIEW.
    """
    if val1 is None or val2 is None:
        return {"status": "NEEDS_REVIEW", "detail": "missing value", "similarity": None}

    n1 = normalize_for_comparison(str(val1))
    n2 = normalize_for_comparison(str(val2))

    if n1 == n2:
        return {"status": "MATCH", "detail": None, "similarity": 1.0}

    ratio = SequenceMatcher(None, n1, n2).ratio()

    if ratio >= SIMILAR_THRESHOLD:
        return {
            "status": "SIMILAR",
            "detail": f"'{val1}' vs '{val2}'",
            "similarity": round(ratio, 3),
        }
    else:
        return {
            "status": "MISMATCH",
            "detail": f"'{val1}' vs '{val2}'",
            "similarity": round(ratio, 3),
        }


def compare_names(val1, val2) -> dict:
    """
    Compare two name values. If one is Urdu-script and the other is Roman-script,
    return DIFFERENT_SCRIPT instead of a misleading MISMATCH.
    Falls back to compare_values() when both are in the same script.
    """
    if val1 is None or val2 is None:
        return {"status": "NEEDS_REVIEW", "detail": "missing value", "similarity": None}

    s1, s2 = str(val1).strip(), str(val2).strip()
    v1_urdu = _is_urdu_script(s1)
    v1_roman = _is_roman_script(s1)
    v2_urdu = _is_urdu_script(s2)
    v2_roman = _is_roman_script(s2)

    # Detect cross-script: one is Urdu-only, the other is Roman-only
    cross_script = (
        (v1_urdu and not v1_roman and v2_roman and not v2_urdu)
        or (v1_roman and not v1_urdu and v2_urdu and not v2_roman)
    )

    if cross_script:
        return {
            "status": "DIFFERENT_SCRIPT",
            "detail": f"'{val1}' vs '{val2}' — names are in different scripts, please verify manually",
            "similarity": None,
        }

    # Same script — use normal comparison
    return compare_values(val1, val2)


def get_field(doc: dict | None, field_path: str):
    """Get a nested field value from a document extraction using dot notation."""
    if doc is None:
        return None
    parts = field_path.split(".")
    val = doc
    for part in parts:
        if isinstance(val, list):
            try:
                val = val[int(part)]
            except (IndexError, ValueError):
                return None
        elif isinstance(val, dict):
            val = val.get(part)
        else:
            return None
    return val


def run_cross_checks(documents: dict) -> list[dict]:
    """
    Run all cross-document validations and return results.
    Returns 5 states: MATCH, SIMILAR, MISMATCH, NEEDS_REVIEW, DIFFERENT_SCRIPT.

    Args:
        documents: dict of doc_type → extracted_json
    """
    checks = []

    # 1. Father CNIC number (B-form vs Father CNIC card)
    checks.append({
        "label": "Father CNIC number (B-form vs CNIC)",
        "source": {"doc": "b_form", "field": "father_cnic_number"},
        "target": {"doc": "father_cnic", "field": "cnic_number"},
        **compare_values(
            normalize_numerals(get_field(documents.get("b_form"), "father_cnic_number")),
            normalize_numerals(get_field(documents.get("father_cnic"), "cnic_number")),
        ),
    })

    # 2. Mother CNIC number (B-form vs Mother CNIC card)
    checks.append({
        "label": "Mother CNIC number (B-form vs CNIC)",
        "source": {"doc": "b_form", "field": "mother_cnic_number"},
        "target": {"doc": "mother_cnic", "field": "cnic_number"},
        **compare_values(
            normalize_numerals(get_field(documents.get("b_form"), "mother_cnic_number")),
            normalize_numerals(get_field(documents.get("mother_cnic"), "cnic_number")),
        ),
    })

    # 3. Father name (B-form vs CNIC) — may be Urdu vs Roman script
    checks.append({
        "label": "Father name (B-form vs CNIC)",
        "source": {"doc": "b_form", "field": "father_name"},
        "target": {"doc": "father_cnic", "field": "name"},
        **compare_names(
            get_field(documents.get("b_form"), "father_name"),
            get_field(documents.get("father_cnic"), "name"),
        ),
    })

    # 4. Father name (B-form vs Death certificate) — may be Urdu vs Roman script
    checks.append({
        "label": "Father name (B-form vs Death cert)",
        "source": {"doc": "b_form", "field": "father_name"},
        "target": {"doc": "death_certificate", "field": "deceased_name"},
        **compare_names(
            get_field(documents.get("b_form"), "father_name"),
            get_field(documents.get("death_certificate"), "deceased_name"),
        ),
    })

    # 5. Photo quality check
    child_pic = documents.get("child_picture")
    if child_pic:
        quality = child_pic.get("quality_check")
        if quality and quality != "clear":
            checks.append({
                "label": "Child photo quality",
                "source": {"doc": "child_picture", "field": "quality_check"},
                "target": {"doc": "child_picture", "field": "quality_check"},
                "status": "MISMATCH" if quality == "face_not_visible" else "SIMILAR",
                "detail": f"Photo quality: {quality}",
                "similarity": 0.5 if quality == "blurry" else 0.2,
            })

    # 6. Cross-document routing mix-up: father_cnic and mother_cnic should
    #    not produce identical payloads (same CNIC, or same name+DOB).
    #    Signals come back as human-readable FLAG strings; convert each to a
    #    standard check entry so the frontend sees them alongside the others.
    father_doc = documents.get("father_cnic")
    mother_doc = documents.get("mother_cnic")
    for signal in compare_father_mother_cnic_extractions(father_doc, mother_doc):
        checks.append({
            "label": "Father/Mother CNIC routing mix-up",
            "source": {"doc": "father_cnic", "field": "_document"},
            "target": {"doc": "mother_cnic", "field": "_document"},
            "status": "NEEDS_REVIEW",
            "detail": signal,
            "similarity": None,
        })

    return checks