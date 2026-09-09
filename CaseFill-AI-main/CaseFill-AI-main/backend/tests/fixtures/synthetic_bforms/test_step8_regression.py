"""Step-8 regression tests: mother<->child column swap analysis.

Tests the SAVED results from 5 independent API calls on test_b.png.
No live API calls — purely deterministic assertions against captured data.

Run from backend/:
    venv/Scripts/python.exe -m pytest tests/fixtures/synthetic_bforms/test_step8_regression.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RESULTS_DIR = Path(__file__).parent / "results" / "step8"

# Ground truth Urdu values from generate_html.py TEST_B
GT_URDU = {
    "father_name_urdu": "برکت علی ہاشمی",
    "mother_name_urdu": "حوریاں برکت",
    "child_name_urdu": "سعد برکت",
}

GT_CNIC = {
    "mother_cnic": "99202-8444444-4",
    "child_reg": "99-2024-333333",
    "father_cnic": "99201-7333333-3",
}

CORRECT_HEADERS = {
    "col1": "نمبر شمار",
    "col2": "بچے کا نام اور رجسٹریشن نمبر",
    "col3": "والد کا نام اور شناختی کارڈ نمبر",
    "col4": "والدہ کا نام اور شناختی کارڈ نمبر",
}

WRONG_HEADERS = {
    "col1": "نمبر شمار",
    "col2": "والد کا نام اور شناختی کارڈ نمبر",
    "col3": "والدہ کا نام اور شناختی کارڈ نمبر",
    "col4": "جنس / رشتہ",
    "col5": "تاریخ پیدائش",
    "col6": "معذوری",
    "col7": "نمبر شمار",
}


def _load_run(idx: int) -> dict:
    path = RESULTS_DIR / f"run_{idx}.json"
    if not path.exists():
        pytest.skip(f"Step-8 run_{idx}.json not found — run the repeatability runner first")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_all_runs() -> list[dict]:
    runs = []
    for i in range(5):
        path = RESULTS_DIR / f"run_{i}.json"
        if path.exists():
            runs.append(json.loads(path.read_text(encoding="utf-8")))
    if not runs:
        pytest.skip("No Step-8 result files found")
    return runs


# ── Section 1: Swap frequency ───────────────────────────────────────────────


class TestSwapFrequency:
    """The mother<->child column swap is stochastic, not deterministic."""

    def test_not_all_runs_same_classification(self):
        runs = _load_all_runs()
        classifications = {r["classification"]["classification"] for r in runs}
        assert len(classifications) >= 2, (
            f"All {len(runs)} runs produced the same classification "
            f"{classifications}; expected stochastic variation"
        )

    def test_swap_count_is_3_of_5(self):
        """Document the observed swap rate: 3 swapped, 2 correct."""
        runs = _load_all_runs()
        swapped = [
            r for r in runs
            if r["classification"]["mother_name_raw"] == GT_URDU["child_name_urdu"]
        ]
        correct = [
            r for r in runs
            if GT_URDU["mother_name_urdu"] in r["classification"]["mother_name_raw"]
            or "حوری" in r["classification"]["mother_name_raw"]
        ]
        assert len(swapped) == 3, f"Expected 3 swapped runs, got {len(swapped)}"
        assert len(correct) == 2, f"Expected 2 correct runs, got {len(correct)}"

    def test_swap_rate_approximately_60_percent(self):
        runs = _load_all_runs()
        swapped = sum(
            1 for r in runs
            if r["classification"]["mother_name_raw"] == GT_URDU["child_name_urdu"]
        )
        rate = swapped / len(runs)
        assert 0.4 <= rate <= 0.8, f"Swap rate {rate:.0%} outside expected range"


# ── Section 2: Exact permutation ────────────────────────────────────────────


class TestExactPermutation:
    """When the swap occurs, it is an exact 4-field permutation."""

    def test_swapped_runs_have_all_four_fields_swapped(self):
        runs = _load_all_runs()
        for r in runs:
            c = r["classification"]
            mother_name = c["mother_name_raw"]
            if mother_name != GT_URDU["child_name_urdu"]:
                continue
            assert c["mother_cnic_raw"] == GT_CNIC["child_reg"], (
                f"Run {r['run_index']}: mother_cnic should be child_reg "
                f"when swapped, got {c['mother_cnic_raw']}"
            )
            assert "حوری" in c["child_name_raw"], (
                f"Run {r['run_index']}: child_name should contain mother_name "
                f"when swapped, got {c['child_name_raw']}"
            )
            assert c["child_reg_raw"] == GT_CNIC["mother_cnic"], (
                f"Run {r['run_index']}: child_reg should be mother_cnic "
                f"when swapped, got {c['child_reg_raw']}"
            )

    def test_swap_is_atomic_not_partial(self):
        """All 4 fields swap together, never 2 or 3 out of 4."""
        runs = _load_all_runs()
        for r in runs:
            c = r["classification"]
            name_swapped = c["mother_name_raw"] == GT_URDU["child_name_urdu"]
            cnic_swapped = c["mother_cnic_raw"] == GT_CNIC["child_reg"]
            child_name_swapped = "حوری" in c["child_name_raw"]
            child_reg_swapped = c["child_reg_raw"] == GT_CNIC["mother_cnic"]

            swap_flags = [name_swapped, cnic_swapped, child_name_swapped, child_reg_swapped]
            n_swapped = sum(swap_flags)
            assert n_swapped in (0, 4), (
                f"Run {r['run_index']}: partial swap detected — "
                f"{n_swapped}/4 fields swapped: {swap_flags}"
            )


# ── Section 3: Column header analysis ───────────────────────────────────────


class TestColumnHeaders:
    """_column_headers_read reveals the model's internal column mapping."""

    def test_run_1_has_correct_headers(self):
        """Run 1 is the only run where both headers and values are correct."""
        r = _load_run(1)
        headers = r["raw_extracted"].get("_column_headers_read", {})
        assert headers.get("col2") == CORRECT_HEADERS["col2"], (
            f"Run 1 should have correct col2, got '{headers.get('col2')}'"
        )

    def test_run_4_has_wrong_headers_but_correct_values(self):
        """Run 4: decoupled header enumeration from value assignment.

        The model reported wrong headers (same as swap runs) but placed
        values in the correct JSON fields — proving that _column_headers_read
        and value assignment use different internal mechanisms.
        """
        r = _load_run(4)
        headers = r["raw_extracted"].get("_column_headers_read", {})
        assert headers.get("col2") == WRONG_HEADERS["col2"], (
            f"Run 4 should have wrong col2 (decoupled), got '{headers.get('col2')}'"
        )
        c = r["classification"]
        assert "حوری" in c["mother_name_raw"], (
            "Run 4 should have correct mother_name despite wrong headers"
        )
        assert c["child_reg_raw"] == GT_CNIC["child_reg"], (
            "Run 4 should have correct child_reg despite wrong headers"
        )

    def test_swapped_runs_have_shifted_headers(self):
        runs = _load_all_runs()
        for r in runs:
            c = r["classification"]
            if c["mother_name_raw"] != GT_URDU["child_name_urdu"]:
                continue
            headers = r["raw_extracted"].get("_column_headers_read", {})
            assert headers.get("col2") == WRONG_HEADERS["col2"], (
                f"Run {r['run_index']}: swapped run should have col2="
                f"'{WRONG_HEADERS['col2']}', got '{headers.get('col2')}'"
            )

    def test_swapped_runs_duplicate_col1_in_col7(self):
        """The model writes the same header for col1 and col7 in swap runs."""
        runs = _load_all_runs()
        for r in runs:
            c = r["classification"]
            if c["mother_name_raw"] != GT_URDU["child_name_urdu"]:
                continue
            headers = r["raw_extracted"].get("_column_headers_read", {})
            assert headers.get("col7") == headers.get("col1"), (
                f"Run {r['run_index']}: col7 should duplicate col1 "
                f"in swap runs"
            )

    def test_swapped_runs_miss_child_column_entirely(self):
        """The child column header (بچے کا نام...) never appears in swap runs."""
        runs = _load_all_runs()
        child_header = CORRECT_HEADERS["col2"]
        for r in runs:
            c = r["classification"]
            if c["mother_name_raw"] != GT_URDU["child_name_urdu"]:
                continue
            headers = r["raw_extracted"].get("_column_headers_read", {})
            header_values = list(headers.values())
            assert child_header not in header_values, (
                f"Run {r['run_index']}: child header should be absent in "
                f"swap run headers"
            )

    def test_header_value_correlation(self):
        """Correct headers ↔ correct values; wrong headers ↔ swapped values.

        Exception: run 4 has wrong headers but correct values — the model's
        header enumeration and value assignment can be decoupled.
        """
        runs = _load_all_runs()
        correct_header_correct_values = 0
        wrong_header_swapped_values = 0
        wrong_header_correct_values = 0

        for r in runs:
            headers = r["raw_extracted"].get("_column_headers_read", {})
            has_correct_col2 = headers.get("col2") == CORRECT_HEADERS["col2"]
            mother_correct = "حوری" in r["classification"]["mother_name_raw"]

            if has_correct_col2 and mother_correct:
                correct_header_correct_values += 1
            elif not has_correct_col2 and not mother_correct:
                wrong_header_swapped_values += 1
            elif not has_correct_col2 and mother_correct:
                wrong_header_correct_values += 1

        assert correct_header_correct_values >= 1
        assert wrong_header_swapped_values >= 1
        # Run 4 is the exception: wrong headers but correct values
        assert wrong_header_correct_values >= 1, (
            "Expected at least one run with wrong headers but correct values "
            "(decoupled header enumeration from value assignment)"
        )


