"""
Field validation for OFSP document extraction.

Applied to BOTH extraction output (server-side post-processing) and manual edits
(the /api/validate-field endpoint). Invalid extraction values are kept (the FSO
needs to see what was misread) but confidence is forced to 0. Invalid manual
edits are rejected before being saved.
"""

import re
from datetime import datetime


# ─── Compiled patterns ───────────────────────────────────────────────────────

CNIC_RE = re.compile(r"^\d{5}-\d{7}-\d{1}$")
NAME_RE = re.compile(r"^[A-Za-z\u0600-\u06FF\s.\-]+$")  # English or Urdu letters + spaces/dots/dashes
REG_NUMBER_RE = re.compile(r"^[\d\-]+$")  # digits and dashes


# ─── Fixed enums ─────────────────────────────────────────────────────────────

EDUCATION_LEVELS = {
    "none", "primary", "middle", "matric",
    "intermediate", "graduate", "post-graduate",
}

QUALITY_CHECK_VALUES = {"clear", "blurry", "face_not_visible"}

# Heuristic patterns that suggest a name is garbled / hallucinated
GARBLE_RE = re.compile(r"\d|\s{3,}|(.)\1{2,}")


# ─── Field → category mapping ───────────────────────────────────────────────
# Keys are the field_path used in extraction JSON (without document_type prefix).
# "free_text" means no validation (always passes).

FIELD_CATEGORIES: dict[str, str] = {
    # CNIC fields
    "father_cnic_number": "cnic",
    "mother_cnic_number": "cnic",
    "applicant_cnic_number": "cnic",
    "cnic_number": "cnic",

    # Name fields (bilingual)
    "father_name": "name",
    "mother_name": "name",
    "applicant_name": "name",
    "name": "name",
    "father_or_husband_name": "name",
    "deceased_name": "name",
    "child_name": "name",

    # Registration / CRC numbers (digits and dashes only)
    "crc_number": "reg_number",
    "child_registration_number": "reg_number",
    "registration_number": "reg_number",

    # Dates (DD-MM-YYYY, not in future)
    "date_of_birth": "date",
    "date_of_death": "date",

    # Fixed enums
    "education_level": "education_enum",
    "quality_check": "quality_enum",

    # Result grade (special)
    "result_percentage_or_grade": "grade",

    # Year (4-digit or freeform)
    "year": "year",

    # Free text — no validation
    "full_address": "free_text",
    "address": "free_text",
    "remarks": "free_text",
    "school_name": "free_text",
    "class_grade": "free_text",
    "issuing_union_council": "free_text",
    "gender_relation": "free_text",
    "serial_number": "free_text",
}


# ─── Validators ──────────────────────────────────────────────────────────────

def validate_field(field_name: str, value: str | None) -> tuple[bool, str | None]:
    """
    Validate a single field value.

    Returns:
        (is_valid, error_message)
        error_message is None when valid.
    """
    if value is None or str(value).strip() == "":
        # Null/empty is acceptable — the FSO will see it as missing
        return True, None

    value = str(value).strip()
    category = FIELD_CATEGORIES.get(field_name, "free_text")

    if category == "free_text":
        return True, None

    if category == "cnic":
        if not CNIC_RE.match(value):
            return False, f"CNIC must be in format XXXXX-XXXXXXX-X (got '{value}')"
        return True, None

    if category == "name":
        if not NAME_RE.match(value):
            return False, f"Name may only contain English or Urdu letters and spaces (got '{value}')"
        return True, None

    if category == "reg_number":
        if not REG_NUMBER_RE.match(value):
            return False, f"Registration number must contain only digits and dashes (got '{value}')"
        return True, None

    if category == "date":
        return _validate_date(value)

    if category == "education_enum":
        if value.lower() not in EDUCATION_LEVELS:
            return False, f"Education level must be one of: {', '.join(sorted(EDUCATION_LEVELS))} (got '{value}')"
        return True, None

    if category == "quality_enum":
        if value.lower() not in QUALITY_CHECK_VALUES:
            return False, f"Quality check must be one of: {', '.join(sorted(QUALITY_CHECK_VALUES))} (got '{value}')"
        return True, None

    if category == "grade":
        return _validate_grade(value)

    if category == "year":
        # Accept 4-digit year or freeform like "2024-2025"
        if not re.match(r"^\d{4}(-\d{4})?$", value):
            return False, f"Year must be a 4-digit number (got '{value}')"
        return True, None

    return True, None


