"""
FastAPI backend for OFSP document intake tool.
Wraps the existing pipeline.py extraction logic with HTTP endpoints.
"""

import json
import re
import shutil
import uuid
import unicodedata
from difflib import SequenceMatcher
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from pipeline import extract_document, schema, conn, cursor

app = FastAPI(title="OFSP Document Intake API")

# CORS — allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)

# Serve uploaded images
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Serve built frontend in production
FRONTEND_DIST = Path("frontend/dist")
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")


# ─── Eastern Arabic numeral normalization ────────────────────────────────────

EASTERN_ARABIC = {chr(0x0660 + i): str(i) for i in range(10)}  # ۰-۹ → 0-9


def normalize_numerals(text: str | None) -> str | None:
    """Convert Eastern Arabic numerals (۰-۹) to Western digits (0-9)."""
    if text is None:
        return None
    return "".join(EASTERN_ARABIC.get(ch, ch) for ch in text)


def normalize_for_comparison(text: str | None) -> str | None:
    """Normalize a string for cross-check comparison."""
    if text is None:
        return None
    text = normalize_numerals(text)
    return text.strip().lower()


# ─── Fuzzy matching ──────────────────────────────────────────────────────────

SIMILAR_THRESHOLD = 0.75  # Above this = SIMILAR, below = MISMATCH

# Unicode range for Urdu/Arabic script
_ARABIC_RANGE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
_ROMAN_RANGE = re.compile(r"[A-Za-z]")


def _is_urdu_script(text: str) -> bool:
    """Return True if the string contains Urdu/Arabic characters."""
    return bool(_ARABIC_RANGE.search(text))


def _is_roman_script(text: str) -> bool:
    """Return True if the string contains Latin/Roman characters."""
    return bool(_ROMAN_RANGE.search(text))


def compare_values(val1, val2) -> dict:
    """
    Compare two values and return status: MATCH, SIMILAR, MISMATCH, or NEEDS_REVIEW.
    """
    if val1 is None or val2 is None:
        return {"status": "NEEDS_REVIEW", "detail": "missing value", "similarity": None}

    n1 = normalize_for_comparison(str(val1))
    n2 = normalize_for_comparison(str(val2))

    if n1 == n2:
        return {"status": "MATCH", "detail": None, "similarity": 1.0}

    ratio = SequenceMatcher(None, n1, n2).ratio()

    if ratio >= SIMILAR_THRESHOLD:
        return {
            "status": "SIMILAR",
            "detail": f"'{val1}' vs '{val2}'",
            "similarity": round(ratio, 3),
        }
    else:
        return {
            "status": "MISMATCH",
            "detail": f"'{val1}' vs '{val2}'",
            "similarity": round(ratio, 3),
        }


def compare_names(val1, val2) -> dict:
    """
    Compare two name values. If one is Urdu-script and the other is Roman-script,
    return DIFFERENT_SCRIPT instead of a misleading MISMATCH.
    Falls back to compare_values() when both are in the same script.
    """
    if val1 is None or val2 is None:
        return {"status": "NEEDS_REVIEW", "detail": "missing value", "similarity": None}

    s1, s2 = str(val1).strip(), str(val2).strip()
    v1_urdu = _is_urdu_script(s1)
    v1_roman = _is_roman_script(s1)
    v2_urdu = _is_urdu_script(s2)
    v2_roman = _is_roman_script(s2)

    # Detect cross-script: one is Urdu-only, the other is Roman-only
    cross_script = (
        (v1_urdu and not v1_roman and v2_roman and not v2_urdu)
        or (v1_roman and not v1_urdu and v2_urdu and not v2_roman)
    )

    if cross_script:
        return {
            "status": "DIFFERENT_SCRIPT",
            "detail": f"'{val1}' vs '{val2}' — names are in different scripts, please verify manually",
            "similarity": None,
        }

    # Same script — use normal comparison
    return compare_values(val1, val2)


# ─── Models ──────────────────────────────────────────────────────────────────

DOCUMENT_TYPES = [
    "child_picture",
    "result_card",
    "b_form",
    "death_certificate",
    "mother_cnic",
    "father_cnic",
]


class ExtractRequest(BaseModel):
    document_type: str
    target_child_serial_number: Optional[int] = None


