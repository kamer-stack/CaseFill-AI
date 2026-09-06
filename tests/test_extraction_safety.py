"""
Synthetic-fixture tests for the five extraction-safety fixes:

  1. Rule E — mother_name verbatim-source hallucination check
  2. Rule F — duplicate sibling names hard-fail
  3. Rule G — child registration number vs parent CNIC contamination
  4. Item 4 — CNIC confidence recalibration floor
  5. Item 5 — per-doc and cross-doc father/mother CNIC mix-up detection

Ground truth modeled on test_bform_v2.png:
  Father: Muhammad Aslam, CNIC 44444-4444444-4
  Mother: Ayesha Bibi,    CNIC 11111-1111111-1
  Child 1: Fatima Aslam,  serial 1, reg# 12345-6789012-3
  Child 2: Zainab Aslam,  serial 2, reg# 12345-6789012-4
"""

import sys, os
from unittest.mock import patch

_backend = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "backend")
sys.path.insert(0, os.path.normpath(_backend))

from app.services.validation import (
    postprocess_bform,
    postprocess_cnic,
    validate_extraction,
    compare_father_mother_cnic_extractions,
)
from app.services.cross_check import run_cross_checks


# ── Helpers ────────────────────────────────────────────────────────────────

def _base_bform(
    mother_name="Ayesha Bibi",
    child1_name="Fatima Aslam",
    child2_name="Zainab Aslam",
    child1_reg="12345-6789012-3",
    child2_reg="12345-6789012-4",
    father_cnic="44444-4444444-4",
    mother_cnic="11111-1111111-1",
):
    return {
        "crc_number": "CRC-2024-001",
        "applicant_name": "Muhammad Aslam",
        "applicant_cnic_number": father_cnic,
        "father_name": "Muhammad Aslam",
        "father_cnic_number": father_cnic,
        "mother_name": mother_name,
        "mother_cnic_number": mother_cnic,
        "children": [
            {
                "serial_number": 1,
                "child_name": child1_name,
                "child_registration_number": child1_reg,
                "gender_relation": "daughter",
                "date_of_birth": "15-03-2015",
                "remarks": "",
            },
            {
                "serial_number": 2,
                "child_name": child2_name,
                "child_registration_number": child2_reg,
                "gender_relation": "daughter",
                "date_of_birth": "20-07-2018",
                "remarks": "",
            },
        ],
        "confidence": {
            "crc_number": 0.9,
            "applicant_name": 0.9,
            "applicant_cnic_number": 0.9,
            "father_name": 0.9,
            "father_cnic_number": 0.9,
            "mother_name": 0.9,
            "mother_cnic_number": 0.9,
            "children": [
                {
                    "serial_number": 0.9,
                    "child_name": 0.9,
                    "child_registration_number": 0.9,
                    "gender_relation": 0.9,
                    "date_of_birth": 0.9,
                    "remarks": 0.9,
                },
                {
                    "serial_number": 0.9,
                    "child_name": 0.9,
                    "child_registration_number": 0.9,
                    "gender_relation": 0.9,
                    "date_of_birth": 0.9,
                    "remarks": 0.9,
                },
            ],
        },
    }


def _base_cnic(doc_type="father_cnic", name="Muhammad Aslam", cnic="44444-4444444-4"):
    key = "father_name" if doc_type == "father_cnic" else "father_or_husband_name"
    return {
        "name": name,
        key: "Some Parent Name",
        "cnic_number": cnic,
        "date_of_birth": "01-01-1980",
        "confidence": {
            "name": 0.9,
            key: 0.8,
            "cnic_number": 0.5,
            "date_of_birth": 0.8,
        },
    }


# ── Rule E: mother_name transliteration consistency ────────────────────────

@patch("app.services.validation.transliterate_urdu_to_roman")
def test_rule_e_hallucinated_mother_name(mock_translit):
    """Model constructs a name that doesn't match the Urdu echo."""
    mock_translit.return_value = "Ayesha Bibi"
    data = _base_bform(mother_name="Zahida Begum")
    data["_raw_mother_name_urdu"] = "عائشہ بی بی"
    raw_text = '{"mother_name": "Zahida Begum", "_raw_mother_name_urdu": "عائشہ بی بی"}'
    result = postprocess_bform(data, raw_model_text=raw_text)
    flags = [c for c in result["_column_corrections"] if "FLAG mother_name" in c]
    assert flags, "Rule E should flag when mother_name doesn't match transliteration of Urdu echo"
    assert result["confidence"]["mother_name"] == 0, "confidence should be zeroed"