def _validate_date(value: str) -> tuple[bool, str | None]:
    """Validate DD-MM-YYYY format, reject future dates."""
    if not re.match(r"^\d{2}-\d{2}-\d{4}$", value):
        return False, f"Date must be in DD-MM-YYYY format (got '{value}')"
    try:
        dt = datetime.strptime(value, "%d-%m-%Y")
        if dt.date() > datetime.now().date():
            return False, f"Date cannot be in the future (got '{value}')"
    except ValueError:
        return False, f"Invalid date '{value}' (e.g. day/month out of range)"
    return True, None


def _validate_grade(value: str) -> tuple[bool, str | None]:
    """Accept a percentage 0-100 or a letter grade."""
    # Try numeric
    try:
        pct = float(value.replace("%", ""))
        if 0 <= pct <= 100:
            return True, None
        return False, f"Percentage must be between 0 and 100 (got '{value}')"
    except ValueError:
        pass
    # Try letter grade (A+, A, B, C, D, F, etc.)
    if re.match(r"^[A-Fa-f][+-]?$", value.strip()):
        return True, None
    return False, f"Grade must be a number 0-100 or a letter grade like A+, B, C (got '{value}')"


def _is_name_field(field_name: str) -> bool:
    """Return True if the field is a name field per FIELD_CATEGORIES."""
    return FIELD_CATEGORIES.get(field_name) == "name"


def _name_looks_garbled(value: str | None) -> bool:
    """Heuristic check for names that are likely model hallucinations."""
    if value is None:
        return False
    s = str(value).strip()
    if not s or len(s) < 2 or len(s) > 80:
        return True
    if GARBLE_RE.search(s):
        return True
    return False


def _set_field_confidence(data: dict, field_path: str, score: float) -> None:
    """Set the confidence score for a top-level or nested child field."""
    parts = field_path.split(".")
    confidence = data.get("confidence")
    if not isinstance(confidence, dict):
        return

    if len(parts) == 1:
        confidence[parts[0]] = score
        return

    if len(parts) == 3 and parts[0] == "children":
        try:
            idx = int(parts[1])
        except ValueError:
            return
        child_confidences = confidence.get("children")
        if isinstance(child_confidences, list) and 0 <= idx < len(child_confidences):
            child_confidences[idx][parts[2]] = score


# ─── Extraction post-processing ─────────────────────────────────────────────

def validate_extraction(document_type: str, data: dict) -> dict:
    """
    Validate all fields in an extraction result.
    For any field that fails validation:
      - Force its confidence to 0
      - Keep the raw value (don't drop it — FSO needs to see what was misread)
    Returns the data dict with a "_validation_errors" list added at top level.
    """
    errors: list[dict] = []

    def flag(field_path: str, raw_value, error_msg: str) -> None:
        errors.append({"field": field_path, "error": error_msg, "raw_value": raw_value})
        _set_field_confidence(data, field_path, 0)

    # Validate top-level fields
    for field_name, value in list(data.items()):
        if field_name in ("confidence", "children") or field_name.startswith("_"):
            continue
        is_valid, error_msg = validate_field(field_name, value)
        if not is_valid:
            flag(field_name, value, error_msg)
        elif _is_name_field(field_name) and _name_looks_garbled(value):
            flag(field_name, value, f"Name appears garbled/hallucinated: '{value}'")

    # Validate children array (b_form)
    child_names: list[tuple[int, str]] = []
    if "children" in data and isinstance(data["children"], list):
        for i, child in enumerate(data["children"]):
            if not isinstance(child, dict):
                continue
            child_name = child.get("child_name")
            if child_name is not None:
                child_names.append((i, str(child_name).strip()))
            for field_name, value in list(child.items()):
                if field_name == "is_target_child":
                    continue
                field_path = f"children.{i}.{field_name}"
                is_valid, error_msg = validate_field(field_name, value)
                if not is_valid:
                    flag(field_path, value, error_msg)
                elif _is_name_field(field_name) and _name_looks_garbled(value):
                    flag(field_path, value, f"Name appears garbled/hallucinated: '{value}'")

        # Duplicate child names across rows are a strong hallucination signal
        if len(child_names) > 1:
            normalized = [name.lower() for _, name in child_names]
            if len(set(normalized)) == 1:
                for idx, raw_name in child_names:
                    flag(f"children.{idx}.child_name", raw_name,
                         "Duplicate child names across rows; likely hallucinated")

    # Surface post-processing column-swap flags as validation errors so the FSO
    # sees them in the same list as field-level failures.
    for corr in data.get("_column_corrections", []):
        if corr.startswith("FLAG child_registration_number"):
            for i, child in enumerate(data.get("children", [])):
                if isinstance(child, dict):
                    flag(
                        f"children.{i}.child_registration_number",
                        child.get("child_registration_number"),
                        "Child registration numbers are identical across rows; likely a parent CNIC was copied here",
                    )
        elif "FLAG father_cnic_number" in corr:
            flag("father_cnic_number", data.get("father_cnic_number"), corr)
        elif "FLAG mother_cnic_number" in corr:
            flag("mother_cnic_number", data.get("mother_cnic_number"), corr)

    data["_validation_errors"] = errors
    return data


