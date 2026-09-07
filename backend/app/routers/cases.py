"""
Case management routes: CRUD, document upload, extraction, submission, verification.
"""

import json
import os
import secrets
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends

from ..db import get_db, dict_row, dict_rows
from ..config import UPLOADS_DIR
from ..models import (
    CaseCreateRequest, ExtractionRequest, FieldEditRequest,
    ValidateFieldRequest,
    SubmitRequest, VerifyRequest, AssignRequest,
    DonorStatusRequest, AidTransferRequest,
)
from ..seed import hash_password
from ..services.extraction import extract_document, DOCUMENT_TYPES
from ..services.cross_check import run_cross_checks
from ..services.validation import (
    validate_field, validate_extraction,
    postprocess_bform, postprocess_cnic,
)
from ..services.duplicates import check_duplicates
from ..services.routing_engine import route_address
from ..services.case_compiler import compile_case_record, extract_duplicate_keys
from .auth import get_current_user, require_role, normalize_cnic

router = APIRouter(prefix="/api/cases", tags=["cases"])


def _generate_case_number() -> str:
    """Generate a unique case number: OFSP-YYYY-NNNN."""
    year = datetime.now().year
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM cases WHERE case_number LIKE ?",
            (f"OFSP-{year}-%",),
        ).fetchone()
        next_num = (row["cnt"] if row else 0) + 1
    return f"OFSP-{year}-{next_num:04d}"


def _serialize_case(case: dict) -> dict:
    """Parse JSON columns on a case row for API responses."""
    if case.get("aid_transfer_log"):
        try:
            case["aid_transfer_log"] = json.loads(case["aid_transfer_log"])
        except (json.JSONDecodeError, TypeError):
            case["aid_transfer_log"] = []
    else:
        case["aid_transfer_log"] = []
    case["donor_arranged"] = bool(case.get("donor_arranged"))
    return case


@router.get("")
def list_cases(
    role: str = None,
    fso_id: str = None,
    family_id: str = None,
    region_id: str = None,
    status: str = None,
    user: dict = Depends(get_current_user),
):
    """List cases with role-based filtering.

    Family (child) logins are always scoped server-side to their own cases.
    """
    # Server-side enforcement: child/family logins only ever see their own case records
    if user["role"] == "family":
        role = "family"
        family_id = user["id"]

    with get_db() as conn:
        query = """SELECT c.*,
                          sf.name AS submitted_by_fso_name,
                          af.name AS assigned_fso_name,
                          vf.name AS verified_by_fso_name
                   FROM cases c
                   LEFT JOIN fsos sf ON c.submitted_by_fso_id = sf.id
                   LEFT JOIN fsos af ON c.assigned_fso_id = af.id
                   LEFT JOIN fsos vf ON c.verified_by_fso_id = vf.id
                   WHERE 1=1"""
        params = []

        if role == "family" and family_id:
            query += " AND c.family_id = ?"
            params.append(family_id)
        elif role == "fso" and fso_id:
            # FSO sees their assigned cases + cases in their regions
            fso_row = conn.execute(
                "SELECT assigned_region_ids FROM fsos WHERE id = ?", (fso_id,)
            ).fetchone()
            region_ids = json.loads(fso_row["assigned_region_ids"]) if fso_row and fso_row["assigned_region_ids"] else []
            if region_ids:
                placeholders = ",".join(["?"] * len(region_ids))
                query += f" AND (c.assigned_fso_id = ? OR c.region_id IN ({placeholders}))"
                params.append(fso_id)
                params.extend(region_ids)
            else:
                query += " AND c.assigned_fso_id = ?"
                params.append(fso_id)
        elif region_id and region_id != "all":
            query += " AND c.region_id = ?"
            params.append(region_id)

        if status and status != "all":
            query += " AND c.status = ?"
            params.append(status)

        query += " ORDER BY c.created_at DESC"
        rows = conn.execute(query, params).fetchall()

    return {"cases": [_serialize_case(dict(r)) for r in rows]}


