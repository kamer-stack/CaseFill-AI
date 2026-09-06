"""Step-9 A/B runner — positional (A) vs header-keyed (B) B-form extraction.

Runs 5 fresh, independent API calls per arm on test_b.png and saves:
  - raw model JSON as emitted by Qwen-VL
  - adapted canonical JSON (B arm only — A arm is already canonical)
  - postprocessed + validated JSON for both arms
  - classification record (swap / correct / other / unmapped-header)

The two arms share the same runner, fixture, ground truth, and classifier
so the comparison is controlled. No state is shared between runs; each
call to extract_document() is a fresh stateless API call.

Run from backend/:
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -X utf8 \
        tests/fixtures/synthetic_bforms/run_step9_ab.py
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

from typing import Any

_backend = str(Path(__file__).resolve().parents[3])
sys.path.insert(0, _backend)

from dotenv import load_dotenv
load_dotenv(str(Path(__file__).resolve().parents[3] / ".env"))

from app.services.extraction import extract_document                       # noqa: E402
from app.services.prompts_header_keyed import build_bform_prompt_header_keyed  # noqa: E402
from app.services.header_mapping import (                                 # noqa: E402
    adapt_header_keyed_to_canonical,
    map_all_headers,
)
from app.services.validation import (                                     # noqa: E402
    postprocess_bform,
    validate_extraction,
)


FIXTURES = Path(__file__).resolve().parent
RESULTS = FIXTURES / "results" / "step9"

NUM_RUNS = 5
IMAGE_PATH = FIXTURES / "test_b.png"

URDU_RE = re.compile(r"[\u0600-\u06FF]")


def normalize_urdu(s: Any) -> str:
    """Tolerant Urdu normalization for semantic comparison only.

    Strips Arabic diacritics, collapses common Urdu glyph variants
    (ں→ن, ۓ/ئ→ی, Arabic ي→Urdu ی, Arabic ك→Urdu ک), applies NFKC,
    collapses whitespace. Returns '' for non-string/empty input.

    Used ONLY inside the classifier for equality checks; raw values
    saved to disk are untouched.
    """
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[\u064B-\u065F\u0670]", "", s)  # strip diacritics
    s = (s.replace("ں", "ن").replace("ۓ", "ی").replace("ئ", "ی")
          .replace("ي", "ی").replace("ك", "ک"))
    return re.sub(r"\s+", " ", s).strip()

# ─── Ground truth for test_b ───────────────────────────────────────────────

GROUND_TRUTH = {
    "crc_number": "99-TEST-B-2024",
    "applicant_name": "Barkat Ali Hashmi",
    "applicant_cnic_number": "99201-7333333-3",
    "father_name": "Barkat Ali Hashmi",
    "father_cnic_number": "99201-7333333-3",
    "mother_name": "Hoorain Barkat",
    "mother_cnic_number": "99202-8444444-4",
    "children": [
        {
            "serial_number": 1,
            "child_name": "Saad Barkat",
            "child_registration_number": "99-2024-333333",
            "gender_relation": "son",
            "date_of_birth": "22-07-2019",
        }
    ],
}

GT_URDU = {
    "father_name_urdu": "برکت علی ہاشمی",
    "mother_name_urdu": "حوریاں برکت",
    "child_name_urdu": "سعد برکت",
}


# ─── Classifier ────────────────────────────────────────────────────────────

def _str(v) -> str:
    return "" if v is None else str(v).strip()


def classify_canonical(raw: dict) -> dict:
    """Classify a canonical-shape extraction (A arm raw, or B arm adapted).

    Categories are mutually exclusive, evaluated in this order:
      1. UNMAPPED_HEADER   — any of mother/child/father missing from output
      2. MOTHER_CHILD_SWAP — exact 4-field atomic permutation
      3. CORRECT           — mother AND child both correct
      4. PARTIAL_SWAP      — some but not all 4 swapped fields
      5. OTHER_COLUMN_ERROR
    """
    mother_name = _str(raw.get("mother_name"))
    mother_cnic = _str(raw.get("mother_cnic_number"))

    children = raw.get("children") or []
    child0 = children[0] if children and isinstance(children[0], dict) else {}
    child_name = _str(child0.get("child_name"))
    child_reg = _str(child0.get("child_registration_number"))

    gt = GROUND_TRUTH
    gt_child = gt["children"][0]

    # Normalized Urdu forms for tolerant comparison
    n_mother = normalize_urdu(mother_name)
    n_child = normalize_urdu(child_name)
    n_gt_mother = normalize_urdu(GT_URDU["mother_name_urdu"])
    n_gt_child = normalize_urdu(GT_URDU["child_name_urdu"])
    n_gt_roman_mother = gt["mother_name"]
    n_gt_roman_child = gt_child["child_name"]

    # Missing-field sentinel
    missing_mother = mother_name == "" and mother_cnic == ""
    missing_child = child_name == "" and child_reg == ""

    # Exact 4-field atomic permutation (tolerant of Urdu glyph variants)
    mother_has_child_name = (n_mother == n_gt_child) or (
        mother_name != "" and mother_name == n_gt_roman_child
    )
    child_has_mother_name = (n_child == n_gt_mother) or (
        child_name != "" and child_name == n_gt_roman_mother
    )
    mother_has_child_reg = mother_cnic == gt_child["child_registration_number"]
    child_has_mother_cnic = child_reg == gt["mother_cnic_number"]

    is_exact_swap = (
        mother_has_child_name and child_has_mother_name
        and mother_has_child_reg and child_has_mother_cnic
    )

    # Partial swap: any subset of the four fields swapped
    swap_signals = sum([
        mother_has_child_name, child_has_mother_name,
        mother_has_child_reg, child_has_mother_cnic,
    ])

    # Correctness (exact normalized equality only — Roman or Urdu accepted,
    # glyph variants collapsed; no substring matching)
    mother_correct = (
        n_mother == n_gt_mother or n_mother == n_gt_roman_mother
    ) and mother_cnic == gt["mother_cnic_number"]
    child_correct = (
        n_child == n_gt_child or n_child == n_gt_roman_child
    ) and child_reg == gt_child["child_registration_number"]

    names_in_urdu = bool(URDU_RE.search(_str(raw.get("father_name"))))

    if missing_mother or missing_child:
        classification = "UNMAPPED_HEADER"
    elif is_exact_swap:
        classification = "MOTHER_CHILD_SWAP"
    elif mother_correct and child_correct:
        classification = "CORRECT"
    elif swap_signals >= 1:
        classification = "PARTIAL_SWAP"
    else:
        classification = "OTHER_COLUMN_ERROR"

    return {
        "classification": classification,
        "is_exact_swap": is_exact_swap,
        "swap_signals": swap_signals,
        "mother_correct": mother_correct,
        "child_correct": child_correct,
        "names_in_urdu": names_in_urdu,
        "mother_name_raw": mother_name,
        "mother_cnic_raw": mother_cnic,
        "child_name_raw": child_name,
        "child_reg_raw": child_reg,
    }


def classify_header_mapping(raw_hk: dict) -> dict:
    """Inspect the B arm's _header_mapping for NEEDS_REVIEW / ambiguity."""
    raw_headers = raw_hk.get("_raw_column_headers") or raw_hk.get("table_headers") or []
    if not isinstance(raw_headers, list):
        raw_headers = []
    mapping = map_all_headers(raw_headers)
    needs_review = [h for h, s in mapping.items() if s == "NEEDS_REVIEW"]
    semantic_counts: dict[str, int] = {}
    for s in mapping.values():
        if s != "NEEDS_REVIEW":
            semantic_counts[s] = semantic_counts.get(s, 0) + 1
    return {
        "raw_headers": raw_headers,
        "mapping": mapping,
        "needs_review_headers": needs_review,
        "semantic_counts": semantic_counts,
        "all_mapped": len(needs_review) == 0 and len(raw_headers) > 0,
    }