@patch("app.services.validation.transliterate_urdu_to_roman")
def test_rule_e_passes_when_transliteration_matches(mock_translit):
    """Transliteration of Urdu echo matches the Roman name — no flag."""
    mock_translit.return_value = "Ayesha Bibi"
    data = _base_bform(mother_name="Ayesha Bibi")
    data["_raw_mother_name_urdu"] = "عائشہ بی بی"
    raw_text = '{"mother_name": "Ayesha Bibi", "_raw_mother_name_urdu": "عائشہ بی بی"}'
    result = postprocess_bform(data, raw_model_text=raw_text)
    flags = [c for c in result["_column_corrections"] if "FLAG mother_name" in c]
    assert not flags, "Rule E should not flag when transliteration matches mother_name"


def test_rule_e_passes_when_no_urdu_echo():
    """No _raw_mother_name_urdu and name present in raw text — no flag."""
    data = _base_bform(mother_name="Ayesha Bibi")
    raw_text = '{"mother_name": "Ayesha Bibi"}'
    result = postprocess_bform(data, raw_model_text=raw_text)
    flags = [c for c in result["_column_corrections"] if "FLAG mother_name" in c]
    assert not flags


# ── Rule F: duplicate sibling names ───────────────────────────────────────

def test_rule_f_duplicate_child_names():
    """Both children extracted with the same name — hard fail."""
    data = _base_bform(child1_name="Ayesha Noor", child2_name="Ayesha Noor")
    result = postprocess_bform(data, raw_model_text='{"mother_name": "X"}')
    flags = [c for c in result["_column_corrections"] if "FLAG child_name" in c]
    assert flags, "Rule F should flag duplicate sibling names"
    assert result["confidence"]["children"][0]["child_name"] == 0
    assert result["confidence"]["children"][1]["child_name"] == 0


def test_rule_f_distinct_names_pass():
    """Distinct sibling names — no flag."""
    data = _base_bform(child1_name="Fatima Aslam", child2_name="Zainab Aslam")
    result = postprocess_bform(data, raw_model_text='{"mother_name": "X"}')
    flags = [c for c in result["_column_corrections"] if "FLAG child_name" in c]
    assert not flags


def test_rule_f_validate_extraction_surfaces_flag():
    """validate_extraction should surface Rule F flags and zero confidence."""
    data = _base_bform(child1_name="Ayesha Noor", child2_name="Ayesha Noor")
    data["_column_corrections"] = [
        "FLAG child_name: rows [0, 1] share identical name 'Ayesha Noor'; real siblings do not — NEEDS_REVIEW"
    ]
    result = validate_extraction("b_form", data)
    child_name_errors = [
        e for e in result["_validation_errors"]
        if "child_name" in e["field"]
    ]
    assert len(child_name_errors) >= 2, f"Expected at least 2 child_name errors, got {len(child_name_errors)}"
    assert result["confidence"]["children"][0]["child_name"] == 0
    assert result["confidence"]["children"][1]["child_name"] == 0


# ── Rule G: child reg# vs parent CNIC contamination ───────────────────────

def test_rule_g_child_reg_matches_parent_cnic():
    """Child #2's registration number is actually the mother's CNIC."""
    data = _base_bform(child2_reg="11111-1111111-1")
    result = postprocess_bform(data, raw_model_text='{"mother_name": "X"}')
    flags = [
        c for c in result["_column_corrections"]
        if "FLAG children.1.child_registration_number" in c
    ]
    assert flags, "Rule G should flag when child reg# matches a parent CNIC"
    assert result["confidence"]["children"][1]["child_registration_number"] == 0


def test_rule_g_clean_regs_pass():
    """Distinct child reg#s that don't match parent CNICs — no flag."""
    data = _base_bform()
    result = postprocess_bform(data, raw_model_text='{"mother_name": "X"}')
    g_flags = [
        c for c in result["_column_corrections"]
        if "child_registration_number" in c and "matches a parent CNIC" in c
    ]
    assert not g_flags


# ── Item 4: CNIC confidence recalibration ─────────────────────────────────

