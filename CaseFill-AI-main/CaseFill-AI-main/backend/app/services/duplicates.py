"""
Cross-case duplicate detection service.
Checks child CRC, mother CNIC, and father CNIC against existing cases.
"""

import json
import re

from ..db import get_db, dict_rows


def clean_digits(s: str | None) -> str:
    """Strip non-digit characters from a string."""
    if not s:
        return ""
    return re.sub(r"[^0-9]", "", s)


def check_duplicates(
    child_crc: str | None = None,
    mother_cnic: str | None = None,
    father_cnic: str | None = None,
    current_case_id: str | None = None,
) -> dict:
    """
    Check for duplicate cases based on normalized identifiers.

    Returns:
        dict with isDuplicate (bool) and matches (list)
    """
    target_child_crc = clean_digits(child_crc)
    target_mother_cnic = clean_digits(mother_cnic)
    target_father_cnic = clean_digits(father_cnic)

    if not target_child_crc and not target_mother_cnic and not target_father_cnic:
        return {"isDuplicate": False, "matches": []}

    with get_db() as conn:
        # Fetch all cases (excluding current)
        query = "SELECT * FROM cases WHERE 1=1"
        params = []
        if current_case_id:
            query += " AND id != ?"
            params.append(current_case_id)

        rows = conn.execute(query, params).fetchall()
        cases = [dict(r) for r in rows]

    matches = []

    for case in cases:
        compiled = {}
        if case.get("compiled_json"):
            try:
                compiled = json.loads(case["compiled_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        existing_child_crc = clean_digits(case.get("child_crc"))
        existing_mother_cnic = clean_digits(case.get("mother_cnic"))
        existing_father_cnic = clean_digits(case.get("father_cnic"))

        matched_case_summary = {
            "id": case["id"],
            "caseNumber": case["case_number"],
            "childName": compiled.get("childDetails", {}).get("name", "Unknown"),
            "status": case["status"],
            "submittedAt": case.get("submitted_at"),
            "fsoName": case.get("assigned_fso_id"),
            "regionName": case.get("region_id"),
            "familyName": compiled.get("familyName"),
            "familyPhone": compiled.get("familyPhone"),
        }

        # 1. Check Child CRC match
        if target_child_crc and len(target_child_crc) >= 5 and existing_child_crc == target_child_crc:
            matches.append({
                "matchedField": "child_crc",
                "matchedFieldLabel": "Child's B-Form / CRC Number",
                "matchedValue": case.get("child_crc"),
                "matchedCase": matched_case_summary,
            })
            continue

        # 2. Check Sibling CRC match
        if target_child_crc and len(target_child_crc) >= 5:
            siblings = compiled.get("siblings", [])
            for sibling in siblings:
                sibling_crc = clean_digits(sibling.get("regNumber"))
                if sibling_crc == target_child_crc:
                    matches.append({
                        "matchedField": "child_crc",
                        "matchedFieldLabel": f"Registered as Sibling ({sibling.get('name', 'Unknown')})",
                        "matchedValue": sibling.get("regNumber"),
                        "matchedCase": matched_case_summary,
                    })
                    break
            if matches and matches[-1]["matchedCase"]["id"] == case["id"]:
                continue

        # 3. Check Mother CNIC match
        if target_mother_cnic and len(target_mother_cnic) >= 9 and existing_mother_cnic == target_mother_cnic:
            matches.append({
                "matchedField": "mother_cnic",
                "matchedFieldLabel": "Mother's National CNIC",
                "matchedValue": case.get("mother_cnic"),
                "matchedCase": matched_case_summary,
            })
            continue

        # 4. Check Father CNIC match
        if target_father_cnic and len(target_father_cnic) >= 9 and existing_father_cnic == target_father_cnic:
            matches.append({
                "matchedField": "father_cnic",
                "matchedFieldLabel": "Deceased Father's CNIC",
                "matchedValue": case.get("father_cnic"),
                "matchedCase": matched_case_summary,
            })
            continue

    return {
        "isDuplicate": len(matches) > 0,
        "matches": matches,
    }