class CrossCheckRequest(BaseModel):
    """Expects a dict of document_type → extracted_json for all uploaded docs."""
    documents: dict  # { "b_form": {...}, "father_cnic": {...}, ... }
    target_child_serial_number: Optional[int] = None


class FieldEdit(BaseModel):
    document_type: str
    field_path: str  # e.g. "father_name" or "children.2.child_name"
    new_value: str | None


class SubmitRequest(BaseModel):
    documents: dict
    cross_checks: list
    acknowledgment: str  # Required if any MISMATCH/SIMILAR exists
    status: str  # "approved" or "submitted_with_flags"


# ─── Endpoints ───────────────────────────────────────────────────────────────


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    """Upload an image and return its ID/path."""
    ext = Path(file.filename).suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".heic"):
        raise HTTPException(400, f"Unsupported file type: {ext}")

    image_id = str(uuid.uuid4())
    save_path = UPLOADS_DIR / f"{image_id}{ext}"
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"image_id": image_id, "path": f"/uploads/{image_id}{ext}", "filename": file.filename}


@app.post("/api/extract")
async def run_extraction(
    image_id: str = Form(...),
    document_type: str = Form(...),
    target_child_serial_number: Optional[int] = Form(None),
):
    """Run extraction on a previously uploaded image."""
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(400, f"Invalid document_type. Must be one of: {DOCUMENT_TYPES}")

    if document_type == "address":
        raise HTTPException(400, "Address is a text field, not an image extraction")

    # Find the uploaded file
    matches = list(UPLOADS_DIR.glob(f"{image_id}.*"))
    if not matches:
        raise HTTPException(404, "Image not found")

    image_path = matches[0]

    try:
        result = extract_document(
            image_path,
            document_type,
            target_child_serial_number=target_child_serial_number,
        )
        return {
            "document_type": document_type,
            "extracted": result,
            "image_path": f"/uploads/{image_path.name}",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(500, f"Extraction failed: {str(e)}")


@app.post("/api/save-address")
async def save_address(full_address: str = Form(...)):
    """Save the manually-typed address (no image extraction needed)."""
    result = {"full_address": full_address}

    timestamp = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO extractions (document_type, extracted_json, timestamp) VALUES (?, ?, ?)",
        ("address", json.dumps(result, ensure_ascii=False), timestamp),
    )
    conn.commit()

    return {"document_type": "address", "extracted": result, "timestamp": timestamp}


@app.post("/api/save-mother-education")
async def save_mother_education(education_level: str = Form(...)):
    """Save the manually-typed mother's education level (no image extraction needed)."""
    print(f"[save-mother-education] Received education_level={education_level!r}")
    result = {"education_level": education_level}

    timestamp = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO extractions (document_type, extracted_json, timestamp) VALUES (?, ?, ?)",
        ("mother_education", json.dumps(result, ensure_ascii=False), timestamp),
    )
    conn.commit()
    print(f"[save-mother-education] Saved to DB, returning: {result}")

    return {"document_type": "mother_education", "extracted": result, "timestamp": timestamp}