# ─── B-form post-processing (column-swap correction) ────────────────────────

def postprocess_bform(result: dict) -> dict:
    """
    Detect and correct B-form column swaps between parent CNICs and child
    registration numbers.

    Reads father_cnic_number and mother_cnic_number from the TOP LEVEL of the
    parsed JSON (as the schema requires) and uses child_registration_number
    values from the children[] rows.

    Detection uses two independent signals:
      1. Value collision: a top-level parent CNIC equals a child registration number.
      2. Format-based: a top-level parent value does not match the CNIC pattern.

    When the real parent CNIC can be recovered from per-row values emitted by
    the model, the swap is corrected. Otherwise the field is flagged so
    validation forces confidence to 0 and an FSO reviews it.
    """
    children = result.get("children", [])
    if not isinstance(children, list):
        children = []

    corrections: list[str] = []

    def _cnic(value) -> bool:
        return bool(CNIC_RE.match(str(value or "")))

    def _reg(value) -> bool:
        return bool(REG_NUMBER_RE.match(str(value or "")))

    def _constant_valid_cnic(values: list[str]) -> str | None:
        """Return a constant valid CNIC across row values, if one exists."""
        nonempty = [v for v in values if v]
        if not nonempty:
            return None
        if len(set(nonempty)) == 1 and _cnic(nonempty[0]):
            return nonempty[0]
        return None

    child_regs = [
        str(child.get("child_registration_number") or "")
        for child in children
        if isinstance(child, dict)
    ]
    child_reg_set = {cr for cr in child_regs if cr}
    nonempty_regs = [cr for cr in child_regs if cr]

    # The model sometimes emits per-row father/mother CNICs inside children;
    # collect them as recovery candidates but do not treat them as canonical.
    per_row_parents = {
        "father_cnic_number": [
            str(child.get("father_cnic_number") or "")
            for child in children
            if isinstance(child, dict)
        ],
        "mother_cnic_number": [
            str(child.get("mother_cnic_number") or "")
            for child in children
            if isinstance(child, dict)
        ],
    }

    for parent_field, row_values in per_row_parents.items():
        top_val = str(result.get(parent_field) or "")
        if not top_val:
            continue

        # ── Signal 1: collision with a child registration number ──
        if top_val in child_reg_set:
            real_parent = _constant_valid_cnic(row_values)
            if not real_parent:
                for v in row_values:
                    if v and v != top_val and _cnic(v):
                        real_parent = v
                        break

            if real_parent:
                result[parent_field] = real_parent
                relocated = False
                for child in children:
                    if (
                        isinstance(child, dict)
                        and str(child.get("child_registration_number") or "") == real_parent
                    ):
                        child["child_registration_number"] = top_val
                        relocated = True
                corrections.append(
                    f"Swapped {parent_field} ↔ child_registration_number "
                    f"(restored {parent_field}={real_parent}; misplaced child reg# "
                    f"{'relocated' if relocated else 'not relocated'})"
                )
            else:
                corrections.append(
                    f"FLAG {parent_field}: top-level value '{top_val}' matches a child "
                    "registration number; real parent CNIC could not be recovered from this extraction"
                )
            continue

        # ── Signal 2: format-based ──
        if not _cnic(top_val):
            real_parent = _constant_valid_cnic(row_values)
            if not real_parent:
                for v in row_values:
                    if v and v != top_val and _cnic(v):
                        real_parent = v
                        break

            if real_parent:
                result[parent_field] = real_parent
                corrections.append(
                    f"Corrected {parent_field} from '{top_val}' to '{real_parent}' "
                    "(format-based recovery)"
                )
            else:
                corrections.append(
                    f"FLAG {parent_field}: value '{top_val}' is not a valid CNIC and "
                    "no real parent CNIC was found"
                )
            continue

    # ── Signal 3: structural invariant ──
    # Child registration numbers should be different per row. If every row has
    # the same valid-CNIC-looking value, a parent CNIC was likely copied into
    # all child_registration_number slots.
    if len(nonempty_regs) >= 2 and len(set(nonempty_regs)) == 1 and _cnic(nonempty_regs[0]):
        constant = nonempty_regs[0]
        corrections.append(
            f"FLAG child_registration_number: every row has the same value '{constant}'; "
            "a parent CNIC may have been copied into all child rows"
        )

        # Try to recover the misplaced parent CNIC and assign it back to the
        # correct top-level parent slot.
        top_father = str(result.get("father_cnic_number") or "")
        top_mother = str(result.get("mother_cnic_number") or "")
        applicant = str(result.get("applicant_cnic_number") or "")

        def _parent_for_constant(constant_val: str) -> str | None:
            # Applicant is usually the father, so it can verify the father slot
            if _cnic(applicant):
                if applicant == top_father:
                    return "mother_cnic_number"
                if applicant == constant_val:
                    return "father_cnic_number"
            # If a top-level parent already equals the constant, the OTHER parent is swapped
            if top_father == constant_val and top_mother != constant_val:
                return "mother_cnic_number"
            if top_mother == constant_val and top_father != constant_val:
                return "father_cnic_number"
            # Fallback: assign constant to the parent whose top-level value is
            # a valid CNIC but differs from the constant (the likely swapped slot)
            if _cnic(top_father) and top_father != constant_val:
                return "mother_cnic_number"
            if _cnic(top_mother) and top_mother != constant_val:
                return "father_cnic_number"
            return None

        target_parent = _parent_for_constant(constant)
        if target_parent:
            old_parent_val = str(result.get(target_parent) or "")
            result[target_parent] = constant
            corrections.append(
                f"Recovered {target_parent}={constant} from constant child_registration_number values; "
                f"previous top-level value '{old_parent_val}' is likely a misplaced child reg#"
            )
            # Preserve the displaced child reg# in the first row if it looks valid
            if old_parent_val and _cnic(old_parent_val) and children:
                first_child = children[0]
                if isinstance(first_child, dict):
                    first_child["child_registration_number"] = old_parent_val
                    corrections.append(
                        f"Placed displaced child reg# '{old_parent_val}' in children[0]"
                    )

    # Update confidence to reflect automated corrections / required review
    conf = result.get("confidence")
    if isinstance(conf, dict):
        for correction in corrections:
            if correction.startswith(("Swapped", "Corrected")):
                # A clean swap: both the parent slot and the child reg# slot were recovered
                for parent_field in ("father_cnic_number", "mother_cnic_number"):
                    if parent_field in correction:
                        conf[parent_field] = 0.5
                child_conf = conf.get("children")
                if isinstance(child_conf, list):
                    for cc in child_conf:
                        if isinstance(cc, dict):
                            cc["child_registration_number"] = 0.5
            elif correction.startswith("Recovered"):
                # We recovered the parent CNIC from the child rows, but the child
                # registration numbers remain suspect; only raise parent confidence.
                for parent_field in ("father_cnic_number", "mother_cnic_number"):
                    if parent_field in correction:
                        conf[parent_field] = 0.5
            elif correction.startswith("FLAG"):
                # Force confidence to 0 for flagged fields; validate_extraction will
                # also do this, but doing it here makes the post-processed output explicit.
                if "father_cnic_number" in correction:
                    conf["father_cnic_number"] = 0
                if "mother_cnic_number" in correction:
                    conf["mother_cnic_number"] = 0
                if "child_registration_number" in correction:
                    child_conf = conf.get("children")
                    if isinstance(child_conf, list):
                        for cc in child_conf:
                            if isinstance(cc, dict):
                                cc["child_registration_number"] = 0

    result["_column_corrections"] = corrections
    return result
