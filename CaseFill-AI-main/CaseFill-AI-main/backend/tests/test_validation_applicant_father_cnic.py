"""
Regression test for the applicant/father CNIC auto-correction bug.

The old `postprocess_bform()` logic silently overwrote `applicant_cnic_number`
with `father_cnic_number` whenever the model's own `_consistency_check`
reported `applicant_cnic_matches_father_cnic == False`. That assumption is
invalid when the father is deceased and the mother is the applicant — the
program's primary use case — and silently corrupted a correctly-extracted
field while labeling the corruption as a "recovery."

The fix preserves both extracted values exactly as read, appends a single
FLAG correction covering both fields, and forces confidence to 0 on both.

CASE A: mother is the applicant, father is deceased
    - father_cnic = Father's CNIC (correctly extracted)
    - applicant_cnic = Mother's CNIC (correctly extracted, different from father)
    - consistency check reports mismatch
    Expected:
      - father_cnic_number unchanged
      - applicant_cnic_number unchanged
      - confidence zeroed on both
      - a FLAG correction string is emitted
      - NO auto-overwrite

CASE B: father is the applicant (the common case)
    - father_cnic = Father's CNIC
    - applicant_cnic = Father's CNIC (same value)
    - consistency check reports match
    Expected:
      - both values unchanged
      - no new FLAG correction emitted for these fields
      - confidence not zeroed by the consistency-check branch
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make `backend/app` importable without installing the package.
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.validation import (  # noqa: E402
    postprocess_bform,
    validate_extraction,
)


FATHER_CNIC = "12345-6789012-3"
MOTHER_CNIC = "98765-4321098-7"


def _make_bform_result(
    *,
    applicant_cnic: str,
    father_cnic: str,
    consistency_match: bool,
    applicant_conf: float = 0.8,
    father_conf: float = 0.8,
) -> dict:
    return {
        "applicant_cnic_number": applicant_cnic,
        "father_cnic_number": father_cnic,
        "mother_cnic_number": "11111-2222222-3",
        "mother_name": "Some Mother",
        "_raw_mother_name_urdu": "some mother",
        "children": [
            {
                "serial_number": "1",
                "child_name": "Child One",
                "child_registration_number": "2024-0001",
            }
        ],
        "confidence": {
            "applicant_cnic_number": applicant_conf,
            "father_cnic_number": father_conf,
            "mother_cnic_number": 0.8,
            "mother_name": 0.9,
            "children": [{"child_name": 0.9, "child_registration_number": 0.9}],
        },
        "_consistency_check": {
            "applicant_cnic_matches_father_cnic": consistency_match,
        },
    }


def _has_applicant_father_flag(corrections: list[str]) -> bool:
    return any(
        "FLAG applicant_cnic_number/father_cnic_number" in c for c in corrections
    )


# ── CASE A: mismatch (mother is the applicant) ───────────────────────────────

def test_case_a_no_auto_overwrite():
    """When the consistency check reports a mismatch, neither value is changed."""
    result = _make_bform_result(
        applicant_cnic=MOTHER_CNIC,
        father_cnic=FATHER_CNIC,
        consistency_match=False,
    )
    postprocess_bform(result)

    assert result["father_cnic_number"] == FATHER_CNIC, (
        "father_cnic_number must be preserved exactly as extracted"
    )
    assert result["applicant_cnic_number"] == MOTHER_CNIC, (
        "applicant_cnic_number must NOT be overwritten with father_cnic_number; "
        "the applicant may legitimately be the mother"
    )


def test_case_a_flag_emitted():
    """A mismatch produces exactly one FLAG correction covering both fields."""
    result = _make_bform_result(
        applicant_cnic=MOTHER_CNIC,
        father_cnic=FATHER_CNIC,
        consistency_match=False,
    )
    postprocess_bform(result)
    corrections = result.get("_column_corrections", [])

    assert _has_applicant_father_flag(corrections), (
        f"expected a FLAG applicant_cnic_number/father_cnic_number correction, "
        f"got: {corrections}"
    )
    # Must NOT be labeled as a recovery — no silent overwrite happened.
    assert not any(c.startswith("Recovered") for c in corrections), (
        "the old 'Recovered applicant_cnic_number=...' correction must no "
        "longer be emitted; the fix removes the overwrite"
    )


def test_case_a_both_confidences_zeroed():
    """Both CNIC confidences are forced to 0 on a mismatch flag."""
    result = _make_bform_result(
        applicant_cnic=MOTHER_CNIC,
        father_cnic=FATHER_CNIC,
        consistency_match=False,
        applicant_conf=0.9,
        father_conf=0.9,
    )
    postprocess_bform(result)
    conf = result["confidence"]

    assert conf["father_cnic_number"] == 0, (
        "father_cnic_number confidence must be 0 after the mismatch flag"
    )
    assert conf["applicant_cnic_number"] == 0, (
        "applicant_cnic_number confidence must be 0 after the mismatch flag; "
        "the old code raised it to 0.5 while silently overwriting the value"
    )


def test_case_a_validate_extraction_surfaces_both_fields():
    """validate_extraction turns the compound FLAG into validation errors on both fields."""
    result = _make_bform_result(
        applicant_cnic=MOTHER_CNIC,
        father_cnic=FATHER_CNIC,
        consistency_match=False,
    )
    postprocess_bform(result)
    validate_extraction("b_form", result)

    flagged_fields = [e["field"] for e in result["_validation_errors"]]
    assert "father_cnic_number" in flagged_fields, (
        f"father_cnic_number must appear in _validation_errors, got {flagged_fields}"
    )
    assert "applicant_cnic_number" in flagged_fields, (
        f"applicant_cnic_number must appear in _validation_errors, got {flagged_fields}"
    )


# ── CASE B: match (father is the applicant, the common case) ─────────────────

def test_case_b_no_flag_when_match():
    """A consistency-check match must not emit the applicant/father FLAG."""
    result = _make_bform_result(
        applicant_cnic=FATHER_CNIC,
        father_cnic=FATHER_CNIC,
        consistency_match=True,
    )
    postprocess_bform(result)
    corrections = result.get("_column_corrections", [])

    assert not _has_applicant_father_flag(corrections), (
        "no applicant/father FLAG should be emitted when the values match; "
        f"got: {corrections}"
    )


def test_case_b_values_unchanged_and_confidence_not_zeroed():
    """A consistency-check match leaves values and confidences alone."""
    result = _make_bform_result(
        applicant_cnic=FATHER_CNIC,
        father_cnic=FATHER_CNIC,
        consistency_match=True,
        applicant_conf=0.85,
        father_conf=0.85,
    )
    postprocess_bform(result)

    assert result["applicant_cnic_number"] == FATHER_CNIC
    assert result["father_cnic_number"] == FATHER_CNIC

    conf = result["confidence"]
    # The CNIC floor recalibration may lift these, but it must never zero them
    # when no flag has fired.
    assert conf["applicant_cnic_number"] > 0
    assert conf["father_cnic_number"] > 0


# ── Extra safety: mismatch with an INVALID father CNIC still flags, never fixes ─

def test_case_a_invalid_father_cnic_still_flags_no_overwrite():
    """Even when father_cnic is malformed, a mismatch must flag, not fix."""
    bad_father = "NOT-A-CNIC"
    result = _make_bform_result(
        applicant_cnic=MOTHER_CNIC,
        father_cnic=bad_father,
        consistency_match=False,
    )
    postprocess_bform(result)

    assert result["father_cnic_number"] == bad_father
    assert result["applicant_cnic_number"] == MOTHER_CNIC
    assert _has_applicant_father_flag(result.get("_column_corrections", []))
    # Both confidences still zeroed regardless of format validity.
    assert result["confidence"]["father_cnic_number"] == 0
    assert result["confidence"]["applicant_cnic_number"] == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
