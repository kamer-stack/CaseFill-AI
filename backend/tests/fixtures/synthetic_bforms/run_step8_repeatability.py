"""Step-8 repeatability runner — 5 independent API calls on test_b.png.

Captures raw Qwen output BEFORE postprocess_bform()/validate_extraction()
for each run. Also runs postprocessing + validation to compare stages.

Run from backend/:
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -X utf8 \
        tests/fixtures/synthetic_bforms/run_step8_repeatability.py
"""

from __future__ import annotations

import copy
import json
import os
import sys
import time
from pathlib import Path

_backend = str(Path(__file__).resolve().parents[3])
sys.path.insert(0, _backend)

from dotenv import load_dotenv
load_dotenv(str(Path(__file__).resolve().parents[3] / ".env"))

from app.services.extraction import extract_document  # noqa: E402
from app.services.validation import (                 # noqa: E402
    postprocess_bform, validate_extraction,
)

FIXTURES = Path(__file__).resolve().parent
RESULTS = FIXTURES / "results" / "step8"

NUM_RUNS = 5
IMAGE_PATH = FIXTURES / "test_b.png"

# Ground truth for test_b
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

# Ground-truth Urdu values (from generate_html.py TEST_B)
GT_URDU = {
    "father_name_urdu": "برکت علی ہاشمی",
    "mother_name_urdu": "حوریاں برکت",
    "child_name_urdu": "سعد برکت",
}


def classify_run(raw: dict) -> dict:
    """Classify a single run's swap pattern."""
    mother_name = str(raw.get("mother_name") or "").strip()
    mother_cnic = str(raw.get("mother_cnic_number") or "").strip()

    children = raw.get("children", [])
    child0 = children[0] if children and isinstance(children[0], dict) else {}
    child_name = str(child0.get("child_name") or "").strip()
    child_reg = str(child0.get("child_registration_number") or "").strip()

    # Check exact permutation: mother↔child swap
    # In Urdu: mother should be GT_URDU["mother_name_urdu"], child should be GT_URDU["child_name_urdu"]
    mother_has_child_name = child_name == "" or mother_name == GT_URDU["child_name_urdu"]
    child_has_mother_name = child_name == GT_URDU["mother_name_urdu"]
    mother_has_child_reg = mother_cnic == GROUND_TRUTH["children"][0]["child_registration_number"]
    child_has_mother_cnic = child_reg == GROUND_TRUTH["mother_cnic_number"]

    is_exact_swap = (
        mother_has_child_name and child_has_mother_name and
        mother_has_child_reg and child_has_mother_cnic
    )

    # Check if names are in Urdu (wrong script)
    import re
    urdu_re = re.compile(r"[\u0600-\u06FF]")
    names_in_urdu = bool(urdu_re.search(str(raw.get("father_name", ""))))

    # Classify
    if is_exact_swap:
        classification = "MOTHER_CHILD_SWAP"
    elif mother_name == GT_URDU["mother_name_urdu"] or (
        # Check if mother name is correct in Roman
        "Hoorain" in mother_name or "حو" in mother_name
    ):
        classification = "CORRECT"
    else:
        classification = "OTHER_COLUMN_ERROR"

    return {
        "classification": classification,
        "is_exact_swap": is_exact_swap,
        "names_in_urdu": names_in_urdu,
        "mother_name_raw": mother_name,
        "mother_cnic_raw": mother_cnic,
        "child_name_raw": child_name,
        "child_reg_raw": child_reg,
    }


def run_once(run_index: int) -> dict:
    """Execute one independent API call and capture all stages."""
    print(f"  Run {run_index + 1}/{NUM_RUNS}...", end=" ", flush=True)
    start = time.time()

    raw = extract_document(IMAGE_PATH, "b_form", target_child_serial_number=None)
    raw_extracted = raw["extracted"]
    raw_model_text = raw["raw_model_text"]
    duration_ms = raw["duration_ms"]

    post = postprocess_bform(copy.deepcopy(raw_extracted), raw_model_text=raw_model_text)
    validated = validate_extraction("b_form", copy.deepcopy(post))

    elapsed = time.time() - start
    print(f"done ({elapsed:.1f}s)")

    classification = classify_run(raw_extracted)

    return {
        "run_index": run_index,
        "model": raw["model"],
        "duration_ms": duration_ms,
        "classification": classification,
        "raw_extracted": raw_extracted,
        "raw_model_text": raw_model_text,
        "postprocessed": post,
        "validated": validated,
    }


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)

    if not os.getenv("API_KEY"):
        print("ERROR: API_KEY not set", file=sys.stderr)
        sys.exit(2)

    if not IMAGE_PATH.exists():
        print(f"ERROR: {IMAGE_PATH} not found", file=sys.stderr)
        sys.exit(2)

    print(f"Step-8 repeatability: {NUM_RUNS} runs on {IMAGE_PATH.name}")
    print(f"Ground truth: mother=Hoorain Barkat, child=Saad Barkat\n")

    runs = []
    for i in range(NUM_RUNS):
        record = run_once(i)
        out = RESULTS / f"run_{i}.json"
        out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        runs.append(record)

    # Summary
    print(f"\n{'='*72}")
    print("SUMMARY")
    print(f"{'='*72}")

    swap_count = sum(1 for r in runs if r["classification"]["is_exact_swap"])
    print(f"Exact mother↔child permutation: {swap_count}/{NUM_RUNS}")

    for i, r in enumerate(runs):
        c = r["classification"]
        print(f"\n  Run {i + 1}: {c['classification']}")
        print(f"    mother_name:  {c['mother_name_raw']}")
        print(f"    mother_cnic:  {c['mother_cnic_raw']}")
        print(f"    child_name:   {c['child_name_raw']}")
        print(f"    child_reg:    {c['child_reg_raw']}")
        print(f"    names_in_urdu: {c['names_in_urdu']}")

        # Header analysis
        raw = r["raw_extracted"]
        headers = raw.get("_column_headers_read", {})
        print(f"    _column_headers_read: {json.dumps(headers, ensure_ascii=False)}")

        # Consistency check
        cc = raw.get("_consistency_check", {})
        print(f"    _consistency_check: {cc}")


if __name__ == "__main__":
    main()
