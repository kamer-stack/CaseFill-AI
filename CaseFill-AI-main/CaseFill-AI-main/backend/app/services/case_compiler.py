"""
Case compilation service.
Builds the CompiledCaseRecord from extracted documents + routing + metadata.
"""

import json
from datetime import datetime


def compile_case_record(
    case_id: str,
    case_number: str,
    documents: dict,
    cross_checks: list[dict],
    routing_result: dict,
    family_info: dict,
    fso_info: dict | None = None,
    intake_duration_seconds: float = 0,
    discrepancy_note: str = "",
    submission_source: str = "fso_manual",
) -> dict:
    """
    Compile a complete case record from all extracted data.

    Args:
        case_id: Unique case identifier
        case_number: Human-readable case number (OFSP-YYYY-NNNN)
        documents: dict of doc_type → extracted data
        cross_checks: list of cross-check results
        routing_result: region routing output
        family_info: {id, name, phone}
        fso_info: {id, name} or None
        intake_duration_seconds: time taken for intake
        discrepancy_note: FSO acknowledgment notes
        submission_source: 'fso_manual' | 'family_self_service' | 'fso_field_collected'
    """
    b_form = documents.get("b_form", {})
    father_cnic = documents.get("father_cnic", {})
    mother_cnic = documents.get("mother_cnic", {})
    death_cert = documents.get("death_certificate", {})
    result_card = documents.get("result_card", {})
    child_pic = documents.get("child_picture", {})
    address = documents.get("address", {})
    mother_edu = documents.get("mother_education", {})

    # Find target child from B-form
    children = b_form.get("children", [])
    target_child = None
    for child in children:
        if child.get("is_target_child"):
            target_child = child
            break
    if not target_child and children:
        target_child = children[0]

    # Build child details
    child_details = {
        "name": _val(target_child, "child_name") if target_child else "",
        "photoQuality": child_pic.get("quality_check", "unknown"),
        "crcOrRegNumber": _val(target_child, "child_registration_number") if target_child else "",
        "gender": _val(target_child, "gender_relation") if target_child else "",
        "dateOfBirth": _val(target_child, "date_of_birth") if target_child else "",
        "grade": _val(result_card, "class_grade"),
        "schoolName": _val(result_card, "school_name"),
        "examScore": _val(result_card, "result_percentage_or_grade"),
        "academicYear": _val(result_card, "year"),
    }

    # Build father details
    father_details = {
        "name": _val(father_cnic, "name") or _val(b_form, "father_name"),
        "cnic": _val(father_cnic, "cnic_number") or _val(b_form, "father_cnic_number"),
        "dateOfBirth": _val(father_cnic, "date_of_birth"),
        "dateOfDeath": _val(death_cert, "date_of_death"),
        "deathRegNumber": _val(death_cert, "registration_number"),
        "deathUnionCouncil": _val(death_cert, "issuing_union_council"),
        "isDeceasedConfirmed": bool(death_cert.get("deceased_name")),
    }

    # Build mother details
    mother_details = {
        "name": _val(mother_cnic, "name") or _val(b_form, "mother_name"),
        "cnic": _val(mother_cnic, "cnic_number") or _val(b_form, "mother_cnic_number"),
        "dateOfBirth": _val(mother_cnic, "date_of_birth"),
        "educationLevel": mother_edu.get("education_level", ""),
        "addressOnCnic": _val(mother_cnic, "address"),
    }

    # Build siblings list
    siblings = []
    for child in children:
        siblings.append({
            "name": _val(child, "child_name"),
            "regNumber": _val(child, "child_registration_number"),
            "relation": _val(child, "gender_relation"),
            "dob": _val(child, "date_of_birth"),
        })

    # Compute metrics
    manual_baseline = 780  # 13 minutes
    time_saved = max(0, (manual_baseline - intake_duration_seconds) / 60)
    speedup = round((1 - intake_duration_seconds / manual_baseline) * 100) if manual_baseline > 0 else 0

    # Compute average confidence
    confidences = _collect_confidences(documents)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.95

    # Determine status
    is_assigned = routing_result.get("isAssigned", False)
    status = "pending_verification" if is_assigned else "unassigned"

    now = datetime.now().isoformat()

    record = {
        "id": case_id,
        "caseNumber": case_number,
        "status": status,
        "submissionSource": submission_source,
        "familyId": family_info.get("id"),
        "familyName": family_info.get("name"),
        "familyPhone": family_info.get("phone"),
        "regionId": routing_result.get("regionId"),
        "regionName": routing_result.get("regionName"),
        "assignedFsoId": routing_result.get("assignedFsoId") or (fso_info.get("id") if fso_info else None),
        "assignedFsoName": fso_info.get("name") if fso_info else None,
        "routingConfidence": routing_result.get("confidence"),
        "routingReason": routing_result.get("reason"),
        "fsoName": fso_info.get("name") if fso_info else None,
        "fsoId": fso_info.get("id") if fso_info else None,
        "createdAt": now,
        "submittedAt": now,
        "intakeDurationSeconds": intake_duration_seconds,
        "manualBaselineSeconds": manual_baseline,
        "timeSavedMinutes": round(time_saved, 1),
        "speedupPercentage": speedup,
        "childDetails": child_details,
        "fatherDetails": father_details,
        "motherDetails": mother_details,
        "residentialAddress": address.get("full_address", ""),
        "siblingsCount": len(siblings),
        "siblings": siblings,
        "crossCheckIssues": cross_checks,
        "discrepancyNotes": discrepancy_note,
        "averageConfidence": round(avg_confidence, 2),
    }

    return record


def extract_duplicate_keys(documents: dict) -> dict:
    """Extract the key identifiers for duplicate detection from documents."""
    b_form = documents.get("b_form", {})
    father_cnic = documents.get("father_cnic", {})
    mother_cnic = documents.get("mother_cnic", {})

    children = b_form.get("children", [])
    target_child = None
    for child in children:
        if child.get("is_target_child"):
            target_child = child
            break
    if not target_child and children:
        target_child = children[0]

    return {
        "child_crc": _val(target_child, "child_registration_number") if target_child else None,
        "mother_cnic": _val(mother_cnic, "cnic_number") or _val(b_form, "mother_cnic_number"),
        "father_cnic": _val(father_cnic, "cnic_number") or _val(b_form, "father_cnic_number"),
    }


def _val(doc: dict | None, field: str) -> str:
    """Safely extract a string value from a document dict."""
    if doc is None:
        return ""
    val = doc.get(field)
    if val is None:
        return ""
    return str(val)


def _collect_confidences(documents: dict) -> list[float]:
    """Collect all confidence scores from extracted documents."""
    scores = []
    for doc_type, doc_data in documents.items():
        if isinstance(doc_data, dict):
            conf = doc_data.get("confidence")
            if isinstance(conf, dict):
                for v in conf.values():
                    if isinstance(v, (int, float)):
                        scores.append(float(v))
            elif isinstance(conf, (int, float)):
                scores.append(float(conf))
    return scores
