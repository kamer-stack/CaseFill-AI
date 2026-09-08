"""Step-7 live VLM extraction runner.

For each synthetic B-form PNG under tests/fixtures/synthetic_bforms/:
  1. Render the exact Qwen prompt and audit it for test-value contamination.
  2. Call extract_document() (Qwen-VL API) once per image.
  3. Run postprocess_bform() and validate_extraction() on the same raw payload
     so the three stages (raw / postprocessed / validated) are captured
     independently.
  4. Write the triple (raw, postprocessed, validated) + ground truth to
     results/<test_id>.json and emit a console summary.

Run from the backend/ directory:
    venv/Scripts/python.exe tests/fixtures/synthetic_bforms/run_extraction.py

Requires API_KEY to be set in .env. Real API call; ~6 calls total.
"""

from __future__ import annotations
import copy
import json
import os
import re
import sys
from pathlib import Path

# Make the app package importable when run as a script.
_backend = str(Path(__file__).resolve().parents[3])
sys.path.insert(0, _backend)

from dotenv import load_dotenv
load_dotenv(str(Path(__file__).resolve().parents[3] / ".env"))

from app.services.prompts import build_bform_prompt      # noqa: E402
from app.services.extraction import load_schemas, extract_document  # noqa: E402
from app.services.validation import (                     # noqa: E402
    postprocess_bform, validate_extraction,
)


FIXTURES = Path(__file__).resolve().parent
RESULTS = FIXTURES / "results"


# Ground truth — each entry keyed by test id (lower-case).
# Names here are the ROMAN transliterations the model is expected to produce;
# small spelling variations are acceptable (e.g. Shafiq / Shafique).
GROUND_TRUTH = {
    "a": {
        "scenario": "All identities distinct",
        "crc_number": "99-TEST-A-2024",
        "applicant_name": "Shafiq ur Rehman Siddiqui",
        "applicant_cnic_number": "99101-7111111-1",
        "father_name": "Shafiq ur Rehman Siddiqui",
        "father_cnic_number": "99101-7111111-1",
        "mother_name": "Zarghuna Shafiq",
        "mother_cnic_number": "99102-8222222-2",
        "children": [
            {
                "serial_number": 1,
                "child_name": "Imran Shafiq",
                "child_registration_number": "99-2024-111111",
                "gender_relation": "son",
                "date_of_birth": "15-03-2018",
            }
        ],
    },
    "b": {
        "scenario": "Applicant == father (legitimately same)",
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
    },
    "c": {
        "scenario": "Applicant != father (mother is applicant)",
        "crc_number": "99-TEST-C-2024",
        "applicant_name": "Mahjabeen Parwaz",
        "applicant_cnic_number": "99301-8555555-5",
        "father_name": "Parwaz Hussain Shah",
        "father_cnic_number": "99302-7666666-6",
        "mother_name": "Mahjabeen Parwaz",
        "mother_cnic_number": "99301-8555555-5",
        "children": [
            {
                "serial_number": 1,
                "child_name": "Yasir Parwaz",
                "child_registration_number": "99-2024-555555",
                "gender_relation": "son",
                "date_of_birth": "10-11-2020",
            }
        ],
    },
    "d": {
        "scenario": "Father/mother names visually similar",
        "crc_number": "99-TEST-D-2024",
        "applicant_name": "Abdul Qadir Mohmand",
        "applicant_cnic_number": "99401-7777777-7",
        "father_name": "Abdul Qadir Mohmand",
        "father_cnic_number": "99401-7777777-7",
        "mother_name": "Abda Al Qadir Mohmand",
        "mother_cnic_number": "99402-8888888-8",
        "children": [
            {
                "serial_number": 1,
                "child_name": "Hammad Abdul Qadir",
                "child_registration_number": "99-2024-777777",
                "gender_relation": "son",
                "date_of_birth": "05-02-2017",
            }
        ],
    },
    "e": {
        "scenario": "Mother cell empty -> expect null",
        "crc_number": "99-TEST-E-2024",
        "applicant_name": "Fazal Karim Awan",
        "applicant_cnic_number": "99501-7999999-9",
        "father_name": "Fazal Karim Awan",
        "father_cnic_number": "99501-7999999-9",
        "mother_name": None,
        "mother_cnic_number": None,
        "children": [
            {
                "serial_number": 1,
                "child_name": "Nabeel Fazal",
                "child_registration_number": "99-2024-999999",
                "gender_relation": "son",
                "date_of_birth": "28-09-2021",
            }
        ],
    },
    "f": {
        "scenario": "Structural mirror of historical failure (3 children)",
        "crc_number": "99-TEST-F-2024",
        "applicant_name": "Ihtisham Ahmed Maghar",
        "applicant_cnic_number": "99601-7101010-1",
        "father_name": "Ihtisham Ahmed Maghar",
        "father_cnic_number": "99601-7101010-1",
        "mother_name": "Ramzana Ihtisham",
        "mother_cnic_number": "99602-8202020-2",
        "children": [
            {"serial_number": 1, "child_name": "Rehan Ihtisham",
             "child_registration_number": "99-2024-101010",
             "gender_relation": "son", "date_of_birth": "12-04-2016"},
            {"serial_number": 2, "child_name": "Aisha Ihtisham",
             "child_registration_number": "99-2024-303030",
             "gender_relation": "daughter", "date_of_birth": "08-01-2019"},
            {"serial_number": 3, "child_name": "Ziyad Ihtisham",
             "child_registration_number": "99-2024-505050",
             "gender_relation": "son", "date_of_birth": "30-06-2022"},
        ],
    },
}


