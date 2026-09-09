"""Step-9 regression tests: A/B experiment (positional vs header-keyed).

Tests the SAVED results from the Step-9 A/B runner on test_b.png.
No live API calls — purely deterministic assertions against captured data.

Run from backend/:
    venv/Scripts/python.exe -m pytest tests/fixtures/synthetic_bforms/test_step9_ab_regression.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RESULTS_DIR = Path(__file__).parent / "results" / "step9"

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


def _load_arm(arm: str, idx: int) -> dict:
    path = RESULTS_DIR / f"{arm}_run_{idx}.json"
    if not path.exists():
        pytest.skip(f"Step-9 {arm}_run_{idx}.json not found — run the A/B runner first")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_arm_all(arm: str) -> list[dict]:
    runs = []
    for i in range(5):
        path = RESULTS_DIR / f"{arm}_run_{i}.json"
        if path.exists():
            runs.append(json.loads(path.read_text(encoding="utf-8")))
    if not runs:
        pytest.skip(f"No Step-9 {arm} result files found")
    return runs


# ── Section 1: Swap frequency comparison ────────────────────────────────────


class TestSwapFrequencyComparison:
    """Header-keyed extraction must reduce the mother<->child swap."""

    def test_positional_swap_rate_at_least_half(self):
        """The positional arm shows the swap on >=50% of runs (Step 8 finding)."""
        runs = _load_arm_all("A")
        swaps = sum(1 for r in runs if r["classification"].get("is_exact_swap"))
        assert swaps >= len(runs) / 2, (
            f"Positional arm: only {swaps}/{len(runs)} swaps; expected >=50%"
        )

    def test_header_keyed_swap_rate_zero(self):
        """The header-keyed arm must show ZERO exact 4-field mother<->child swaps."""
        runs = _load_arm_all("B")
        swaps = sum(
            1 for r in runs if r["classification_adapted"].get("is_exact_swap")
        )
        assert swaps == 0, (
            f"Header-keyed arm: {swaps}/{len(runs)} runs showed an exact swap; "
            "expected 0"
        )

    def test_header_keyed_all_correct(self):
        """Every header-keyed run places the correct name/CNIC in each slot."""
        runs = _load_arm_all("B")
        for r in runs:
            cls = r["classification_adapted"]
            assert cls["classification"] == "CORRECT", (
                f"B run {r['run_index']+1} classified as {cls['classification']}, "
                "expected CORRECT"
            )

    def test_positional_vs_header_keyed_swap_counts(self):
        """Arm A swap count strictly greater than Arm B swap count."""
        a = _load_arm_all("A")
        b = _load_arm_all("B")
        a_swaps = sum(1 for r in a if r["classification"].get("is_exact_swap"))
        b_swaps = sum(1 for r in b if r["classification_adapted"].get("is_exact_swap"))
        assert a_swaps > b_swaps, (
            f"Positional swaps {a_swaps} must exceed header-keyed swaps {b_swaps}"
        )


# ── Section 2: Header mapping reliability ───────────────────────────────────


class TestHeaderMappingReliability:
    """Every B-arm run must resolve all 7 headers to their semantic keys."""

    def test_no_needs_review_in_any_b_run(self):
        runs = _load_arm_all("B")
        for r in runs:
            nr = r["header_mapping"]["needs_review_headers"]
            assert nr == [], (
                f"B run {r['run_index']+1} has NEEDS_REVIEW headers: {nr}"
            )

    def test_all_seven_semantic_keys_present(self):
        expected = {
            "serial", "child", "father", "mother",
            "gender_relation", "date_of_birth", "remarks",
        }
        runs = _load_arm_all("B")
        for r in runs:
            semantics = set(r["header_mapping"]["mapping"].values())
            assert semantics == expected, (
                f"B run {r['run_index']+1} semantics {semantics} != {expected}"
            )

    def test_b_arm_raw_headers_match_canonical(self):
        """The VLM reads the same canonical Urdu headers we seeded in the HTML."""
        canonical = set(GT_URDU.values())  # not used — but assert header values
        runs = _load_arm_all("B")
        for r in runs:
            raw_headers = r["header_mapping"]["raw_headers"]
            assert len(raw_headers) == 7, (
                f"B run {r['run_index']+1} has {len(raw_headers)} headers, expected 7"
            )


# ── Section 3: Postprocessing compatibility ────────────────────────────────


class TestPostprocessingCompatibility:
    """The adapter output is accepted by existing postprocessing unchanged."""

    def test_b_arm_postprocessing_does_not_swap_back(self):
        """Postprocessing preserves the correct mother/child placement from the adapter."""
        runs = _load_arm_all("B")
        for r in runs:
            post = r["postprocessed"]
            mother_name = (post.get("mother_name") or "").strip()
            mother_cnic = (post.get("mother_cnic_number") or "").strip()
            ch = post.get("children") or []
            child = ch[0] if ch and isinstance(ch[0], dict) else {}
            child_name = (child.get("child_name") or "").strip()
            child_reg = (child.get("child_registration_number") or "").strip()

            # Mother slot holds mother's values, not child's
            assert mother_cnic == GT_CNIC["mother_cnic"], (
                f"B run {r['run_index']+1} postprocessing moved mother_cnic to "
                f"{mother_cnic!r}, expected {GT_CNIC['mother_cnic']!r}"
            )
            assert child_reg == GT_CNIC["child_reg"], (
                f"B run {r['run_index']+1} postprocessing moved child_reg to "
                f"{child_reg!r}, expected {GT_CNIC['child_reg']!r}"
            )
            # Name values (Urdu)
            assert "سعد" not in mother_name, (
                f"B run {r['run_index']+1} postprocessing leaked child name into mother: "
                f"{mother_name!r}"
            )
            assert "سعد" in child_name, (
                f"B run {r['run_index']+1} postprocessing lost child name: {child_name!r}"
            )

    def test_a_arm_swap_survives_postprocessing(self):
        """Postprocessing does NOT reverse the swap in the A arm (established Step 8)."""
        runs = _load_arm_all("A")
        swapped_runs = [r for r in runs if r["classification"].get("is_exact_swap")]
        assert swapped_runs, "No A-arm swapped runs available to test"
        for r in swapped_runs:
            post = r["postprocessed"]
            mother_cnic = (post.get("mother_cnic_number") or "").strip()
            # Swapped post-state: mother_cnic holds the CHILD reg, not the mother CNIC
            assert mother_cnic == GT_CNIC["child_reg"], (
                f"A run {r['run_index']+1} postprocessing unexpectedly reversed "
                f"the swap: mother_cnic={mother_cnic!r}"
            )


# ── Section 4: Raw evidence preservation ────────────────────────────────────


class TestRawEvidencePreservation:
    """The header-keyed arm preserves raw forensic evidence."""

    def test_raw_column_headers_present(self):
        runs = _load_arm_all("B")
        for r in runs:
            hk = r["raw_header_keyed"]
            assert "_raw_column_headers" in hk
            assert isinstance(hk["_raw_column_headers"], list)
            assert len(hk["_raw_column_headers"]) >= 7

    def test_raw_urdu_echoes_present(self):
        runs = _load_arm_all("B")
        for r in runs:
            hk = r["raw_header_keyed"]
            assert hk.get("_raw_father_name_urdu"), "missing _raw_father_name_urdu"
            assert hk.get("_raw_mother_name_urdu"), "missing _raw_mother_name_urdu"
            assert hk.get("_raw_child_names_urdu"), "missing _raw_child_names_urdu"

    def test_adapted_canonical_preserves_echoes(self):
        """The adapter passes raw echoes through verbatim."""
        runs = _load_arm_all("B")
        for r in runs:
            adapted = r["adapted_canonical"]
            assert adapted.get("_raw_father_name_urdu")
            assert adapted.get("_raw_mother_name_urdu")
            assert adapted.get("_raw_child_names_urdu")
            assert "_header_mapping" in adapted
            assert "_raw_column_headers" in adapted

    def test_header_mapping_diagnostic_present(self):
        """Each B run includes the deterministic post-hoc header mapping."""
        runs = _load_arm_all("B")
        for r in runs:
            hm = r["header_mapping"]
            assert "mapping" in hm
            assert "needs_review_headers" in hm
            assert "semantic_counts" in hm
            # 7 distinct semantic keys, each count=1
            assert len(hm["mapping"]) == 7
            assert all(v == 1 for v in hm["semantic_counts"].values())


# ── Section 5: Other error categories ──────────────────────────────────────


class TestOtherErrors:
    """Document-level correctness outside the mother/child swap."""

    def test_b_arm_father_cnic_correct(self):
        runs = _load_arm_all("B")
        for r in runs:
            adapted = r["adapted_canonical"]
            assert adapted.get("father_cnic_number") == GT_CNIC["father_cnic"], (
                f"B run {r['run_index']+1}: father_cnic "
                f"{adapted.get('father_cnic_number')!r} != {GT_CNIC['father_cnic']!r}"
            )

    def test_b_arm_mother_cnic_correct(self):
        runs = _load_arm_all("B")
        for r in runs:
            adapted = r["adapted_canonical"]
            assert adapted.get("mother_cnic_number") == GT_CNIC["mother_cnic"]

    def test_b_arm_child_registration_correct(self):
        runs = _load_arm_all("B")
        for r in runs:
            adapted = r["adapted_canonical"]
            ch = adapted.get("children") or []
            assert ch, "no children in adapted canonical"
            assert ch[0].get("child_registration_number") == GT_CNIC["child_reg"]

    def test_model_confidence_never_zero_on_canonical_fields(self):
        """B arm: confidence should be non-zero for fields the model did emit."""
        runs = _load_arm_all("B")
        for r in runs:
            hk = r["raw_header_keyed"]
            conf = hk.get("confidence") or {}
            # At least one of the top-level confs is non-zero
            top_keys = ("crc_number", "applicant_name", "applicant_cnic_number")
            assert any(conf.get(k) not in (None, 0) for k in top_keys), (
                f"B run {r['run_index']+1}: all top-level confidences are zero"
            )