@app.post("/api/cross-check")
async def run_cross_check(req: CrossCheckRequest):
    """
    Run all cross-document validations and return results.
    Returns 5 states: MATCH, SIMILAR, MISMATCH, NEEDS_REVIEW, DIFFERENT_SCRIPT.
    DIFFERENT_SCRIPT is used when comparing names across Urdu-script (B-form)
    and Roman-script (CNIC/death cert/result card) — a manual-review flag, not a hard failure.
    """
    docs = req.documents
    checks = []

    def get_field(doc_type, field_path):
        """Get a nested field value from a document extraction."""
        doc = docs.get(doc_type)
        if doc is None:
            return None
        parts = field_path.split(".")
        val = doc
        for part in parts:
            if isinstance(val, list):
                try:
                    val = val[int(part)]
                except (IndexError, ValueError):
                    return None
            elif isinstance(val, dict):
                val = val.get(part)
            else:
                return None
        return val

    def get_target_child_name():
        """Find the target child's name from b_form."""
        b_form = docs.get("b_form")
        if not b_form:
            return None
        children = b_form.get("children", [])
        for child in children:
            if child.get("is_target_child") is True:
                return child.get("child_name")
        # Fallback: use target_child_serial_number
        if req.target_child_serial_number is not None:
            for child in children:
                if child.get("serial_number") == req.target_child_serial_number:
                    return child.get("child_name")
        return None

    # 1. Father CNIC number
    checks.append({
        "label": "Father CNIC number",
        "source": {"doc": "b_form", "field": "father_cnic_number"},
        "target": {"doc": "father_cnic", "field": "cnic_number"},
        **compare_values(
            normalize_numerals(get_field("b_form", "father_cnic_number")),
            normalize_numerals(get_field("father_cnic", "cnic_number")),
        ),
    })

    # 2. Mother CNIC number
    checks.append({
        "label": "Mother CNIC number",
        "source": {"doc": "b_form", "field": "mother_cnic_number"},
        "target": {"doc": "mother_cnic", "field": "cnic_number"},
        **compare_values(
            normalize_numerals(get_field("b_form", "mother_cnic_number")),
            normalize_numerals(get_field("mother_cnic", "cnic_number")),
        ),
    })

    # 3. Father name (B-form vs CNIC) — may be Urdu vs Roman script
    checks.append({
        "label": "Father name (B-form vs CNIC)",
        "source": {"doc": "b_form", "field": "father_name"},
        "target": {"doc": "father_cnic", "field": "name"},
        **compare_names(
            get_field("b_form", "father_name"),
            get_field("father_cnic", "name"),
        ),
    })

    # 4. Father name (B-form vs Death certificate) — may be Urdu vs Roman script
    checks.append({
        "label": "Father name (B-form vs Death cert)",
        "source": {"doc": "b_form", "field": "father_name"},
        "target": {"doc": "death_certificate", "field": "deceased_name"},
        **compare_names(
            get_field("b_form", "father_name"),
            get_field("death_certificate", "deceased_name"),
        ),
    })

    # 5. Target child name (B-form vs Result card) — may be Urdu vs Roman script
    target_name = get_target_child_name()
    checks.append({
        "label": "Target child name (B-form vs Result card)",
        "source": {"doc": "b_form", "field": "children[target].child_name"},
        "target": {"doc": "result_card", "field": "child_name"},
        **compare_names(
            target_name,
            get_field("result_card", "child_name"),
        ),
    })

    return {"checks": checks}


@app.get("/api/extractions")
def list_extractions():
    """List all extractions from the database."""
    cursor.execute("SELECT id, document_type, extracted_json, timestamp FROM extractions ORDER BY id DESC")
    rows = cursor.fetchall()
    return [
        {
            "id": row[0],
            "document_type": row[1],
            "extracted_json": json.loads(row[2]),
            "timestamp": row[3],
        }
        for row in rows
    ]


@app.post("/api/submit")
async def submit_case(req: SubmitRequest):
    """Submit a case. Requires acknowledgment if any checks are flagged."""
    has_flags = any(
        c.get("status") in ("MISMATCH", "SIMILAR", "NEEDS_REVIEW", "DIFFERENT_SCRIPT")
        for c in req.cross_checks
    )

    if has_flags and not req.acknowledgment.strip():
        raise HTTPException(
            400,
            "Acknowledgment is required when there are unresolved flags (MISMATCH/SIMILAR/NEEDS_REVIEW/DIFFERENT_SCRIPT).",
        )

    case_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().isoformat()

    case_record = {
        "case_id": case_id,
        "documents": req.documents,
        "cross_checks": req.cross_checks,
        "acknowledgment": req.acknowledgment,
        "status": req.status,
        "submitted_at": timestamp,
    }

    # Save to DB
    cursor.execute(
        "INSERT INTO extractions (document_type, extracted_json, timestamp) VALUES (?, ?, ?)",
        ("_case_submission", json.dumps(case_record, ensure_ascii=False), timestamp),
    )
    conn.commit()

    return {"case_id": case_id, "status": "submitted", "submitted_at": timestamp}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# ─── Serve frontend in production ────────────────────────────────────────────

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """Serve the React SPA for any non-API route (production only)."""
    if not FRONTEND_DIST.exists():
        raise HTTPException(404, "Frontend not built or running in dev mode")

    # Try to serve the exact file first
    file_path = FRONTEND_DIST / full_path
    if file_path.is_file():
        return FileResponse(file_path)

    # Fall back to index.html for client-side routing
    return FileResponse(FRONTEND_DIST / "index.html")