# ── Section 4: Consistent errors across all runs ────────────────────────────


class TestConsistentErrors:
    """Errors that appear in ALL 5 runs regardless of swap state."""

    def test_all_runs_output_names_in_urdu(self):
        """F1: model ignores 'NEVER output Urdu/Arabic script' instruction."""
        import re
        urdu_re = re.compile(r"[\u0600-\u06FF]")
        runs = _load_all_runs()
        for r in runs:
            assert r["classification"]["names_in_urdu"], (
                f"Run {r['run_index']}: expected names in Urdu (F1)"
            )

    def test_all_runs_reverse_crc_groups(self):
        """F5: CRC '99-TEST-B-2024' always read as 'TEST-B-2024-99'."""
        runs = _load_all_runs()
        for r in runs:
            crc = r["raw_extracted"].get("crc_number", "")
            assert crc == "TEST-B-2024-99", (
                f"Run {r['run_index']}: expected reversed CRC, got '{crc}'"
            )

    def test_all_runs_misspell_hashmi_as_pashmi(self):
        """Model consistently reads ہاشمی as پاشمی (H→P confusion)."""
        runs = _load_all_runs()
        for r in runs:
            raw_father = r["raw_extracted"].get("_raw_father_name_urdu", "")
            assert "پاشمی" in raw_father, (
                f"Run {r['run_index']}: expected پاشمی in father name, "
                f"got '{raw_father}'"
            )

    def test_all_runs_use_betta_for_son(self):
        """Gender always read as 'بٹا' (with ٹ) instead of standard 'بیٹا'."""
        runs = _load_all_runs()
        for r in runs:
            children = r["raw_extracted"].get("children", [])
            if children:
                gender = children[0].get("gender_relation", "")
                assert gender == "بٹا", (
                    f"Run {r['run_index']}: expected 'بٹا', got '{gender}'"
                )


