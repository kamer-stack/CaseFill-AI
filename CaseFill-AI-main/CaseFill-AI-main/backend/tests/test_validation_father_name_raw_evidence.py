"""
Regression tests for Rule E (father) — the raw-Urdu echo-back check that
mirrors the existing Rule E for mother_name.

The observed hallucination case produced father_name = "Muhammad Aslam"
from a cell that actually read "اشتیاق احمد مغل" (Ishtiaq Ahmed Mughal).
The mother_name field had this defense already; the father_name field did
not. This suite verifies that father_name now has the same symmetric
raw-evidence check.

Pipeline path under test:
    postprocess_bform(result, raw_model_text=...)
        └─ Rule E (father): compare father_name to
           transliterate_urdu_to_roman(_raw_father_name_urdu);
           flag + zero confidence when similarity < 0.6
        └─ Fallback: when _raw_father_name_urdu is missing, check that
           father_name appears verbatim in raw_model_text; flag + zero
           confidence when it does not.

    validate_extraction("b_form", result)
        └─ surfaces "FLAG father_name" corrections as father_name
           entries in _validation_errors
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.validation import (  # noqa: E402
    postprocess_bform,
    validate_extraction,
)
from app.services.transliterate import transliterate_urdu_to_roman  # noqa: E402


# ── Fixtures ──────────────────────────────────────────────────────────────────

# "اشتیاق احمد مغل" transliterates to roughly "Ishtiaq Ahmad Mughal" — used
# as the ground-truth father name on the form.
GROUND_TRUTH_URDU = "اشتیاق احمد مغل"
GROUND_TRUTH_ROMAN = transliterate_urdu_to_roman(GROUND_TRUTH_URDU)

# The exact hallucinated name from the reported failure case.
HALLUCINATED_ROMAN = "Muhammad Aslam"


def _make_bform_result(
    *,
    father_name: str | None,
    raw_father_urdu: str | None,
    mother_name: str = "Some Mother",
    raw_mother_urdu: str = "some mother",
) -> dict:
    return {
        "father_name": father_name,
        "father_cnic_number": "12345-6789012-3",
        "mother_name": mother_name,
        "mother_cnic_number": "11111-2222222-3",
        "applicant_cnic_number": "12345-6789012-3",
        "_raw_father_name_urdu": raw_father_urdu,
        "_raw_mother_name_urdu": raw_mother_urdu,
        "children": [],
        "confidence": {
            "father_name": 0.9,
            "father_cnic_number": 0.8,
            "mother_name": 0.9,
            "mother_cnic_number": 0.8,
            "applicant_cnic_number": 0.8,
            "children": [],
        },
    }


# ── CASE 1: raw Urdu evidence supports the extracted father name ─────────────

def test_supported_father_name_is_not_flagged():
    """A faithful transliteration of the raw Urdu must pass without a flag."""
    result = _make_bform_result(
        father_name=GROUND_TRUTH_ROMAN,
        raw_father_urdu=GROUND_TRUTH_URDU,
    )
    postprocess_bform(result)
    corrections = result.get("_column_corrections", [])

    assert not any("FLAG father_name" in c for c in corrections), (
        f"faithful transliteration should not be flagged; got: {corrections}"
    )
    assert result["confidence"]["father_name"] > 0, (
        "faithful transliteration must retain nonzero confidence"
    )


def test_supported_father_name_accepts_minor_transliteration_variance():
    """Small spelling differences in Roman output must not trigger the 0.6 threshold."""
    # Same Urdu source, two plausible Roman spellings that are close.
    result = _make_bform_result(
        father_name=GROUND_TRUTH_ROMAN.replace("Ahmad", "Ahmed"),
        raw_father_urdu=GROUND_TRUTH_URDU,
    )
    postprocess_bform(result)
    corrections = result.get("_column_corrections", [])
    assert not any("FLAG father_name" in c for c in corrections), (
        f"minor Roman variance should not flag; got: {corrections}"
    )


# ── CASE 2: missing / null / empty raw Urdu evidence ─────────────────────────

def test_missing_raw_urdu_no_raw_text_falls_through_cleanly():
    """
    When _raw_father_name_urdu is null AND no raw_model_text is supplied,
    the father name is neither flagged nor zeroed by this rule. The
    defense requires at least one evidence source; absent both, it abstains.
    """
    result = _make_bform_result(
        father_name=HALLUCINATED_ROMAN,
        raw_father_urdu=None,
    )
    postprocess_bform(result)
    corrections = result.get("_column_corrections", [])
    assert not any("FLAG father_name" in c for c in corrections), (
        "with neither raw urdu nor raw_model_text, the rule must abstain "
        f"(no evidence to flag on); got: {corrections}"
    )


def test_missing_raw_urdu_with_raw_text_that_contains_name_passes():
    """Fallback path: raw_model_text contains father_name verbatim → no flag."""
    result = _make_bform_result(
        father_name=HALLUCINATED_ROMAN,
        raw_father_urdu=None,
    )
    postprocess_bform(
        result,
        raw_model_text=f'{{"father_name": "{HALLUCINATED_ROMAN}", "other": "fields"}}',
    )
    corrections = result.get("_column_corrections", [])
    assert not any("FLAG father_name" in c for c in corrections), (
        "verbatim presence in raw_model_text should not flag; got: {corrections}"
    )


def test_missing_raw_urdu_with_raw_text_that_does_not_contain_name_flags():
    """Fallback path: raw_model_text lacks father_name verbatim → flag + zero."""
    result = _make_bform_result(
        father_name=HALLUCINATED_ROMAN,
        raw_father_urdu=None,
    )
    postprocess_bform(
        result,
        raw_model_text='{"father_name": "something-else", "other": "fields"}',
    )
    corrections = result.get("_column_corrections", [])

    assert any("FLAG father_name" in c for c in corrections), (
        "father_name not present verbatim in raw_model_text must be flagged; "
        f"got: {corrections}"
    )
    assert result["confidence"]["father_name"] == 0, (
        "unsupported father_name must have confidence forced to 0"
    )


def test_empty_raw_urdu_is_treated_as_missing():
    """An empty-string _raw_father_name_urdu is treated as absent, not as evidence."""
    result = _make_bform_result(
        father_name=HALLUCINATED_ROMAN,
        raw_father_urdu="",
    )
    # With no raw_model_text, the rule abstains — same as the None case.
    postprocess_bform(result)
    assert not any(
        "FLAG father_name" in c for c in result.get("_column_corrections", [])
    )


# ── CASE 3: raw Urdu evidence does NOT support the extracted father name ─────

def test_unsupported_father_name_is_flagged_and_zeroed():
    """
    The exact observed failure: model emits "Muhammad Aslam" while the
    cell actually reads "اشتیاق احمد مغل". The check must flag and
    zero confidence — it must NOT silently accept the plausible-looking
    Roman name.
    """
    result = _make_bform_result(
        father_name=HALLUCINATED_ROMAN,
        raw_father_urdu=GROUND_TRUTH_URDU,
    )
    postprocess_bform(result)
    corrections = result.get("_column_corrections", [])

    father_flags = [c for c in corrections if "FLAG father_name" in c]
    assert father_flags, (
        "a Roman name unsupported by the raw Urdu echo must be flagged; "
        f"got corrections: {corrections}"
    )
    assert result["confidence"]["father_name"] == 0, (
        "unsupported father_name must have confidence forced to 0"
    )
    assert result["father_name"] == HALLUCINATED_ROMAN, (
        "the raw value must be preserved for FSO review (no silent deletion/rewrite)"
    )


def test_completely_unrelated_urdu_flags():
    """A totally unrelated Urdu string (e.g. a common female name) must flag."""
    result = _make_bform_result(
        father_name=HALLUCINATED_ROMAN,
        raw_father_urdu="عائشہ بی بی",  # "Ayesha Bibi" — a different person entirely
    )
    postprocess_bform(result)
    assert any(
        "FLAG father_name" in c for c in result.get("_column_corrections", [])
    )
    assert result["confidence"]["father_name"] == 0


def test_unsupported_father_name_surfaces_in_validation_errors():
    """validate_extraction must surface FLAG father_name as a father_name error."""
    result = _make_bform_result(
        father_name=HALLUCINATED_ROMAN,
        raw_father_urdu=GROUND_TRUTH_URDU,
    )
    postprocess_bform(result)
    validate_extraction("b_form", result)

    flagged_fields = [e["field"] for e in result["_validation_errors"]]
    assert "father_name" in flagged_fields, (
        f"father_name must appear in _validation_errors, got {flagged_fields}"
    )


def test_mother_name_check_still_works_independently():
    """The existing mother_name Rule E must still fire on its own bad inputs."""
    result = _make_bform_result(
        father_name=GROUND_TRUTH_ROMAN,
        raw_father_urdu=GROUND_TRUTH_URDU,
        mother_name="Zahida Begum",
        raw_mother_urdu="عائشہ بی بی",
    )
    postprocess_bform(result)
    corrections = result.get("_column_corrections", [])
    assert any("FLAG mother_name" in c for c in corrections), (
        "mother_name Rule E must still fire independently; got: {corrections}"
    )
    assert result["confidence"]["mother_name"] == 0
    # Father side is supported — must NOT be flagged.
    assert not any("FLAG father_name" in c for c in corrections)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