def test_item4_cnic_confidence_floor():
    """Well-formatted CNIC with model score 0.5 should be raised to 0.8."""
    data = _base_cnic("father_cnic", cnic="44444-4444444-4")
    data["confidence"]["cnic_number"] = 0.5
    result = postprocess_cnic(data, "father_cnic")
    assert result["confidence"]["cnic_number"] == 0.8, (
        f"Expected 0.8, got {result['confidence']['cnic_number']}"
    )


def test_item4_already_high_confidence_unchanged():
    """CNIC confidence already at 0.9 should stay at 0.9."""
    data = _base_cnic("father_cnic", cnic="44444-4444444-4")
    data["confidence"]["cnic_number"] = 0.9
    result = postprocess_cnic(data, "father_cnic")
    assert result["confidence"]["cnic_number"] == 0.9


def test_item4_flagged_cnic_not_recalibrated():
    """CNIC already zeroed by a flag should not be raised."""
    data = _base_cnic("father_cnic", cnic="44444-4444444-4")
    data["confidence"]["cnic_number"] = 0
    result = postprocess_cnic(data, "father_cnic")
    assert result["confidence"]["cnic_number"] == 0, (
        "Zero-confidence CNIC should not be recalibrated upward"
    )


def test_item4_malformed_cnic_not_recalibrated():
    """Malformed CNIC should not be recalibrated."""
    data = _base_cnic("father_cnic", cnic="12345")
    data["confidence"]["cnic_number"] = 0.5
    result = postprocess_cnic(data, "father_cnic")
    assert result["confidence"]["cnic_number"] == 0.5


# ── Item 5: per-document mix-up signal ────────────────────────────────────

def test_item5_per_doc_empty_name_with_husband():
    """Empty cardholder name but father_or_husband_name populated → flag."""
    data = {
        "name": "",
        "father_or_husband_name": "Muhammad Aslam",
        "cnic_number": "11111-1111111-1",
        "date_of_birth": "01-01-1985",
        "confidence": {
            "name": 0.8,
            "father_or_husband_name": 0.8,
            "cnic_number": 0.9,
            "date_of_birth": 0.8,
        },
    }
    result = postprocess_cnic(data, "mother_cnic")
    assert any("FLAG mother_cnic.name" in c for c in result["_cnic_corrections"])
    assert result["confidence"]["name"] == 0


def test_item5_per_doc_name_present_no_flag():
    """Populated name — no flag."""
    data = _base_cnic("mother_cnic", name="Ayesha Bibi", cnic="11111-1111111-1")
    result = postprocess_cnic(data, "mother_cnic")
    assert not any("FLAG" in c for c in result["_cnic_corrections"])


# ── Item 5: cross-document routing mix-up ─────────────────────────────────

def test_item5_cross_doc_identical_cnic():
    """Same CNIC number from both father and mother cards."""
    father = {"cnic_number": "44444-4444444-4", "name": "Muhammad Aslam", "date_of_birth": "01-01-1980"}
    mother = {"cnic_number": "44444-4444444-4", "name": "Muhammad Aslam", "date_of_birth": "01-01-1980"}
    signals = compare_father_mother_cnic_extractions(father, mother)
    assert len(signals) >= 1, "Should flag identical CNIC across both cards"


def test_item5_cross_doc_identical_name_dob():
    """Same name AND DOB across both cards (even if CNIC differs)."""
    father = {"cnic_number": "44444-4444444-4", "name": "Muhammad Aslam", "date_of_birth": "01-01-1980"}
    mother = {"cnic_number": "11111-1111111-1", "name": "Muhammad Aslam", "date_of_birth": "01-01-1980"}
    signals = compare_father_mother_cnic_extractions(father, mother)
    assert any("name=" in s and "date_of_birth=" in s for s in signals)


def test_item5_cross_doc_distinct_no_flag():
    """Distinct father and mother extractions — no signal."""
    father = {"cnic_number": "44444-4444444-4", "name": "Muhammad Aslam", "date_of_birth": "01-01-1980"}
    mother = {"cnic_number": "11111-1111111-1", "name": "Ayesha Bibi", "date_of_birth": "15-06-1985"}
    signals = compare_father_mother_cnic_extractions(father, mother)
    assert not signals


# ── Cross-check integration ───────────────────────────────────────────────

