from pipeline import extract_document
import json

TEST_CASES = [
    ("test_cnic.png", "mother_cnic"),
    ("test_father_cnic.png", "father_cnic"),
    ("test_bform.png", "b_form"),
    ("test_death_certificate.png", "death_certificate"),
    ("test_result_card.png", "result_card"),
]

print("=" * 60)
print("DOCUMENT EXTRACTION PIPELINE TEST")
print("=" * 60)

results = {}

for image_file, doc_type in TEST_CASES:
    print(f"\n{'─' * 60}")
    print(f"Processing: {image_file} as {doc_type}")
    print(f"{'─' * 60}")
    
    try:
        # Pass target_child_serial_number for b_form
        if doc_type == "b_form":
            result = extract_document(image_file, doc_type, target_child_serial_number=3)
        else:
            result = extract_document(image_file, doc_type)
        results[doc_type] = result
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except FileNotFoundError as e:
        print(f"⚠ SKIPPED - {e}")
    except Exception as e:
        print(f"✗ ERROR - {e}")


def compare_values(val1, val2):
    """Compare two values and return status."""
    if val1 is None or val2 is None:
        return "NEEDS_REVIEW", "missing value"
    # Normalize strings for comparison (lowercase, strip whitespace)
    v1 = str(val1).strip().lower()
    v2 = str(val2).strip().lower()
    if v1 == v2:
        return "MATCH", None
    else:
        return "MISMATCH", f"'{val1}' vs '{val2}'"


# Cross-document validation
print(f"\n{'=' * 60}")
print("CROSS-DOCUMENT VALIDATION")
print("=" * 60)

comparisons = []

# 1. b_form father_cnic_number vs father_cnic cnic_number
if "b_form" in results and "father_cnic" in results:
    status, detail = compare_values(
        results["b_form"].get("father_cnic_number"),
        results["father_cnic"].get("cnic_number")
    )
    comparisons.append(("Father CNIC number", status, detail))
else:
    comparisons.append(("Father CNIC number", "NEEDS_REVIEW", "documents missing"))

# 2. b_form mother_cnic_number vs mother_cnic cnic_number
if "b_form" in results and "mother_cnic" in results:
    status, detail = compare_values(
        results["b_form"].get("mother_cnic_number"),
        results["mother_cnic"].get("cnic_number")
    )
    comparisons.append(("Mother CNIC number", status, detail))
else:
    comparisons.append(("Mother CNIC number", "NEEDS_REVIEW", "documents missing"))

# 3. b_form father_name vs father_cnic name
if "b_form" in results and "father_cnic" in results:
    status, detail = compare_values(
        results["b_form"].get("father_name"),
        results["father_cnic"].get("name")
    )
    comparisons.append(("Father name (B-form vs CNIC)", status, detail))
else:
    comparisons.append(("Father name (B-form vs CNIC)", "NEEDS_REVIEW", "documents missing"))

# 4. b_form father_name vs death_certificate deceased_name
if "b_form" in results and "death_certificate" in results:
    status, detail = compare_values(
        results["b_form"].get("father_name"),
        results["death_certificate"].get("deceased_name")
    )
    comparisons.append(("Father name (B-form vs Death cert)", status, detail))
else:
    comparisons.append(("Father name (B-form vs Death cert)", "NEEDS_REVIEW", "documents missing"))

# 5. b_form target child_name vs result_card child_name
if "b_form" in results and "result_card" in results:
    # Find the target child (is_target_child: true) in the children array
    target_child = None
    for child in results["b_form"].get("children", []):
        if child.get("is_target_child") is True:
            target_child = child
            break
    
    if target_child:
        status, detail = compare_values(
            target_child.get("child_name"),
            results["result_card"].get("child_name")
        )
        comparisons.append(("Target child name (B-form vs Result card)", status, detail))
    else:
        comparisons.append(("Target child name (B-form vs Result card)", "NEEDS_REVIEW", "no target child found"))
else:
    comparisons.append(("Target child name (B-form vs Result card)", "NEEDS_REVIEW", "documents missing"))

# Print summary checklist
print("\nValidation Checklist:")
print("─" * 60)
for label, status, detail in comparisons:
    if status == "MATCH":
        print(f"✅ {label}: {status}")
    elif status == "MISMATCH":
        print(f"❌ {label}: {status} ({detail})")
    else:
        print(f"⚠️  {label}: {status} ({detail})")

print(f"\n{'=' * 60}")
print("TEST COMPLETE")
print("=" * 60)