# ── Section 5: Postprocessing behavior ──────────────────────────────────────


class TestPostprocessingBehavior:
    """Postprocessing catches symptoms but cannot fix the swap."""

    def test_rule_e_flags_swapped_mother_name(self):
        runs = _load_all_runs()
        for r in runs:
            c = r["classification"]
            if c["mother_name_raw"] != GT_URDU["child_name_urdu"]:
                continue
            corrections = r["postprocessed"].get("_column_corrections", [])
            mother_flags = [x for x in corrections if "mother_name" in x]
            assert len(mother_flags) >= 1, (
                f"Run {r['run_index']}: Rule E should flag swapped mother_name"
            )

    def test_cnic_format_check_flags_child_reg_in_mother_slot(self):
        """When swapped, child_reg (99-2024-333333) fails CNIC format check."""
        runs = _load_all_runs()
        for r in runs:
            c = r["classification"]
            if c["mother_name_raw"] != GT_URDU["child_name_urdu"]:
                continue
            corrections = r["postprocessed"].get("_column_corrections", [])
            cnic_flags = [x for x in corrections if "mother_cnic_number" in x]
            assert len(cnic_flags) >= 1, (
                f"Run {r['run_index']}: CNIC format check should flag "
                f"child_reg in mother_cnic slot"
            )

    def test_confidence_zeroed_on_swapped_fields(self):
        """Postprocessor forces confidence=0 on flagged fields."""
        runs = _load_all_runs()
        for r in runs:
            c = r["classification"]
            if c["mother_name_raw"] != GT_URDU["child_name_urdu"]:
                continue
            conf = r["postprocessed"].get("confidence", {})
            assert conf.get("mother_name") == 0
            assert conf.get("mother_cnic_number") == 0

    def test_postprocessing_does_not_reverse_swap(self):
        """Critical: postprocessing flags but never swaps values back."""
        runs = _load_all_runs()
        for r in runs:
            c = r["classification"]
            if c["mother_name_raw"] != GT_URDU["child_name_urdu"]:
                continue
            post = r["postprocessed"]
            assert post["mother_name"] == GT_URDU["child_name_urdu"], (
                f"Run {r['run_index']}: postprocessing should NOT fix the swap; "
                f"mother_name should still contain child_name"
            )

    def test_correct_runs_still_trigger_rule_e_false_positive(self):
        """F2: Rule E flags Urdu names even when column assignment is correct."""
        runs = _load_all_runs()
        for r in runs:
            c = r["classification"]
            if "حوری" not in c["mother_name_raw"]:
                continue
            corrections = r["postprocessed"].get("_column_corrections", [])
            mother_flags = [x for x in corrections if "mother_name" in x]
            assert len(mother_flags) >= 1, (
                f"Run {r['run_index']}: Rule E false positive should still fire "
                f"on correct runs (names in Urdu vs Roman comparison)"
            )