# ─── Single run ────────────────────────────────────────────────────────────

def run_arm_a(run_index: int) -> dict:
    """Positional arm: existing build_bform_prompt (default)."""
    print(f"  A[{run_index + 1}/{NUM_RUNS}]...", end=" ", flush=True)
    start = time.time()
    raw = extract_document(IMAGE_PATH, "b_form", target_child_serial_number=None)
    duration_ms = raw["duration_ms"]

    extracted = raw["extracted"]
    raw_model_text = raw["raw_model_text"]
    post = postprocess_bform(copy.deepcopy(extracted), raw_model_text=raw_model_text)
    validated = validate_extraction("b_form", copy.deepcopy(post))

    elapsed = time.time() - start
    print(f"done ({elapsed:.1f}s, {duration_ms}ms API)")

    return {
        "arm": "A_positional",
        "run_index": run_index,
        "model": raw["model"],
        "duration_ms": duration_ms,
        "classification": classify_canonical(extracted),
        "raw_extracted": extracted,
        "raw_model_text": raw_model_text,
        "postprocessed": post,
        "validated": validated,
    }


def run_arm_b(run_index: int) -> dict:
    """Header-keyed arm: new prompt + adapter to canonical."""
    print(f"  B[{run_index + 1}/{NUM_RUNS}]...", end=" ", flush=True)
    start = time.time()
    raw = extract_document(
        IMAGE_PATH, "b_form",
        target_child_serial_number=None,
        prompt_builder=build_bform_prompt_header_keyed,
    )
    duration_ms = raw["duration_ms"]

    hk_extracted = raw["extracted"]
    raw_model_text = raw["raw_model_text"]

    # Header mapping diagnostics (independent of the model's own _header_mapping)
    header_diag = classify_header_mapping(hk_extracted)

    # Adapter — structural only, no value mutation
    canonical = adapt_header_keyed_to_canonical(copy.deepcopy(hk_extracted))

    post = postprocess_bform(copy.deepcopy(canonical), raw_model_text=raw_model_text)
    validated = validate_extraction("b_form", copy.deepcopy(post))

    elapsed = time.time() - start
    print(f"done ({elapsed:.1f}s, {duration_ms}ms API)")

    return {
        "arm": "B_header_keyed",
        "run_index": run_index,
        "model": raw["model"],
        "duration_ms": duration_ms,
        "classification_raw_hk": classify_canonical(hk_extracted),  # on header-keyed shape (mother/father may not exist as flat keys)
        "classification_adapted": classify_canonical(canonical),
        "header_mapping": header_diag,
        "raw_header_keyed": hk_extracted,
        "adapted_canonical": canonical,
        "raw_model_text": raw_model_text,
        "postprocessed": post,
        "validated": validated,
    }


