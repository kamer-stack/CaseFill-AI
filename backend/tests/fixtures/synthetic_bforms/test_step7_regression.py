"""Step-7 regression tests for deterministic pipeline stages.

These tests feed captured raw model outputs (from the 6 synthetic B-form
extraction runs) through postprocess_bform() and validate_extraction()
WITHOUT any API calls. They verify:

  1. Column-shift detection (mother/child name swap)
  2. Rule E false-positive behaviour when names are in Urdu script
  3. Consistency-check propagation (applicant != father CNIC)
  4. Null handling (mother cell empty)
  5. Validation error accumulation
  6. CNIC format validation

Run:
    cd backend && venv/Scripts/python.exe -m pytest \
        tests/fixtures/synthetic_bforms/test_step7_regression.py -v
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

_backend = str(Path(__file__).resolve().parents[3])
sys.path.insert(0, _backend)

from app.services.validation import (  # noqa: E402
    postprocess_bform,
    validate_extraction,
    validate_field,
    CNIC_RE,
)

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _load(test_id: str) -> dict:
    """Load the captured result JSON for a given test id."""
    p = RESULTS_DIR / f"test_{test_id}.json"
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ─── Helpers ──────────────────────────────────────────────────────────────

def _rerun_pipeline(record: dict) -> tuple[dict, dict]:
    """Re-run postprocess + validate on the raw_extracted from a record."""
    raw = copy.deepcopy(record["raw_extracted"])
    raw_text = record.get("raw_model_text", "")
    post = postprocess_bform(raw, raw_model_text=raw_text)
    val = validate_extraction("b_form", copy.deepcopy(post))
    return post, val


# ─── CNIC format ──────────────────────────────────────────────────────────

class TestCNICFormat:
    def test_valid_synthetic_cnic(self):
        assert CNIC_RE.match("99101-7111111-1")

    def test_rejects_child_reg_number(self):
        assert not CNIC_RE.match("99-2024-111111")

    def test_rejects_short(self):
        assert not CNIC_RE.match("99101-711111-1")

    def test_validate_field_cnic_valid(self):
        ok, err = validate_field("father_cnic_number", "99101-7111111-1")
        assert ok is True
        assert err is None

    def test_validate_field_cnic_invalid(self):
        ok, err = validate_field("father_cnic_number", "99-2024-111111")
        assert ok is False
        assert "CNIC" in err


# ─── Test A: All identities distinct ─────────────────────────────────────

class TestA_AllDistinct:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.record = _load("a")
        self.post, self.val = _rerun_pipeline(self.record)

    def test_no_column_corrections_for_mother_child_swap(self):
        """No mother↔child swap should be detected — model placed names correctly."""
        corrections = self.post.get("_column_corrections", [])
        swap_flags = [c for c in corrections if "mother_name" in c and "child" in c.lower()]
        assert len(swap_flags) == 0, f"Unexpected swap flag: {swap_flags}"

    def test_rule_e_false_positive_urdu_names(self):
        """Rule E fires because names are in Urdu, not Roman — documents the
        systematic false positive discovered during Step 7."""
        corrections = self.post.get("_column_corrections", [])
        rule_e_flags = [c for c in corrections if "FLAG father_name" in c or "FLAG mother_name" in c]
        # This assertion DOCUMENTS the current (incorrect) behavior.
        # When the model returns Urdu instead of Roman, Rule E fires.
        assert len(rule_e_flags) >= 2, (
            f"Expected Rule E false positives for Urdu-script names, got: {rule_e_flags}"
        )

    def test_cnic_confidence_preserved(self):
        """All CNICs were correctly read — confidence should remain at model value."""
        conf = self.val.get("confidence", {})
        assert conf.get("applicant_cnic_number") == 1.0
        assert conf.get("father_cnic_number") == 1.0
        assert conf.get("mother_cnic_number") == 1.0

    def test_consistency_check_agrees(self):
        """Applicant CNIC matches father CNIC — consistency check should report True."""
        raw = self.record["raw_extracted"]
        cc = raw.get("_consistency_check", {})
        assert cc.get("applicant_cnic_matches_father_cnic") is True


# ─── Test B: Column shift (mother/child) ─────────────────────────────────

class TestB_ColumnShift:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.record = _load("b")
        self.post, self.val = _rerun_pipeline(self.record)

    def test_model_put_child_name_in_mother_slot(self):
        """Raw model placed 'Saad Barkat' (child) in mother_name and
        'Hoorain Barkat' (actual mother) in child_name — column shift."""
        raw = self.record["raw_extracted"]
        assert raw.get("mother_name") is not None
        # The raw mother_name should NOT match the ground-truth mother name
        gt_mother = "Hoorain Barkat"
        raw_mother_urdu = raw.get("_raw_mother_name_urdu", "")
        # The raw Urdu echo for mother_name was 'سعد برکت' = Saad Barkat (the child)
        assert "سعد" in str(raw_mother_urdu), f"Expected child name in mother slot, got: {raw_mother_urdu}"

    def test_mother_cnic_contains_child_reg_number(self):
        """Raw model placed child reg number in mother_cnic_number slot."""
        raw = self.record["raw_extracted"]
        mother_cnic = raw.get("mother_cnic_number", "")
        # Should be a child reg format, not CNIC
        assert not CNIC_RE.match(str(mother_cnic)), (
            f"Expected child reg number in mother_cnic slot, got CNIC: {mother_cnic}"
        )

    def test_validation_flags_mother_cnic_format(self):
        """Validation should flag mother_cnic_number as invalid CNIC format."""
        errors = self.val.get("_validation_errors", [])
        mother_cnic_errors = [e for e in errors if e["field"] == "mother_cnic_number"]
        assert len(mother_cnic_errors) >= 1


# ─── Test C: Applicant != father ─────────────────────────────────────────

class TestC_ApplicantNotFather:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.record = _load("c")
        self.post, self.val = _rerun_pipeline(self.record)

    def test_consistency_check_reports_mismatch(self):
        """Model correctly identified applicant_cnic != father_cnic."""
        raw = self.record["raw_extracted"]
        cc = raw.get("_consistency_check", {})
        assert cc.get("applicant_cnic_matches_father_cnic") is False

    def test_postprocessor_flags_both_cnics(self):
        """Postprocessor should flag both applicant and father CNIC for review."""
        errors = self.val.get("_validation_errors", [])
        flagged_fields = {e["field"] for e in errors}
        assert "applicant_cnic_number" in flagged_fields
        assert "father_cnic_number" in flagged_fields

    def test_column_shift_mother_child_again(self):
        """Test C also exhibits mother↔child column shift."""
        raw = self.record["raw_extracted"]
        # mother_name in raw was 'یاس پرواز' = Yas(ir) Parwaz — the child name
        raw_mother_urdu = str(raw.get("_raw_mother_name_urdu", ""))
        assert "یاس" in raw_mother_urdu or "یاسر" in raw_mother_urdu, (
            f"Expected child name in mother slot, got: {raw_mother_urdu}"
        )


# ─── Test D: Visually similar names ──────────────────────────────────────

class TestD_SimilarNames:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.record = _load("d")
        self.post, self.val = _rerun_pipeline(self.record)

    def test_mother_name_distinct_from_father(self):
        """Model should produce distinct values for father and mother despite visual similarity."""
        raw = self.record["raw_extracted"]
        father = raw.get("father_name", "")
        mother = raw.get("mother_name", "")
        assert father != mother, "Father and mother names should be distinct"

    def test_column_headers_read_correctly(self):
        """Column headers should be correctly identified."""
        raw = self.record["raw_extracted"]
        headers = raw.get("_column_headers_read", {})
        # At least some headers should reference father/mother
        header_values = list(headers.values())
        has_father = any("والد" in str(v) for v in header_values)
        has_mother = any("والدہ" in str(v) for v in header_values)
        assert has_father, f"Missing father header in: {header_values}"
        assert has_mother, f"Missing mother header in: {header_values}"


# ─── Test E: Null mother cell ────────────────────────────────────────────

class TestE_NullMother:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.record = _load("e")
        self.post, self.val = _rerun_pipeline(self.record)

    def test_mother_name_is_null(self):
        """Empty cell should produce None."""
        raw = self.record["raw_extracted"]
        assert raw.get("mother_name") is None

    def test_mother_cnic_is_null(self):
        raw = self.record["raw_extracted"]
        assert raw.get("mother_cnic_number") is None

    def test_raw_mother_urdu_is_none(self):
        raw = self.record["raw_extracted"]
        assert raw.get("_raw_mother_name_urdu") is None

    def test_no_rule_e_false_positive_on_null(self):
        """Rule E should NOT fire when mother_name is null."""
        corrections = self.post.get("_column_corrections", [])
        mother_flags = [c for c in corrections if "FLAG mother_name" in c]
        assert len(mother_flags) == 0, f"Unexpected mother_name flag: {mother_flags}"

    def test_rule_e_false_positive_on_father_urdu(self):
        """Father name IS present in Urdu — Rule E still fires (documented false positive)."""
        corrections = self.post.get("_column_corrections", [])
        father_flags = [c for c in corrections if "FLAG father_name" in c]
        assert len(father_flags) >= 1, "Expected Rule E false positive on Urdu father_name"

    def test_all_cnic_correct(self):
        """All CNIC values should match ground truth."""
        raw = self.record["raw_extracted"]
        assert raw.get("applicant_cnic_number") == "99501-7999999-9"
        assert raw.get("father_cnic_number") == "99501-7999999-9"


# ─── Test F: 3 children (historical failure mirror) ──────────────────────

class TestF_ThreeChildren:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.record = _load("f")
        self.post, self.val = _rerun_pipeline(self.record)

    def test_three_children_extracted(self):
        """Model should extract 3 child rows."""
        raw = self.record["raw_extracted"]
        children = raw.get("children", [])
        assert len(children) == 3

    def test_child_names_distinct(self):
        """No duplicate child names — Rule F should NOT fire."""
        raw = self.record["raw_extracted"]
        children = raw.get("children", [])
        names = [c.get("child_name") for c in children if isinstance(c, dict)]
        non_null = [n for n in names if n]
        assert len(set(non_null)) == len(non_null), f"Duplicate names: {non_null}"

    def test_no_rule_f_flag(self):
        """Rule F (duplicate sibling names) should NOT fire."""
        corrections = self.post.get("_column_corrections", [])
        rule_f = [c for c in corrections if "FLAG child_name" in c and "identical" in c.lower()]
        assert len(rule_f) == 0

    def test_mother_name_is_first_child_name(self):
        """Column shift: mother_name = Rehan Ihtisham (first child's name)."""
        raw = self.record["raw_extracted"]
        mother_name = raw.get("mother_name", "")
        first_child_name = raw.get("children", [{}])[0].get("child_name", "")
        assert mother_name == first_child_name, (
            f"Expected mother_name ({mother_name}) to equal first child name ({first_child_name})"
        )

    def test_mother_cnic_is_first_child_reg(self):
        """Column shift: mother_cnic = first child's registration number."""
        raw = self.record["raw_extracted"]
        mother_cnic = raw.get("mother_cnic_number", "")
        first_child_reg = raw.get("children", [{}])[0].get("child_registration_number", "")
        assert mother_cnic == first_child_reg, (
            f"Expected mother_cnic ({mother_cnic}) to equal first child reg ({first_child_reg})"
        )

    def test_child_registration_numbers_correct_format(self):
        """Child registration numbers should match expected format."""
        raw = self.record["raw_extracted"]
        children = raw.get("children", [])
        for child in children:
            reg = child.get("child_registration_number", "")
            assert "99-2024-" in str(reg), f"Unexpected reg format: {reg}"

    def test_all_dates_correct(self):
        """All child DOBs should match ground truth."""
        val = self.val
        children = val.get("children", [])
        expected_dobs = ["12-04-2016", "08-01-2019", "30-06-2022"]
        for i, child in enumerate(children):
            if i < len(expected_dobs):
                assert child.get("date_of_birth") == expected_dobs[i], (
                    f"Child {i} DOB mismatch: {child.get('date_of_birth')} != {expected_dobs[i]}"
                )


# ─── Cross-cutting: Rule E systematic false positive ─────────────────────

class TestRuleESystematicFalsePositive:
    """Documents the systematic Rule E false positive across all tests
    where names are returned in Urdu script instead of Roman."""

    @pytest.mark.parametrize("test_id", ["a", "b", "c", "d", "e", "f"])
    def test_rule_e_fires_on_urdu_names(self, test_id):
        """For every test with a non-null father_name in Urdu, Rule E fires
        because the check compares Urdu-vs-Roman transliteration."""
        record = _load(test_id)
        post, _ = _rerun_pipeline(record)
        corrections = post.get("_column_corrections", [])
        father_flags = [c for c in corrections if "FLAG father_name" in c]

        raw = record["raw_extracted"]
        father_name = raw.get("father_name")
        if father_name is not None:
            assert len(father_flags) >= 1, (
                f"Test {test_id}: expected Rule E false positive on Urdu father_name, "
                f"got: {father_flags}"
            )


# ─── Cross-cutting: CRC number order reversal ────────────────────────────

class TestCRCOrderReversal:
    """Documents the systematic CRC group-order reversal."""

    @pytest.mark.parametrize("test_id,expected_gt", [
        ("a", "99-TEST-A-2024"),
        ("b", "99-TEST-B-2024"),
        ("c", "99-TEST-C-2024"),
        ("d", "99-TEST-D-2024"),
        ("e", "99-TEST-E-2024"),
        ("f", "99-TEST-F-2024"),
    ])
    def test_crc_group_order_reversed(self, test_id, expected_gt):
        """Model consistently reverses CRC group order (RTL reading)."""
        record = _load(test_id)
        raw = record["raw_extracted"]
        got_crc = raw.get("crc_number", "")
        # Document the reversal rather than assert exact match
        assert got_crc != expected_gt, (
            f"Expected CRC to be reversed, but got exact match: {got_crc}"
        )


# ─── Cross-cutting: child reg number digit drop ──────────────────────────

class TestChildRegDigitDrop:
    """Documents the systematic child registration number digit loss."""

    @pytest.mark.parametrize("test_id,expected_gt", [
        ("a", "99-2024-111111"),
        ("e", "99-2024-999999"),
    ])
    def test_child_reg_missing_digit(self, test_id, expected_gt):
        """Model drops one digit from child registration numbers."""
        record = _load(test_id)
        raw = record["raw_extracted"]
        children = raw.get("children", [])
        if children:
            got = children[0].get("child_registration_number", "")
            assert len(str(got)) < len(expected_gt), (
                f"Expected digit drop, but got full length: {got}"
            )


# ─── Deterministic validation logic ──────────────────────────────────────

class TestValidationDeterministic:
    """Pure validation tests — no postprocessing, no API."""

    def test_empty_value_passes(self):
        ok, err = validate_field("father_name", None)
        assert ok is True

    def test_empty_string_passes(self):
        ok, err = validate_field("father_name", "")
        assert ok is True

    def test_name_with_digits_fails(self):
        ok, err = validate_field("father_name", "John123")
        assert ok is False

    def test_name_urdu_passes(self):
        ok, err = validate_field("father_name", "شفیق الرحمن")
        assert ok is True

    def test_date_valid(self):
        ok, err = validate_field("date_of_birth", "15-03-2018")
        assert ok is True

    def test_date_future_fails(self):
        ok, err = validate_field("date_of_birth", "15-03-2099")
        assert ok is False

    def test_date_bad_format(self):
        ok, err = validate_field("date_of_birth", "2018-03-15")
        assert ok is False

    def test_education_enum_valid(self):
        ok, err = validate_field("education_level", "matric")
        assert ok is True

    def test_education_enum_invalid(self):
        ok, err = validate_field("education_level", "phd")
        assert ok is False

    def test_grade_percentage(self):
        ok, err = validate_field("result_percentage_or_grade", "85")
        assert ok is True

    def test_grade_letter(self):
        ok, err = validate_field("result_percentage_or_grade", "A+")
        assert ok is True

    def test_year_valid(self):
        ok, err = validate_field("year", "2024")
        assert ok is True

    def test_year_range_valid(self):
        ok, err = validate_field("year", "2024-2025")
        assert ok is True

    def test_year_invalid(self):
        ok, err = validate_field("year", "abc")
        assert ok is False