def test_cross_check_includes_routing_mixup():
    """run_cross_checks should surface routing mix-up as a NEEDS_REVIEW check."""
    documents = {
        "b_form": _base_bform(),
        "father_cnic": {"cnic_number": "44444-4444444-4", "name": "Muhammad Aslam", "date_of_birth": "01-01-1980"},
        "mother_cnic": {"cnic_number": "44444-4444444-4", "name": "Muhammad Aslam", "date_of_birth": "01-01-1980"},
        "death_certificate": {"deceased_name": "Muhammad Aslam", "date_of_death": "01-06-2023"},
        "result_card": {"child_name": "Fatima Aslam"},
        "child_picture": {"quality_check": "clear"},
    }
    checks = run_cross_checks(documents)
    mixup_checks = [c for c in checks if "routing mix-up" in c.get("label", "").lower()]
    assert mixup_checks, "Cross-check should include routing mix-up for identical payloads"
    assert all(c["status"] == "NEEDS_REVIEW" for c in mixup_checks)


# ── Existing checks still pass ────────────────────────────────────────────

def test_existing_swap_detection_still_works():
    """Column-swap detection should still recover swapped parent CNICs."""
    data = _base_bform()
    # Simulate a swap: father_cnic_number has a child reg#, and per-row
    # father CNICs have the real value.
    data["father_cnic_number"] = "12345-6789012-3"
    for child in data["children"]:
        child["father_cnic_number"] = "44444-4444444-4"
    result = postprocess_bform(data, raw_model_text='{"mother_name": "X"}')
    assert result["father_cnic_number"] == "44444-4444444-4", (
        f"Swap recovery should restore father_cnic_number, got {result['father_cnic_number']}"
    )


def test_clean_extraction_no_spurious_flags():
    """A correct extraction should produce zero column-correction flags."""
    data = _base_bform()
    raw_text = '{"mother_name": "Ayesha Bibi", "_raw_mother_name_urdu": "عائشہ بی بی"}'
    result = postprocess_bform(data, raw_model_text=raw_text)
    flags = [c for c in result["_column_corrections"] if c.startswith("FLAG")]
    assert not flags, f"Clean extraction should have no flags, got: {flags}"


# ── B-form CNIC confidence recalibration ───────────────────────────────────

def test_bform_cnic_confidence_recalibrated():
    """Well-formatted B-form CNIC fields at 0.5 should be lifted to 0.8."""
    data = _base_bform()
    # Simulate model hedging: correct values but low confidence
    data["confidence"]["father_cnic_number"] = 0.5
    data["confidence"]["mother_cnic_number"] = 0.5
    data["confidence"]["applicant_cnic_number"] = 0.5
    result = postprocess_bform(data, raw_model_text='{"mother_name": "X"}')
    assert result["confidence"]["father_cnic_number"] == 0.8, (
        f"father_cnic_number should be recalibrated to 0.8, got {result['confidence']['father_cnic_number']}"
    )
    assert result["confidence"]["mother_cnic_number"] == 0.8, (
        f"mother_cnic_number should be recalibrated to 0.8, got {result['confidence']['mother_cnic_number']}"
    )
    assert result["confidence"]["applicant_cnic_number"] == 0.8, (
        f"applicant_cnic_number should be recalibrated to 0.8, got {result['confidence']['applicant_cnic_number']}"
    )


def test_bform_cnic_flagged_not_recalibrated():
    """A flagged B-form CNIC field must NOT be recalibrated — stays at 0."""
    data = _base_bform()
    # Force a collision: mother_cnic_number equals a child reg# → triggers swap flag
    data["mother_cnic_number"] = "12345-6789012-3"
    data["confidence"]["mother_cnic_number"] = 0.5
    result = postprocess_bform(data, raw_model_text='{"mother_name": "X"}')
    # mother_cnic_number was flagged — should NOT have been lifted to 0.8
    assert result["confidence"]["mother_cnic_number"] != 0.8, (
        "Flagged CNIC field must not be recalibrated upward"
    )


def test_bform_malformed_cnic_not_recalibrated():
    """Malformed CNIC values on B-form should not be recalibrated to 0.8."""
    data = _base_bform()
    data["father_cnic_number"] = "not-a-cnic"
    data["confidence"]["father_cnic_number"] = 0.5
    result = postprocess_bform(data, raw_model_text='{"mother_name": "X"}')
    assert result["confidence"]["father_cnic_number"] != 0.8, (
        "Malformed CNIC must not be recalibrated to 0.8"
    )


# ── Runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"  PASS  {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed out of {passed + failed}")