# ─── Main ──────────────────────────────────────────────────────────────────

def _print_summary(label: str, records: list[dict]) -> None:
    print(f"\n{'=' * 72}\n{label}\n{'=' * 72}")
    counts: dict[str, int] = {}
    for r in records:
        c = r["classification"]["classification"]
        counts[c] = counts.get(c, 0) + 1
    print(f"Distribution over {len(records)} runs: {counts}")

    for r in records:
        cls = r["classification"]
        print(f"\n  {r['arm']} run {r['run_index'] + 1}: {cls['classification']}")
        print(f"    mother_name: {cls['mother_name_raw']}")
        print(f"    mother_cnic: {cls['mother_cnic_raw']}")
        print(f"    child_name:  {cls['child_name_raw']}")
        print(f"    child_reg:   {cls['child_reg_raw']}")
        print(f"    names_in_urdu: {cls['names_in_urdu']}")


def _print_summary_b(records: list[dict]) -> None:
    print(f"\n{'=' * 72}\nARM B — header-keyed\n{'=' * 72}")
    adapted_counts: dict[str, int] = {}
    raw_counts: dict[str, int] = {}
    needs_review_runs = 0
    for r in records:
        a = r["classification_adapted"]["classification"]
        k = r["classification_raw_hk"]["classification"]
        adapted_counts[a] = adapted_counts.get(a, 0) + 1
        raw_counts[k] = raw_counts.get(k, 0) + 1
        if not r["header_mapping"]["all_mapped"]:
            needs_review_runs += 1
    print(f"Adapted classification: {adapted_counts}")
    print(f"Raw-HK classification (flat lookup, may miss keys): {raw_counts}")
    print(f"Runs with >=1 NEEDS_REVIEW header: {needs_review_runs}/{len(records)}")

    for r in records:
        cls = r["classification_adapted"]
        hm = r["header_mapping"]
        print(f"\n  B run {r['run_index'] + 1}: {cls['classification']}")
        print(f"    mother_name: {cls['mother_name_raw']}")
        print(f"    mother_cnic: {cls['mother_cnic_raw']}")
        print(f"    child_name:  {cls['child_name_raw']}")
        print(f"    child_reg:   {cls['child_reg_raw']}")
        print(f"    header_mapping: {json.dumps(hm['mapping'], ensure_ascii=False)}")
        print(f"    needs_review: {hm['needs_review_headers']}")


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)

    if not os.getenv("API_KEY"):
        print("ERROR: API_KEY not set", file=sys.stderr)
        sys.exit(2)

    if not IMAGE_PATH.exists():
        print(f"ERROR: {IMAGE_PATH} not found", file=sys.stderr)
        sys.exit(2)

    print(f"Step-9 A/B experiment on {IMAGE_PATH.name}")
    print(f"Ground truth: mother=Hoorain Barkat ({GT_URDU['mother_name_urdu']}), "
          f"child=Saad Barkat ({GT_URDU['child_name_urdu']})\n")

    print("ARM A — positional (existing prompt):")
    a_runs = [run_arm_a(i) for i in range(NUM_RUNS)]
    print("\nARM B — header-keyed (new prompt + adapter):")
    b_runs = [run_arm_b(i) for i in range(NUM_RUNS)]

    # Persist each run
    for r in a_runs:
        out = RESULTS / f"A_run_{r['run_index']}.json"
        out.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in b_runs:
        out = RESULTS / f"B_run_{r['run_index']}.json"
        out.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    _print_summary("ARM A — positional", a_runs)
    _print_summary_b(b_runs)

    # Cross-arm comparison summary
    print(f"\n{'=' * 72}\nCOMPARISON\n{'=' * 72}")
    a_swap = sum(1 for r in a_runs if r["classification"]["is_exact_swap"])
    b_swap = sum(1 for r in b_runs if r["classification_adapted"]["is_exact_swap"])
    a_correct = sum(1 for r in a_runs if r["classification"]["classification"] == "CORRECT")
    b_correct = sum(1 for r in b_runs if r["classification_adapted"]["classification"] == "CORRECT")
    b_unmapped = sum(1 for r in b_runs if r["classification_adapted"]["classification"] == "UNMAPPED_HEADER")
    print(f"Positional (A):  exact_swap={a_swap}/{NUM_RUNS}  correct={a_correct}/{NUM_RUNS}")
    print(f"Header-keyed (B): exact_swap={b_swap}/{NUM_RUNS}  correct={b_correct}/{NUM_RUNS}  unmapped={b_unmapped}/{NUM_RUNS}")


if __name__ == "__main__":
    main()