# ── Section 6: Deterministic postprocessing ─────────────────────────────────


class TestDeterministicPostprocessing:
    """Same raw input always produces same postprocessed output."""

    def test_swap_run_0_and_2_produce_identical_postprocessing(self):
        """Runs 0 and 2 have identical raw output → identical postprocessing."""
        run0 = _load_run(0)
        run2 = _load_run(2)
        assert run0["raw_extracted"] == run2["raw_extracted"], (
            "Runs 0 and 2 should have identical raw output"
        )
        assert run0["postprocessed"] == run2["postprocessed"], (
            "Identical raw input should produce identical postprocessing"
        )

    def test_swap_run_0_and_3_produce_identical_postprocessing(self):
        run0 = _load_run(0)
        run3 = _load_run(3)
        assert run0["raw_extracted"] == run3["raw_extracted"]
        assert run0["postprocessed"] == run3["postprocessed"]


# ── Section 7: Confidence analysis ──────────────────────────────────────────


class TestConfidenceAnalysis:
    """Model self-reports confidence=1 even when wrong."""

    def test_raw_confidence_always_1(self):
        """Model reports confidence=1 for all fields in all runs."""
        runs = _load_all_runs()
        for r in runs:
            conf = r["raw_extracted"].get("confidence", {})
            assert conf.get("mother_name") == 1
            assert conf.get("mother_cnic_number") == 1
            children_conf = conf.get("children", [])
            if children_conf:
                assert children_conf[0].get("child_name") == 1
                assert children_conf[0].get("child_registration_number") == 1

    def test_model_confidence_uncorrelated_with_accuracy(self):
        """Confidence=1 appears in both correct and swapped runs."""
        runs = _load_all_runs()
        for r in runs:
            raw_conf = r["raw_extracted"].get("confidence", {})
            assert raw_conf.get("mother_name") == 1, (
                f"Run {r['run_index']}: raw confidence should be 1 "
                f"regardless of swap state"
            )


# ── Section 8: Cross-reference with Step 7 ─────────────────────────────────


class TestStep7Consistency:
    """Step-8 results must be consistent with Step-7 baseline."""

    def test_step7_test_b_matches_swap_pattern(self):
        """The Step 7 test_b result also shows the swap (consistent with 60% rate)."""
        step7_path = RESULTS_DIR.parent / "test_b.json"
        if not step7_path.exists():
            pytest.skip("Step 7 test_b.json not found")
        step7 = json.loads(step7_path.read_text(encoding="utf-8"))
        raw = step7["raw_extracted"]
        mother_name = raw.get("mother_name", "")
        assert mother_name == GT_URDU["child_name_urdu"], (
            f"Step 7 test_b should show swap pattern, "
            f"mother_name='{mother_name}'"
        )

    def test_step7_headers_match_swap_pattern(self):
        """Step 7 test_b _column_headers_read should match the swap-run pattern."""
        step7_path = RESULTS_DIR.parent / "test_b.json"
        if not step7_path.exists():
            pytest.skip("Step 7 test_b.json not found")
        step7 = json.loads(step7_path.read_text(encoding="utf-8"))
        headers = step7["raw_extracted"].get("_column_headers_read", {})
        assert headers.get("col2") == WRONG_HEADERS["col2"], (
            "Step 7 test_b headers should match swap-run pattern"
        )
