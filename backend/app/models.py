"""
Pydantic models for request/response validation.
"""

from typing import Optional
from pydantic import BaseModel


# ─── Auth Models ───────────────────────────────────────────────────────────────

class SigninRequest(BaseModel):
    cnic: str
    password: str
    expected_account_type: Optional[str] = None


class AuthResponse(BaseModel):
    success: bool
    message: str
    user: dict
    token: Optional[str] = None


# ─── Case Models ───────────────────────────────────────────────────────────────

class CaseCreateRequest(BaseModel):
    submission_source: str = "fso_manual"


class DocumentUploadResponse(BaseModel):
    doc_type: str
    file_path: str
    status: str


class ExtractionRequest(BaseModel):
    doc_type: str
    target_child_serial_number: Optional[int] = None
    # Preferred way to identify the target orphan in a B-form: the child's
    # own registration number, read by the FSO off the physical document.
    # Matched deterministically in Python (header_mapping.match_target_child)
    # rather than trusted to a model guess. target_child_serial_number above
    # is legacy/deprecated.
    target_child_registration_number: Optional[str] = None
    # FSO-entered target child's name — used only for a post-extraction
    # cross-check against the B-form's own child_name and the result
    # card's child_name, to flag a conflict before submission. Never used
    # to select or override which child row is the target.
    target_child_name: Optional[str] = None
    # "old" or "new" — required (meaningfully) only for mother_cnic/father_cnic.
    # "old" routes to OCR.space + Qwen-plus text structuring; "new" or None
    # keeps the existing Qwen-VL vision path. Ignored for all other doc types.
    cnic_format: Optional[str] = None


class FieldEditRequest(BaseModel):
    doc_type: str
    field_path: str
    new_value: Optional[str] = None


class ValidateFieldRequest(BaseModel):
    field_name: str
    value: Optional[str] = None


class SubmitRequest(BaseModel):
    acknowledgment: str = ""
    status: str = "approved"


class VerifyRequest(BaseModel):
    status: str  # 'verified' | 'flagged' | 'rejected'
    fso_review_notes: Optional[str] = ""
    flag_reason: Optional[str] = ""


class AssignRequest(BaseModel):
    region_id: str
    region_name: str
    assigned_fso_id: str
    assigned_fso_name: str
    admin_notes: Optional[str] = ""


class DonorStatusRequest(BaseModel):
    donor_arranged: bool


class AidTransferRequest(BaseModel):
    date: str  # YYYY-MM-DD
    amount: float


# ─── FSO/Region Management ────────────────────────────────────────────────────

class FSOCreateRequest(BaseModel):
    name: str
    cnic: str
    phone: Optional[str] = ""
    email: Optional[str] = ""
    password: Optional[str] = "password123"
    assigned_region_ids: list[str] = []
    badge: Optional[str] = ""


class FSOUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    assigned_region_ids: Optional[list[str]] = None
    password: Optional[str] = None
    badge: Optional[str] = None


class RegionCreateRequest(BaseModel):
    name: str
    urdu_name: Optional[str] = ""
    keywords: list[str] = []
    assigned_fso_id: Optional[str] = None
    active: bool = True


# ─── Chat Models ───────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    history: Optional[list[dict]] = []
    current_role: Optional[str] = "fso"
    current_task: Optional[str] = "general_intake"
    task_label: Optional[str] = ""
    active_step: Optional[str] = ""
    case_context: Optional[dict] = None


# ─── Routing Models ────────────────────────────────────────────────────────────

class RouteRequest(BaseModel):
    address: str