# Names that should NEVER appear in any rendered prompt (Step-6 decontamination
# plus synthetic test names). Presence of any would invalidate the test.
BANNED_TOKENS = [
    # Step-6 decontaminated
    "Ayesha Bibi", "Muhammad Aslam", "Muhammad Ibrahim",
    "Zahida", "Naseem", "Ishtiaq Ahmed Mughal",
    # Synthetic ground-truth names (must not leak into prompt)
    "Shafiq", "Zarghuna", "Barkat", "Hoorain", "Mahjabeen",
    "Parwaz", "Abdul Qadir", "Abda Al", "Fazal Karim", "Ihtisham",
    "Ramzana", "Rehan Ihtisham", "Ziyad",
]


def audit_prompt(prompt: str) -> list[str]:
    """Return a list of banned tokens that appear in the rendered prompt."""
    found = []
    for tok in BANNED_TOKENS:
        if re.search(rf"\b{re.escape(tok)}\b", prompt, re.IGNORECASE):
            found.append(tok)
    return found


def run_single(test_id: str, image_path: Path) -> dict:
    """Run the full pipeline on one synthetic image and capture each stage."""
    schemas = load_schemas()
    doc_schema = schemas["b_form"]
    prompt = build_bform_prompt(doc_schema, target_child_serial_number=None)

    leaks = audit_prompt(prompt)

    # Stage 1: raw Qwen call
    raw = extract_document(image_path, "b_form", target_child_serial_number=None)
    raw_extracted = raw["extracted"]
    raw_model_text = raw["raw_model_text"]

    # Stage 2: postprocess (deep-copy so we can compare)
    post = postprocess_bform(copy.deepcopy(raw_extracted), raw_model_text=raw_model_text)

    # Stage 3: validate (operates on the postprocessed dict)
    validated = validate_extraction("b_form", copy.deepcopy(post))

    return {
        "test_id": test_id,
        "image": image_path.name,
        "model": raw["model"],
        "duration_ms": raw["duration_ms"],
        "prompt_length_chars": len(prompt),
        "prompt_banned_token_leaks": leaks,
        "ground_truth": GROUND_TRUTH[test_id],
        "raw_extracted": raw_extracted,
        "raw_model_text": raw_model_text,
        "postprocessed": post,
        "validated": validated,
    }


def print_summary(record: dict) -> None:
    """Print a compact per-field summary to stdout."""
    tid = record["test_id"].upper()
    gt = record["ground_truth"]
    val = record["validated"]
    print(f"\n{'='*72}\nTEST {tid}: {gt['scenario']}\n{'='*72}")
    if record["prompt_banned_token_leaks"]:
        print(f"PROMPT LEAK DETECTED: {record['prompt_banned_token_leaks']}")
    else:
        print("Prompt audit: CLEAN (no test names or decontaminated names).")

    top_fields = [
        "crc_number", "applicant_name", "applicant_cnic_number",
        "father_name", "father_cnic_number",
        "mother_name", "mother_cnic_number",
    ]
    for f in top_fields:
        gt_val = gt.get(f)
        val_val = val.get(f)
        conf = (val.get("confidence") or {}).get(f) if isinstance(val.get("confidence"), dict) else None
        print(f"  {f:28s}  GT={gt_val!r:40s}  GOT={val_val!r:40s}  conf={conf}")

    for i, gt_c in enumerate(gt["children"]):
        got_c = (val.get("children") or [{}])[i:i+1]
        got_c = got_c[0] if got_c else {}
        print(f"  child[{i}] (serial {gt_c['serial_number']})")
        for k in ("child_name", "child_registration_number", "gender_relation", "date_of_birth"):
            gv = gt_c.get(k)
            vv = got_c.get(k)
            cc = None
            cconf = (val.get("confidence") or {}).get("children")
            if isinstance(cconf, list) and i < len(cconf) and isinstance(cconf[i], dict):
                cc = cconf[i].get(k)
            print(f"      {k:30s}  GT={gv!r:35s}  GOT={vv!r:35s}  conf={cc}")

    # Cross-field leakage check
    print("  -- cross-field leakage --")
    vals = {k: str(val.get(k) or "").strip() for k in top_fields if k.endswith("_cnic_number") or k.endswith("_name")}
    for (a, b) in [
        ("father_name", "mother_name"),
        ("father_cnic_number", "mother_cnic_number"),
        ("applicant_cnic_number", "father_cnic_number"),
        ("applicant_name", "father_name"),
    ]:
        if vals[a] and vals[b] and vals[a] == vals[b]:
            gt_a = gt.get(a)
            gt_b = gt.get(b)
            note = "OK (intended same)" if (gt_a and gt_b and gt_a == gt_b) else "SUSPICIOUS (ground truth differs)"
            print(f"    {a} == {b}  ->  {note}")


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    if not os.getenv("API_KEY"):
        print("ERROR: API_KEY not set in .env", file=sys.stderr)
        sys.exit(2)

    # Iterate tests a..f in order
    for test_id in ["a", "b", "c", "d", "e", "f"]:
        img = FIXTURES / f"test_{test_id}.png"
        if not img.exists():
            print(f"SKIP {test_id}: missing {img}")
            continue
        print(f"\n>> Running Test {test_id.upper()}  ({img.name})")
        try:
            record = run_single(test_id, img)
        except Exception as e:
            print(f"ERROR running {test_id}: {e}")
            record = {"test_id": test_id, "error": str(e)}
        out_path = RESULTS / f"test_{test_id}.json"
        out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"   wrote {out_path.name}")
        if "error" not in record:
            print_summary(record)


if __name__ == "__main__":
    main()
