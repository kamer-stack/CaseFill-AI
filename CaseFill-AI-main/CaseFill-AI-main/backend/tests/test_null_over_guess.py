"""
Regression tests for Step 4 — NULL-OVER-GUESS on B-form fields.

The architecture review identified that the postprocessor used to
"recover" missing or invalid parent CNICs from per-row values emitted
inside the children array, and to relocate displaced child registration
numbers to arbitrary child rows. All of these are GUESSES: the pipeline
has no independent evidence of which row held which value, so
reconstruction amounts to inventing data.

Step 4 enforces the principle:

    no independent evidence → no invented value

For every B-form field:
    * clearly visible → extract
    * partially visible but enough evidence → extract only what's supported
    * genuinely unreadable / absent → null + confidence 0

The postprocessor now:
    * NEVER assigns a parent CNIC from per-row values to an empty or
      invalid top-level parent slot.
    * NEVER relocates a "displaced" child registration number into an
      arbitrary child row.
    * NEVER assigns a constant-across-rows CNIC to a parent slot via the
      old `_parent_for_constant` heuristic.
    * Still performs a DETERMINISTIC swap when every child row carries
      the same valid CNIC as the top-level parent slot (an unambiguous
      structural column swap).

The prompt now includes an explicit NULL-OVER-GUESS principle and
per-field null fallbacks for applicant_name, applicant_cnic_number,
crc_number, child_name, and child_registration_number. Prompt-level
behavior cannot be unit-tested without a live VLM; these tests verify
the postprocessor's side of the contract.
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
    validate_field,
)


FATHER_CNIC = "12345-6789012-3"
MOTHER_CNIC = "98765-4321098-7"
THIRD_CNIC = "55555-1234567-0"


def _make_bform(
    *,
    father_cnic: str | None = FATHER_CNIC,
    mother_cnic: str | None = MOTHER_CNIC,
    applicant_cnic: str | None = FATHER_CNIC,
    father_name: str | None = "Ishtiaq Ahmed Mughal",
    mother_name: str | None = "Ayesha Bibi",
    children: list[dict] | None = None,
) -> dict:
    if children is None:
        children = [
            {
                "serial_number": "1",
                "child_name": "Child One",
                "child_registration_number": "2024-0001",
            }
        ]
    return {
        "crc_number": "CRC-12345",
        "applicant_name": "Some Applicant",
        "applicant_cnic_number": applicant_cnic,
        "father_name": father_name,
        "father_cnic_number": father_cnic,
        "mother_name": mother_name,
        "mother_cnic_number": mother_cnic,
        "_raw_father_name_urdu": "اشتیاق احمد مغل" if father_name else None,
        "_raw_mother_name_urdu": "عائشہ بی بی" if mother_name else None,
        "children": children,
        "confidence": {
            "crc_number": 0.9,
            "applicant_name": 0.9,
            "applicant_cnic_number": 0.9 if applicant_cnic else 0,
            "father_name": 0.9 if father_name else 0,
            "father_cnic_number": 0.9 if father_cnic else 0,
            "mother_name": 0.9 if mother_name else 0,
            "mother_cnic_number": 0.9 if mother_cnic else 0,
            "children": [
                {
                    "child_name": 0.9 if c.get("child_name") else 0,
                    "child_registration_number": 0.9 if c.get("child_registration_number") else 0,
                }
                for c in children
            ],
        },
    }


# ── 1. Unreadable / null names remain null ──────────────────────────────────


def test_unreadable_father_name_remains_null():
    """postprocess_bform must not invent a father_name when it is null."""
    result = _make_bform(father_name=None)
    postprocess_bform(result)
    assert result["father_name"] is None, (
        "null father_name must stay null; postprocessor must not guess"
    )
    assert result["confidence"]["father_name"] == 0
    assert not any(
        c.startswith("Recovered") for c in result.get("_column_corrections", [])
    )


def test_unreadable_mother_name_remains_null():
    """postprocess_bform must not invent a mother_name when it is null."""
    result = _make_bform(mother_name=None)
    postprocess_bform(result)
    assert result["mother_name"] is None
    assert result["confidence"]["mother_name"] == 0
    assert not any(
        c.startswith("Recovered") for c in result.get("_column_corrections", [])
    )


def test_unreadable_child_name_remains_null():
    """A null child_name on a single row must pass validation unchanged."""
    result = _make_bform(
        children=[
            {
                "serial_number": "1",
                "child_name": None,
                "child_registration_number": "2024-0001",
            }
        ]
    )
    postprocess_bform(result)
    validate_extraction("b_form", result)

    assert result["children"][0]["child_name"] is None, (
        "null child_name must stay null; postprocessor must not guess a sibling name"
    )
    # No validation error should fire for a nulled-out name.
    name_errors = [
        e for e in result["_validation_errors"] if e["field"].endswith(".child_name")
    ]
    assert name_errors == []


# ── 2. Unclear parent CNICs are not reconstructed from other CNICs ──────────


def test_empty_father_cnic_not_reconstructed_from_mother_or_applicant():
    """Empty father_cnic_number must stay empty; no inference from other CNICs."""
    result = _make_bform(
        father_cnic=None,
        mother_cnic=MOTHER_CNIC,
        applicant_cnic=FATHER_CNIC,
    )
    postprocess_bform(result)

    assert result["father_cnic_number"] is None, (
        "empty father_cnic_number must not be filled from applicant or mother CNIC"
    )
    assert not any(
        c.startswith("Recovered") for c in result.get("_column_corrections", [])
    ), "no 'Recovered father_cnic_number=...' correction may be emitted"
    assert not any(
        c.startswith("Corrected") for c in result.get("_column_corrections", [])
    ), "no 'Corrected father_cnic_number' correction may be emitted"


def test_invalid_father_cnic_not_reconstructed_from_per_row_values():
    """An invalid-format father_cnic must not be replaced with a per-row CNIC."""
    bad_value = "NOT-A-CNIC"
    result = _make_bform(
        father_cnic=bad_value,
        children=[
            {
                "serial_number": "1",
                "child_name": "A",
                "child_registration_number": "2024-0001",
                # Per-row father_cnic emitted by the model — the old code
                # would have promoted this to the top-level slot.
                "father_cnic_number": FATHER_CNIC,
            }
        ],
    )
    postprocess_bform(result)

    assert result["father_cnic_number"] == bad_value, (
        "invalid top-level father_cnic must NOT be replaced from per-row data; "
        "the pipeline has no independent evidence of the correct value"
    )
    assert not any(
        c.startswith("Corrected") for c in result.get("_column_corrections", [])
    )
    # The field must be flagged for FSO review, since it's unreadable/invalid.
    assert any(
        "FLAG father_cnic_number" in c for c in result.get("_column_corrections", [])
    )


def test_empty_applicant_cnic_not_reconstructed_from_father():
    """Empty applicant_cnic_number must stay empty; no inference from father_cnic."""
    result = _make_bform(
        applicant_cnic=None,
        father_cnic=FATHER_CNIC,
    )
    postprocess_bform(result)

    assert result["applicant_cnic_number"] is None, (
        "empty applicant_cnic must NOT be filled from father_cnic; applicant may "
        "legitimately be the mother or another guardian"
    )
    assert not any(
        c.startswith("Recovered") for c in result.get("_column_corrections", [])
    )


def test_constant_child_reg_not_assigned_to_parent_via_heuristic():
    """
    When every child row carries the same valid CNIC but neither top-level
    parent slot currently matches it, the postprocessor must NOT guess
    which parent slot (mother vs father) the constant belongs to.
    """
    mystery_cnic = "77777-7777777-7"
    result = _make_bform(
        father_cnic=None,
        mother_cnic=None,
        applicant_cnic=None,
        children=[
            {"serial_number": "1", "child_name": "A", "child_registration_number": mystery_cnic},
            {"serial_number": "2", "child_name": "B", "child_registration_number": mystery_cnic},
        ],
    )
    postprocess_bform(result)

    assert result["father_cnic_number"] is None, (
        "father_cnic must stay null — the constant child-reg CNIC cannot be "
        "assigned via the old _parent_for_constant heuristic"
    )
    assert result["mother_cnic_number"] is None
    assert not any(
        c.startswith("Recovered") for c in result.get("_column_corrections", [])
    )
    # The contamination IS flagged for FSO review.
    assert any(
        "FLAG child_registration_number" in c and "every row" in c
        for c in result.get("_column_corrections", [])
    )


def test_no_displaced_child_reg_placed_in_arbitrary_row():
    """
    Even when a swap is deterministic (every row held the parent CNIC),
    the postprocessor must NOT guess which child row the displaced
    child_registration_number belongs to — it clears the rows instead.
    """
    result = _make_bform(
        father_cnic=FATHER_CNIC,
        children=[
            {"serial_number": "1", "child_name": "A", "child_registration_number": FATHER_CNIC},
            {"serial_number": "2", "child_name": "B", "child_registration_number": FATHER_CNIC},
        ],
    )
    postprocess_bform(result)

    # Every child row must be cleared (set to None), NOT populated with
    # some "displaced" value the postprocessor chose.
    for i, child in enumerate(result["children"]):
        assert child["child_registration_number"] is None, (
            f"row {i}: child_registration_number must be cleared, not guessed"
        )
    # And no "Placed displaced child reg#" correction may appear.
    assert not any(
        "Placed displaced child reg#" in c
        for c in result.get("_column_corrections", [])
    ), "postprocessor must not guess which child row receives a displaced reg#"


# ── 3. Clearly extracted values are NOT unnecessarily nulled ────────────────


def test_clearly_extracted_names_are_not_nulled():
    """Names that the model extracted verbatim must survive postprocessing unchanged."""
    result = _make_bform(
        father_name="Ishtiaq Ahmed Mughal",
        mother_name="Ayesha Bibi",
        children=[
            {"serial_number": "1", "child_name": "Child One", "child_registration_number": "2024-0001"},
            {"serial_number": "2", "child_name": "Child Two", "child_registration_number": "2024-0002"},
        ],
    )
    postprocess_bform(result)
    validate_extraction("b_form", result)

    assert result["father_name"] == "Ishtiaq Ahmed Mughal"
    assert result["mother_name"] == "Ayesha Bibi"
    assert result["children"][0]["child_name"] == "Child One"
    assert result["children"][1]["child_name"] == "Child Two"
    assert result["confidence"]["father_name"] > 0
    assert result["confidence"]["mother_name"] > 0


def test_clearly_extracted_cnic_is_not_nulled():
    """A valid, uncontested parent CNIC keeps its value and non-zero confidence."""
    result = _make_bform(
        father_cnic=FATHER_CNIC,
        mother_cnic=MOTHER_CNIC,
        applicant_cnic=FATHER_CNIC,
    )
    postprocess_bform(result)

    assert result["father_cnic_number"] == FATHER_CNIC
    assert result["mother_cnic_number"] == MOTHER_CNIC
    assert result["applicant_cnic_number"] == FATHER_CNIC
    assert result["confidence"]["father_cnic_number"] > 0
    assert result["confidence"]["mother_cnic_number"] > 0
    assert result["confidence"]["applicant_cnic_number"] > 0


def test_validate_field_accepts_null_for_all_bform_fields():
    """
    Null is a legitimate "unreadable" answer for every B-form field category.
    The validator must accept it (not reject as malformed).
    """
    for field in (
        "father_name", "mother_name", "applicant_name", "child_name",
        "father_cnic_number", "mother_cnic_number", "applicant_cnic_number",
        "child_registration_number", "crc_number",
        "date_of_birth",
    ):
        is_valid, err = validate_field(field, None)
        assert is_valid, f"null {field} should be valid, got error: {err}"
        assert err is None


def test_deterministic_constant_swap_still_works():
    """
    When every child row holds the SAME valid CNIC as the top-level
    parent slot, the structural swap is unambiguous and the
    postprocessor may (and should) clear the child rows. This is a
    deterministic correction, not a guess.
    """
    result = _make_bform(
        father_cnic=FATHER_CNIC,
        children=[
            {"serial_number": "1", "child_name": "A", "child_registration_number": FATHER_CNIC},
            {"serial_number": "2", "child_name": "B", "child_registration_number": FATHER_CNIC},
        ],
    )
    postprocess_bform(result)

    assert result["father_cnic_number"] == FATHER_CNIC, (
        "father CNIC at top level is preserved (every row held it)"
    )
    for child in result["children"]:
        assert child["child_registration_number"] is None, (
            "child rows must be cleared so the FSO re-reads Column 2"
        )
    assert any(
        c.startswith("Swapped") for c in result.get("_column_corrections", [])
    ), "the deterministic swap should still emit a 'Swapped' correction"


def test_partial_contamination_is_flagged_not_guessed():
    """
    When only SOME child rows carry the parent CNIC (not all), this is
    ambiguous contamination, not a clean swap. The postprocessor must
    flag without attempting recovery or relocation.
    """
    result = _make_bform(
        father_cnic=FATHER_CNIC,
        children=[
            {"serial_number": "1", "child_name": "A", "child_registration_number": FATHER_CNIC},
            {"serial_number": "2", "child_name": "B", "child_registration_number": "2024-0002"},
        ],
    )
    postprocess_bform(result)

    assert result["father_cnic_number"] == FATHER_CNIC, (
        "isolated-contamination guard must leave the parent CNIC untouched"
    )
    # Row 1 keeps its (likely-wrong) value — postprocessor does not
    # relocate; Rule G will flag the contamination separately.
    assert result["children"][0]["child_registration_number"] == FATHER_CNIC
    assert result["children"][1]["child_registration_number"] == "2024-0002"


# ── Regression: Step-1 and Step-3 tests still pass ─────────────────────────


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
