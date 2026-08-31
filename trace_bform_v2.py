"""Four-stage diagnostic trace for B-form extraction on test_bform v2.png."""
import json
import copy
import sqlite3
from pathlib import Path

from pipeline import extract_document, save_extraction
from validation import postprocess_bform, validate_extraction

IMAGE_PATH = Path("sample docs/test_bform v2.png")

print("=" * 70)
print("STAGE 1: Raw Qwen-VL output (before any post-processing)")
print("=" * 70)
raw = extract_document(IMAGE_PATH, "b_form", target_child_serial_number=3)
print(json.dumps(raw, ensure_ascii=False, indent=2))

print("\n" + "=" * 70)
print("STAGE 2: After postprocess_bform")
print("=" * 70)
stage2 = postprocess_bform(copy.deepcopy(raw))
print(json.dumps(stage2, ensure_ascii=False, indent=2))

print("\n" + "=" * 70)
print("STAGE 3: After validate_extraction")
print("=" * 70)
stage3 = validate_extraction("b_form", copy.deepcopy(stage2))
print(json.dumps(stage3, ensure_ascii=False, indent=2))

print("\n" + "=" * 70)
print("STAGE 4: SQLite persistence check")
print("=" * 70)
save_extraction("b_form", copy.deepcopy(stage3))
conn = sqlite3.connect("extractions.db")
cursor = conn.cursor()
cursor.execute(
    "SELECT id, document_type, extracted_json, timestamp FROM extractions ORDER BY id DESC LIMIT 1"
)
row = cursor.fetchone()
print(f"Saved row id={row[0]}, document_type={row[1]}, timestamp={row[3]}")
saved = json.loads(row[2])
print("Top-level mother_cnic_number:", saved.get("mother_cnic_number"))
print("Top-level father_cnic_number:", saved.get("father_cnic_number"))
print("Validation errors:", json.dumps(saved.get("_validation_errors"), ensure_ascii=False))
print("Column corrections:", json.dumps(saved.get("_column_corrections"), ensure_ascii=False))
print("Children:")
for i, child in enumerate(saved.get("children", [])):
    print(f"  [{i}] child_name={child.get('child_name')!r}, "
          f"child_registration_number={child.get('child_registration_number')!r}")
print("Confidence:", json.dumps(saved.get("confidence"), ensure_ascii=False, indent=2))
conn.close()