@router.post("")
def create_case(
    req: CaseCreateRequest,
    user: dict = Depends(require_role("fso", "admin")),
):
    """Create a new draft case (FSO/Admin only — families cannot self-register cases)."""
    case_id = f"case_{uuid.uuid4().hex[:12]}"
    case_number = _generate_case_number()

    with get_db() as conn:
        conn.execute(
            """INSERT INTO cases (id, case_number, status, submission_source, family_id, created_by_user_id)
               VALUES (?, ?, 'draft', ?, NULL, ?)""",
            (case_id, case_number, req.submission_source, user["id"]),
        )
        # Seed 8 document slots
        doc_types = ["child_picture", "result_card", "b_form", "death_certificate",
                      "mother_cnic", "father_cnic", "address", "mother_education"]
        for dt in doc_types:
            conn.execute(
                "INSERT INTO case_documents (case_id, doc_type, status) VALUES (?, ?, 'empty')",
                (case_id, dt),
            )

    # Create uploads directory
    case_dir = UPLOADS_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    return {"case_id": case_id, "case_number": case_number, "status": "draft"}


@router.get("/{case_id}")
def get_case(case_id: str, user: dict = Depends(get_current_user)):
    """Get a case with all its documents."""
    with get_db() as conn:
        case_row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if not case_row:
            raise HTTPException(404, "Case not found")

        docs = conn.execute(
            "SELECT * FROM case_documents WHERE case_id = ?", (case_id,)
        ).fetchall()

        # Display-only enrichment: verifier name for the "Reviewed by" note
        # (must run inside the with-block — the connection closes after it)
        verifier = None
        if case_row["verified_by_fso_id"]:
            verifier = conn.execute(
                "SELECT name FROM fsos WHERE id = ?", (case_row["verified_by_fso_id"],)
            ).fetchone()

    case = dict(case_row)
    if verifier:
        case["verified_by_fso_name"] = verifier["name"]

    # Child/family logins are strictly read-only and scoped to their own case record
    if user["role"] == "family" and case.get("family_id") != user["id"]:
        raise HTTPException(403, "You do not have access to this case.")

    case = _serialize_case(case)
    case["documents"] = {}
    for doc in docs:
        d = dict(doc)
        # Parse JSON fields
        if d.get("extracted_json"):
            try:
                d["extracted_json"] = json.loads(d["extracted_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        if d.get("manual_edits_json"):
            try:
                d["manual_edits_json"] = json.loads(d["manual_edits_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        # Add image URL
        if d.get("file_path"):
            d["imageUrl"] = f"/uploads/{case_id}/{d['file_path']}"
        case["documents"][d["doc_type"]] = d

    if case.get("compiled_json"):
        try:
            case["compiled"] = json.loads(case["compiled_json"])
        except (json.JSONDecodeError, TypeError):
            pass

    return case


@router.post("/{case_id}/documents")
async def upload_document(
    case_id: str,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(require_role("fso", "admin")),
):
    """Upload a document image for a case (FSO/Admin only, no family self-upload)."""
    if doc_type not in DOCUMENT_TYPES:
        raise HTTPException(400, f"Invalid doc_type. Must be one of: {DOCUMENT_TYPES}")

    ext = Path(file.filename).suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".heic"):
        raise HTTPException(400, f"Unsupported file type: {ext}")

    # Save file
    case_dir = UPLOADS_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    # Remove any previously uploaded file for this slot (handles extension
    # changes so re-uploads never leave a stale image for extraction to find)
    for old_file in case_dir.glob(f"{doc_type}.*"):
        try:
            old_file.unlink()
        except OSError:
            pass

    filename = f"{doc_type}{ext}"
    save_path = case_dir / filename

    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Update document record
    with get_db() as conn:
        conn.execute(
            """UPDATE case_documents
               SET status = 'uploading', file_path = ?, original_filename = ?
               WHERE case_id = ? AND doc_type = ?""",
            (filename, file.filename, case_id, doc_type),
        )

    return {
        "doc_type": doc_type,
        "file_path": filename,
        "image_url": f"/uploads/{case_id}/{filename}",
        "status": "uploading",
    }


@router.post("/{case_id}/extract")
async def run_extraction(
    case_id: str,
    req: ExtractionRequest,
    user: dict = Depends(require_role("fso", "admin")),
):
    """Run AI extraction on a document (FSO/Admin only)."""
    if req.doc_type not in DOCUMENT_TYPES:
        raise HTTPException(400, f"Invalid doc_type. Must be one of: {DOCUMENT_TYPES}")

    # Find the uploaded file
    case_dir = UPLOADS_DIR / case_id
    matches = list(case_dir.glob(f"{req.doc_type}.*"))
    if not matches:
        raise HTTPException(404, "Document file not found. Upload first.")

    image_path = matches[0]

    # Update status to extracting
    with get_db() as conn:
        conn.execute(
            "UPDATE case_documents SET status = 'extracting' WHERE case_id = ? AND doc_type = ?",
            (case_id, req.doc_type),
        )

    try:
        result = extract_document(
            image_path, req.doc_type,
            target_child_serial_number=req.target_child_serial_number,
            cnic_format=req.cnic_format,
            target_child_registration_number=req.target_child_registration_number,
        )

        # Server-side post-processing: document-type-specific correction
        # (B-form column-swap + verbatim-source checks, CNIC cross-field
        # sanity checks), then field-level validation. The data dict is
        # mutated in place — invalid fields keep their raw value but have
        # confidence forced to 0, and a "_validation_errors" list is
        # attached for the frontend to surface.
        extracted = result["extracted"]
        raw_model_text = result.get("raw_model_text") or ""
        if isinstance(extracted, dict):
            if req.doc_type == "b_form":
                extracted = postprocess_bform(extracted, raw_model_text=raw_model_text)
                # Stash the FSO's own entry for the target child so the
                # cross-check step can compare it against what was actually
                # read off the B-form / result card — never used to pick
                # or override the target child itself.
                if req.target_child_name and req.target_child_name.strip():
                    extracted["_fso_target_child_name"] = req.target_child_name.strip()
            elif req.doc_type in ("father_cnic", "mother_cnic"):
                extracted = postprocess_cnic(extracted, req.doc_type)
            extracted = validate_extraction(req.doc_type, extracted)
            result["extracted"] = extracted

        # Save extraction result
        with get_db() as conn:
            conn.execute(
                """UPDATE case_documents
                   SET status = 'done', extracted_json = ?, extracted_at = ?,
                       extraction_ms = ?, model = ?
                   WHERE case_id = ? AND doc_type = ?""",
                (json.dumps(result["extracted"], ensure_ascii=False),
                 datetime.now().isoformat(), result["duration_ms"], result["model"],
                 case_id, req.doc_type),
            )

        return {
            "doc_type": req.doc_type,
            "extracted": result["extracted"],
            "model": result["model"],
            "duration_ms": result["duration_ms"],
            "image_url": f"/uploads/{case_id}/{image_path.name}",
        }

    except Exception as e:
        with get_db() as conn:
            conn.execute(
                "UPDATE case_documents SET status = 'error' WHERE case_id = ? AND doc_type = ?",
                (case_id, req.doc_type),
            )
        raise HTTPException(500, f"Extraction failed: {str(e)}")


@router.put("/{case_id}/fields")
def update_fields(
    case_id: str,
    req: FieldEditRequest,
    user: dict = Depends(require_role("fso", "admin")),
):
    """Update text-only fields (address, mother_education) or manual edits (FSO/Admin only).

    Invalid values are rejected before being saved — unlike extraction, where
    bad reads are kept with confidence forced to 0 for FSO review, manual edits
    come from a human and should be corrected at the point of entry.
    """
    # Resolve the leaf field name used for category lookup. For nested paths
    # like "children.0.child_name" we validate against "child_name".
    leaf_field = req.field_path.split(".")[-1]

    is_valid, error_msg = validate_field(leaf_field, req.new_value)
    if not is_valid:
        raise HTTPException(400, error_msg or f"Invalid value for '{req.field_path}'.")

    with get_db() as conn:
        doc_row = conn.execute(
            "SELECT * FROM case_documents WHERE case_id = ? AND doc_type = ?",
            (case_id, req.doc_type),
        ).fetchone()

        if not doc_row:
            raise HTTPException(404, "Document slot not found")

        if req.doc_type in ("address", "mother_education"):
            # Text-only slots — save directly
            data = {}
            if req.doc_type == "address":
                data = {"full_address": req.new_value or ""}
            elif req.doc_type == "mother_education":
                data = {"education_level": req.new_value or ""}

            conn.execute(
                """UPDATE case_documents
                   SET status = 'done', extracted_json = ?, extracted_at = ?
                   WHERE case_id = ? AND doc_type = ?""",
                (json.dumps(data), datetime.now().isoformat(), case_id, req.doc_type),
            )
        else:
            # Manual edit on extracted data
            existing = {}
            if doc_row["extracted_json"]:
                try:
                    existing = json.loads(doc_row["extracted_json"])
                except (json.JSONDecodeError, TypeError):
                    pass

            # Apply edit at field_path
            parts = req.field_path.split(".")
            target = existing
            for part in parts[:-1]:
                if isinstance(target, dict):
                    target = target.setdefault(part, {})
                elif isinstance(target, list):
                    target = target[int(part)]

            if isinstance(target, dict):
                target[parts[-1]] = req.new_value

            # Save manual edits
            edits = {}
            if doc_row["manual_edits_json"]:
                try:
                    edits = json.loads(doc_row["manual_edits_json"])
                except (json.JSONDecodeError, TypeError):
                    pass
            edits[req.field_path] = req.new_value

            conn.execute(
                """UPDATE case_documents
                   SET extracted_json = ?, manual_edits_json = ?
                   WHERE case_id = ? AND doc_type = ?""",
                (json.dumps(existing, ensure_ascii=False),
                 json.dumps(edits, ensure_ascii=False),
                 case_id, req.doc_type),
            )

    return {"success": True}


@router.post("/validate-field")
def validate_field_endpoint(
    req: ValidateFieldRequest,
    user: dict = Depends(get_current_user),
):
    """Validate a single field value against the same rules used for extraction
    and manual edits. Returns {valid, error}. Any authenticated user can call
    this — it's used by the frontend on blur before an edit is submitted."""
    is_valid, error_msg = validate_field(req.field_name, req.value)
    return {"valid": is_valid, "error": error_msg, "field_name": req.field_name}


@router.put("/{case_id}/documents/{doc_type}/not-provided")
def mark_not_provided(
    case_id: str,
    doc_type: str,
    reason: str = Form(...),
    user: dict = Depends(require_role("fso", "admin")),
):
    """Mark a document as not provided with a reason (FSO/Admin only)."""
    if doc_type != "father_cnic":
        raise HTTPException(400, "Only father_cnic can be marked as not provided.")

    with get_db() as conn:
        conn.execute(
            """UPDATE case_documents
               SET status = 'not_provided', not_provided_reason = ?, file_path = NULL
               WHERE case_id = ? AND doc_type = ?""",
            (reason, case_id, doc_type),
        )

    return {"success": True, "doc_type": doc_type, "status": "not_provided"}


@router.delete("/{case_id}/documents/{doc_type}")
def delete_document(
    case_id: str,
    doc_type: str,
    user: dict = Depends(require_role("fso", "admin")),
):
    """Delete an uploaded document image so the FSO can re-upload it (pre-submission only)."""
    if doc_type not in DOCUMENT_TYPES:
        raise HTTPException(400, f"Invalid doc_type. Must be one of: {DOCUMENT_TYPES}")

    with get_db() as conn:
        case_row = conn.execute("SELECT status FROM cases WHERE id = ?", (case_id,)).fetchone()
        if not case_row:
            raise HTTPException(404, "Case not found")
        if case_row["status"] != "draft":
            raise HTTPException(400, "Documents can only be deleted before the case is submitted.")

        doc_row = conn.execute(
            "SELECT id FROM case_documents WHERE case_id = ? AND doc_type = ?",
            (case_id, doc_type),
        ).fetchone()
        if not doc_row:
            raise HTTPException(404, "Document slot not found")

        conn.execute(
            """UPDATE case_documents
               SET status = 'empty', file_path = NULL, original_filename = NULL,
                   extracted_json = NULL, manual_edits_json = NULL,
                   not_provided_reason = NULL, extracted_at = NULL,
                   extraction_ms = NULL, model = NULL
               WHERE case_id = ? AND doc_type = ?""",
            (case_id, doc_type),
        )

    # Remove the image file(s) from disk
    case_dir = UPLOADS_DIR / case_id
    if case_dir.exists():
        for f in case_dir.glob(f"{doc_type}.*"):
            try:
                f.unlink()
            except OSError:
                pass

    return {"success": True, "doc_type": doc_type, "status": "empty"}


@router.post("/{case_id}/cross-check")
def cross_check(case_id: str, user: dict = Depends(require_role("fso", "admin"))):
    """Run cross-document validation for a case (FSO/Admin only)."""
    with get_db() as conn:
        docs = conn.execute(
            "SELECT doc_type, extracted_json FROM case_documents WHERE case_id = ? AND status = 'done'",
            (case_id,),
        ).fetchall()

    documents = {}
    for doc in docs:
        d = dict(doc)
        if d["extracted_json"]:
            try:
                documents[d["doc_type"]] = json.loads(d["extracted_json"])
            except (json.JSONDecodeError, TypeError):
                pass

    checks = run_cross_checks(documents)

    # Save run
    with get_db() as conn:
        conn.execute(
            "INSERT INTO cross_check_runs (case_id, results_json) VALUES (?, ?)",
            (case_id, json.dumps(checks)),
        )

    return {"checks": checks}


@router.get("/check-duplicate")
def check_duplicate_get(
    crc: str = None,
    child_crc: str = None,
    mother_cnic: str = None,
    father_cnic: str = None,
    current_case_id: str = None,
    user: dict = Depends(get_current_user),
):
    """Check for duplicate cases (GET)."""
    return check_duplicates(
        child_crc=child_crc or crc,
        mother_cnic=mother_cnic,
        father_cnic=father_cnic,
        current_case_id=current_case_id,
    )


@router.post("/check-duplicate")
def check_duplicate_post(body: dict, user: dict = Depends(get_current_user)):
    """Check for duplicate cases (POST)."""
    return check_duplicates(
        child_crc=body.get("child_crc") or body.get("crc"),
        mother_cnic=body.get("mother_cnic"),
        father_cnic=body.get("father_cnic"),
        current_case_id=body.get("current_case_id"),
    )


@router.post("/{case_id}/submit")
def submit_case(
    case_id: str,
    req: SubmitRequest,
    user: dict = Depends(require_role("fso", "admin")),
):
    """Submit a case for verification (FSO/Admin only — families cannot self-submit)."""
    with get_db() as conn:
        case_row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if not case_row:
            raise HTTPException(404, "Case not found")

        docs = conn.execute(
            "SELECT doc_type, extracted_json, status FROM case_documents WHERE case_id = ?",
            (case_id,),
        ).fetchall()

    case = dict(case_row)

    # Build documents dict
    documents = {}
    for doc in docs:
        d = dict(doc)
        if d["extracted_json"]:
            try:
                documents[d["doc_type"]] = json.loads(d["extracted_json"])
            except (json.JSONDecodeError, TypeError):
                pass

    # Run cross-checks
    cross_checks = run_cross_checks(documents)

    # Enforce acknowledgment if flags exist
    has_flags = any(c.get("status") in ("MISMATCH", "SIMILAR", "NEEDS_REVIEW", "DIFFERENT_SCRIPT") for c in cross_checks)
    if has_flags and not req.acknowledgment.strip():
        raise HTTPException(
            400,
            "Acknowledgment is required when there are unresolved flags.",
        )

    # Route to region
    address_data = documents.get("address", {})
    address_str = address_data.get("full_address", "")
    routing = route_address(address_str)

    # Family details come from the extracted documents (mother's record)
    b_form_doc = documents.get("b_form", {})
    mother_doc = documents.get("mother_cnic", {})
    family_info = {
        "id": case.get("family_id"),
        "name": (mother_doc.get("name") or b_form_doc.get("mother_name") or "").strip(),
        "phone": "",
    }

    fso_info = None
    if user["role"] == "fso":
        fso_info = {"id": user.get("fso_id") or user["id"], "name": user["name"]}

    # Determine final assignment
    region_id = routing.get("regionId")
    assigned_fso_id = routing.get("assignedFsoId")
    submitted_by_fso_id = None
    status = "pending_verification" if routing.get("isAssigned") else "unassigned"

    # A case submitted by an FSO goes straight into that FSO's own queue,
    # regardless of address routing. Admin sees the case attributed to that FSO.
    if user["role"] == "fso":
        submitted_by_fso_id = user.get("fso_id") or user["id"]
        assigned_fso_id = submitted_by_fso_id
        status = "pending_verification"
        if not region_id:
            # Fall back to the submitting FSO's first assigned region
            with get_db() as conn:
                fso_row = conn.execute(
                    "SELECT assigned_region_ids FROM fsos WHERE id = ?", (submitted_by_fso_id,)
                ).fetchone()
            if fso_row and fso_row["assigned_region_ids"]:
                try:
                    fso_regions = json.loads(fso_row["assigned_region_ids"])
                    if fso_regions:
                        region_id = fso_regions[0]
                except (json.JSONDecodeError, TypeError):
                    pass

    # Validate foreign keys before saving
    with get_db() as conn:
        if region_id:
            row = conn.execute("SELECT id FROM regions WHERE id = ?", (region_id,)).fetchone()
            if not row:
                region_id = None
        if assigned_fso_id:
            row = conn.execute("SELECT id FROM fsos WHERE id = ? AND active = 1", (assigned_fso_id,)).fetchone()
            if not row:
                assigned_fso_id = None
        if not assigned_fso_id:
            status = "unassigned"
        if submitted_by_fso_id:
            row = conn.execute("SELECT id FROM fsos WHERE id = ?", (submitted_by_fso_id,)).fetchone()
            if not row:
                submitted_by_fso_id = None

    # Keep the compiled record consistent with the final assignment
    routing = dict(routing)
    routing["regionId"] = region_id
    routing["assignedFsoId"] = assigned_fso_id
    routing["isAssigned"] = bool(assigned_fso_id)

    record = compile_case_record(
        case_id=case_id,
        case_number=case["case_number"],
        documents=documents,
        cross_checks=cross_checks,
        routing_result=routing,
        family_info=family_info,
        fso_info=fso_info,
        discrepancy_note=req.acknowledgment,
        submission_source=case.get("submission_source", "fso_manual"),
    )

    # Extract duplicate keys
    dup_keys = extract_duplicate_keys(documents)

    # Save
    with get_db() as conn:
        conn.execute(
            """UPDATE cases SET
               status = ?, submitted_at = ?, compiled_json = ?,
               region_id = ?, assigned_fso_id = ?, submitted_by_fso_id = ?,
               routing_confidence = ?, routing_reason = ?,
               child_crc = ?, mother_cnic = ?, father_cnic = ?,
               average_confidence = ?
               WHERE id = ?""",
            (status, datetime.now().isoformat(),
             json.dumps(record, ensure_ascii=False),
             region_id, assigned_fso_id, submitted_by_fso_id,
             routing.get("confidence"), routing.get("reason"),
             dup_keys.get("child_crc"), dup_keys.get("mother_cnic"), dup_keys.get("father_cnic"),
             record.get("averageConfidence"),
             case_id),
        )

    return {
        "success": True,
        "case_id": case_id,
        "case_number": case["case_number"],
        "status": status,
        "routing": routing,
        "duplicate_check": check_duplicates(
            child_crc=dup_keys.get("child_crc"),
            mother_cnic=dup_keys.get("mother_cnic"),
            father_cnic=dup_keys.get("father_cnic"),
            current_case_id=case_id,
        ),
    }


@router.patch("/{case_id}/verify")
def verify_case(
    case_id: str,
    req: VerifyRequest,
    user: dict = Depends(require_role("fso", "admin")),
):
    """FSO verifies or flags a case."""
    with get_db() as conn:
        case_row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if not case_row:
            raise HTTPException(404, "Case not found")

        conn.execute(
            """UPDATE cases SET
               status = ?, verified_at = ?, verified_by_fso_id = ?,
               fso_review_notes = ?, flag_reason = ?
               WHERE id = ?""",
            (req.status, datetime.now().isoformat(),
             user.get("fso_id") or user["id"],
             req.fso_review_notes, req.flag_reason,
             case_id),
        )

    return {"success": True, "status": req.status}


@router.patch("/{case_id}/assign")
def assign_case(
    case_id: str,
    req: AssignRequest,
    user: dict = Depends(require_role("admin")),
):
    """Admin manually assigns a case to a region/FSO."""
    with get_db() as conn:
        case_row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if not case_row:
            raise HTTPException(404, "Case not found")

        new_status = "pending_verification" if dict(case_row)["status"] == "unassigned" else dict(case_row)["status"]
        conn.execute(
            """UPDATE cases SET
               region_id = ?, assigned_fso_id = ?,
               routing_confidence = 1.0, routing_reason = ?,
               status = ?
               WHERE id = ?""",
            (req.region_id, req.assigned_fso_id,
             f"Manually assigned by Admin{': ' + req.admin_notes if req.admin_notes else ''}",
             new_status, case_id),
        )

    return {"success": True}


@router.delete("/{case_id}")
def delete_case(
    case_id: str,
    user: dict = Depends(require_role("admin")),
):
    """Admin deletes a case."""
    with get_db() as conn:
        result = conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        if result.rowcount == 0:
            raise HTTPException(404, "Case not found")

    # Clean up uploads
    case_dir = UPLOADS_DIR / case_id
    if case_dir.exists():
        shutil.rmtree(case_dir)

    return {"success": True}


# ─── Child Login (post-verification only) ─────────────────────────────────────

@router.post("/{case_id}/generate-login")
def generate_child_login(
    case_id: str,
    user: dict = Depends(require_role("fso", "admin")),
):
    """Generate a read-only child login for a Verified case.

    The username is always the child's CNIC/B-Form registration number taken
    from the case record — never a chosen username. Credentials are stored on
    the same case record so the child's profile screen can display them.
    """
    with get_db() as conn:
        case_row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if not case_row:
            raise HTTPException(404, "Case not found")
        case = dict(case_row)

        if case["status"] != "verified":
            raise HTTPException(400, "Child logins can only be generated once a case is Verified.")

        # Username = the child's B-Form registration number from the case record
        username_raw = case.get("child_crc")
        child_name = ""
        if case.get("compiled_json"):
            try:
                compiled = json.loads(case["compiled_json"])
                if not username_raw:
                    username_raw = compiled.get("childDetails", {}).get("crcOrRegNumber")
                child_name = compiled.get("childDetails", {}).get("name") or ""
            except (json.JSONDecodeError, TypeError):
                pass

        if not username_raw or not str(username_raw).strip():
            raise HTTPException(400, "No child B-Form registration number is available for this case.")

        username = normalize_cnic(str(username_raw).strip())
        linked_user_id = case.get("child_user_id")
        was_reset = bool(linked_user_id)

        # Guard: an account with this B-Form number must not belong to another case
        existing = conn.execute("SELECT id, role FROM users WHERE cnic = ?", (username,)).fetchone()
        if existing and existing["id"] != linked_user_id:
            other_case = conn.execute(
                "SELECT id FROM cases WHERE family_id = ? AND id != ?",
                (existing["id"], case_id),
            ).fetchone()
            if other_case or existing["role"] != "family":
                raise HTTPException(409, f"An account already exists for B-Form number {username}.")

        # Fresh password each call (also serves as a reset for existing logins)
        password = f"OFSP-{secrets.token_hex(3).upper()}"
        pw_hash, salt = hash_password(password)

        if existing:
            user_id = existing["id"]
            conn.execute(
                """UPDATE users SET password_hash = ?, salt = ?,
                   name = CASE WHEN ? != '' THEN ? ELSE name END
                   WHERE id = ?""",
                (pw_hash, salt, child_name, child_name, user_id),
            )
        else:
            user_id = f"child_{uuid.uuid4().hex[:10]}"
            conn.execute(
                """INSERT INTO users
                   (id, name, cnic, phone, email, password_hash, salt, role, account_type,
                    designation, created_at)
                   VALUES (?, ?, ?, '', '', ?, ?, 'family', 'family',
                           'Orphan Child (Read-only)', ?)""",
                (user_id, child_name or "Orphan Child", username,
                 pw_hash, salt, datetime.now().isoformat()),
            )

        generated_at = datetime.now().isoformat()
        conn.execute(
            """UPDATE cases SET
               family_id = ?, child_user_id = ?, child_username = ?,
               child_password = ?, child_login_generated_at = ?
               WHERE id = ?""",
            (user_id, user_id, username, password, generated_at, case_id),
        )

    return {
        "success": True,
        "case_id": case_id,
        "case_number": case["case_number"],
        "username": username,
        "password": password,
        "generated_at": generated_at,
        "reset": was_reset,
    }


# ─── Donor & Aid Transfer Management (FSO/Admin only — never the child login) ─

@router.patch("/{case_id}/donor-status")
def set_donor_status(
    case_id: str,
    req: DonorStatusRequest,
    user: dict = Depends(require_role("fso", "admin")),
):
    """Toggle donor_arranged on a Verified case."""
    with get_db() as conn:
        case_row = conn.execute("SELECT status FROM cases WHERE id = ?", (case_id,)).fetchone()
        if not case_row:
            raise HTTPException(404, "Case not found")
        if case_row["status"] != "verified":
            raise HTTPException(400, "Donor status can only be managed on Verified cases.")

        conn.execute(
            "UPDATE cases SET donor_arranged = ? WHERE id = ?",
            (1 if req.donor_arranged else 0, case_id),
        )

    return {"success": True, "donor_arranged": req.donor_arranged}


@router.post("/{case_id}/aid-transfers")
def add_aid_transfer(
    case_id: str,
    req: AidTransferRequest,
    user: dict = Depends(require_role("fso", "admin")),
):
    """Append a {date, amount} entry to the case's aid transfer log."""
    if not req.date or not req.date.strip():
        raise HTTPException(400, "Transfer date is required.")
    if req.amount <= 0:
        raise HTTPException(400, "Transfer amount must be greater than zero.")

    with get_db() as conn:
        case_row = conn.execute(
            "SELECT aid_transfer_log FROM cases WHERE id = ?", (case_id,)
        ).fetchone()
        if not case_row:
            raise HTTPException(404, "Case not found")

        try:
            entries = json.loads(case_row["aid_transfer_log"] or "[]")
        except (json.JSONDecodeError, TypeError):
            entries = []

        entries.append({
            "date": req.date.strip(),
            "amount": req.amount,
            "recorded_at": datetime.now().isoformat(),
            "recorded_by": user.get("name", ""),
        })
        conn.execute(
            "UPDATE cases SET aid_transfer_log = ? WHERE id = ?",
            (json.dumps(entries, ensure_ascii=False), case_id),
        )

    return {"success": True, "aid_transfer_log": entries}


@router.delete("/{case_id}/aid-transfers/{entry_index}")
def remove_aid_transfer(
    case_id: str,
    entry_index: int,
    user: dict = Depends(require_role("fso", "admin")),
):
    """Remove an entry from the aid transfer log."""
    with get_db() as conn:
        case_row = conn.execute(
            "SELECT aid_transfer_log FROM cases WHERE id = ?", (case_id,)
        ).fetchone()
        if not case_row:
            raise HTTPException(404, "Case not found")

        try:
            entries = json.loads(case_row["aid_transfer_log"] or "[]")
        except (json.JSONDecodeError, TypeError):
            entries = []

        if entry_index < 0 or entry_index >= len(entries):
            raise HTTPException(404, "Aid transfer entry not found.")

        entries.pop(entry_index)
        conn.execute(
            "UPDATE cases SET aid_transfer_log = ? WHERE id = ?",
            (json.dumps(entries, ensure_ascii=False), case_id),
        )

    return {"success": True, "aid_transfer_log": entries}