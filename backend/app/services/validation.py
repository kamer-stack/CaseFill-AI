"""
Field validation for OFSP document extraction.

Applied to BOTH extraction output (server-side post-processing) and manual edits
(the /api/cases/validate-field endpoint). Invalid extraction values are kept (the
FSO needs to see what was misread) but confidence is forced to 0. Invalid manual
edits are rejected before being saved.

Ported from the HACKATHON prototype's validation.py.
"""

import re
from datetime import datetime
from difflib import SequenceMatcher

from .transliterate import transliterate_urdu_to_roman


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

# Urdu-script detection (Arabic block, incl. Urdu-specific glyphs)
URDU_SCRIPT_RE = re.compile(r"[\u0600-\u06FF]")


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


def _contains_urdu_script(value) -> bool:
    """True if the value (or any element, when a list) contains Urdu-script text."""
    if isinstance(value, list):
        return any(_contains_urdu_script(v) for v in value)
    if value is None:
        return False
    return bool(URDU_SCRIPT_RE.search(str(value)))


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

    # Deterministic Urdu-script rule (runs regardless of the model's
    # self-reported confidence): any NAME-category field (father_name,
    # mother_name, applicant_name, child_name, …) or any _raw_*_urdu echo
    # whose value contains Urdu-script text is forced to confidence 0 and
    # flagged requires_human_review.
    def flag_urdu(field_path: str, raw_value) -> None:
        errors.append({
            "field": field_path,
            "error": (
                "Urdu-script text in name field; requires_human_review "
                "(model self-reported confidence overridden to 0)"
            ),
            "raw_value": raw_value,
            "flag": "requires_human_review",
        })
        _set_field_confidence(data, field_path, 0)

    raw_name_echoes = ("_raw_father_name_urdu", "_raw_mother_name_urdu", "_raw_child_names_urdu")
    for field_name, value in list(data.items()):
        if field_name in raw_name_echoes:
            if _contains_urdu_script(value):
                flag_urdu(field_name, value)
        elif not field_name.startswith("_") and _is_name_field(field_name):
            if _contains_urdu_script(value):
                flag_urdu(field_name, value)
    if isinstance(data.get("children"), list):
        for i, child in enumerate(data["children"]):
            if not isinstance(child, dict):
                continue
            for field_name, value in child.items():
                if _is_name_field(field_name) and _contains_urdu_script(value):
                    flag_urdu(f"children.{i}.{field_name}", value)

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
        elif "FLAG applicant_cnic_number/father_cnic_number" in corr:
            # Compound flag from the applicant/father consistency-check mismatch:
            # surface on BOTH fields because the pipeline cannot determine which
            # (if either) is correct without source-document verification.
            flag("applicant_cnic_number", data.get("applicant_cnic_number"), corr)
            flag("father_cnic_number", data.get("father_cnic_number"), corr)
        elif "FLAG father_cnic_number" in corr:
            flag("father_cnic_number", data.get("father_cnic_number"), corr)
        elif "FLAG mother_cnic_number" in corr:
            flag("mother_cnic_number", data.get("mother_cnic_number"), corr)
        elif "FLAG mother_name" in corr:
            flag("mother_name", data.get("mother_name"), corr)
        elif "FLAG father_name" in corr:
            flag("father_name", data.get("father_name"), corr)
        elif "FLAG child_name" in corr:
            # Rule F: duplicate sibling names — find the implicated rows
            # from the correction string and zero each one.
            m = re.search(r"rows \[([0-9, ]+)\]", corr)
            if m:
                for idx_str in m.group(1).split(","):
                    try:
                        idx = int(idx_str.strip())
                    except ValueError:
                        continue
                    child_row = (data.get("children") or [None])[idx:idx + 1]
                    row_val = child_row[0].get("child_name") if child_row and isinstance(child_row[0], dict) else None
                    flag(f"children.{idx}.child_name", row_val, corr)
        elif corr.startswith("FLAG children.") and "child_registration_number" in corr:
            m = re.search(r"FLAG children\.(\d+)\.child_registration_number", corr)
            if m:
                idx = int(m.group(1))
                child_row = (data.get("children") or [None])[idx:idx + 1]
                row_val = child_row[0].get("child_registration_number") if child_row and isinstance(child_row[0], dict) else None
                flag(f"children.{idx}.child_registration_number", row_val, corr)

    # Surface CNIC-document flags (item 5 routing mix-up, etc.)
    for corr in data.get("_cnic_corrections", []):
        if "cnic_number" in corr:
            flag("cnic_number", data.get("cnic_number"), corr)
        elif f"{document_type}.name" in corr or ".name" in corr:
            flag("name", data.get("name"), corr)
        else:
            # Generic fallback — attach as a document-level error
            errors.append({"field": "_document", "error": corr, "raw_value": None})

    data["_validation_errors"] = errors
    return data


# Well-formatted CNIC confidence floor after all cross-checks pass. Chosen
# to counteract the model's tendency to emit hedged 0.5 scores for legible
# values on worn cards; 0.8 still leaves headroom for genuinely uncertain
# reads while lifting obvious false-negatives out of the "needs review"
# band. Used by both postprocess_bform (top-level CNIC fields) and
# postprocess_cnic (cnic_number on standalone CNIC documents).
_CNIC_CONFIDENCE_FLOOR = 0.8


# ─── B-form post-processing (column-swap correction) ────────────────────────

def postprocess_bform(result: dict, raw_model_text: str = "") -> dict:
    """
    Detect and flag B-form column swaps between parent CNICs and child
    registration numbers, then apply verbatim-source and cross-field
    hallucination checks added for test_bform_v2.png-class regressions.

    Under the null-over-guess principle, the postprocessor NEVER invents
    a value that is not already present in the model's extraction. Swap
    detection uses two structural signals (value collision and format
    mismatch) and performs a deterministic swap ONLY when every child row
    carries the same valid CNIC as the top-level parent slot — an
    unambiguous structural swap. Every other contamination pattern is
    flagged NEEDS_REVIEW and left for the FSO; the postprocessor does
    NOT reconstruct missing parent CNICs from per-row values or guess
    which parent slot a misplaced constant belongs to.

      * Rule E check: mother_name must appear verbatim — either as the
        transliterated Roman string or as the model's own Urdu echo
        (_raw_mother_name_urdu) — somewhere in the raw model response. If
        neither form appears, the name was constructed rather than copied.
      * Rule E (father) check: symmetric check for father_name against
        _raw_father_name_urdu.
      * Rule F check: two children on the same B-form with identical
        child_name values are a hard fail (real siblings virtually never
        share an identical full name). No auto-correct; confidence forced
        to 0 and flagged NEEDS_REVIEW.
      * Rule G check: if a child's child_registration_number exactly
        matches a parent's CNIC number on the same case, that is a
        contamination signal independent of the swap detection above.
        Confidence is forced to 0 and the field flagged NEEDS_REVIEW.
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

    consistency_check = result.get("_consistency_check")
    if (
        isinstance(consistency_check, dict)
        and consistency_check.get("applicant_cnic_matches_father_cnic") is False
    ):
        # Do NOT auto-correct. Applicant != father is a legitimate case
        # (e.g. father deceased, mother is the applicant) — the pipeline
        # has no independent evidence of who the applicant is relative to
        # the child, so it must not invent which value (if either) is
        # correct. Preserve both extracted values exactly as read and
        # flag both for FSO review with confidence forced to 0.
        corrections.append(
            "FLAG applicant_cnic_number/father_cnic_number: model's consistency "
            "check reports these differ; applicant's relationship to the child "
            "is not independently established — neither value can be assumed "
            "correct without source-document verification (NEEDS_REVIEW)"
        )

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
            # If the top-level parent value is already a well-formed CNIC,
            # and the collision is against only one (not most/all) child
            # rows, this is far more likely a single-row contamination on
            # the CHILD side — e.g. the model copied the parent CNIC into
            # one child's registration-number cell — rather than evidence
            # that the parent field itself was misread. Rule G (below)
            # independently catches and flags that child-side row. Treating
            # this as a parent-side swap here would incorrectly zero out a
            # correct parent CNIC.
            colliding_rows = sum(1 for cr in nonempty_regs if cr == top_val)
            isolated_contamination = (
                _cnic(top_val)
                and nonempty_regs
                and colliding_rows < len(nonempty_regs)
            )
            if isolated_contamination:
                continue

            # Deterministic swap ONLY when every non-empty child row
            # carries the same value as the top-level parent — a clean
            # structural column swap with no ambiguity about where the
            # parent CNIC ended up. Any other collision pattern (mixed
            # rows, partial contamination, no row carries top_val) has
            # no independent evidence for recovery and must flag per
            # null-over-guess.
            all_rows_constant = nonempty_regs and all(cr == top_val for cr in nonempty_regs)
            if all_rows_constant and _cnic(top_val):
                for child in children:
                    if isinstance(child, dict) and str(child.get("child_registration_number") or "") == top_val:
                        child["child_registration_number"] = None
                corrections.append(
                    f"Swapped {parent_field} ↔ child_registration_number "
                    f"(every child row held '{top_val}'; cleared child_registration_number "
                    f"rows so FSO re-reads them from Column 2 — do not guess)"
                )
            else:
                corrections.append(
                    f"FLAG {parent_field}: top-level value '{top_val}' collides with "
                    "a child registration number in a non-uniform pattern; real "
                    "parent CNIC cannot be recovered without source-document "
                    "verification (NEEDS_REVIEW)"
                )
            continue

        # ── Signal 2: format-based ──
        # If the top-level parent CNIC is empty or malformed, do NOT
        # reconstruct it from per-row values — the pipeline has no
        # independent evidence of what this cell read. Leave the
        # original value (empty or malformed) in place and flag for FSO
        # review. validate_field will already have zeroed confidence
        # when the format is invalid.
        if not _cnic(top_val):
            corrections.append(
                f"FLAG {parent_field}: value '{top_val}' is not a valid CNIC; "
                "postprocessor will not reconstruct missing digits from per-row "
                "data or another CNIC (NEEDS_REVIEW)"
            )
            continue

    # ── Signal 3: structural invariant ──
    # Child registration numbers should be different per row. If every row has
    # the same valid-CNIC-looking value, a parent CNIC was likely copied into
    # all child_registration_number slots. Signal 1 above may already have
    # cleared the child rows when the constant matched a top-level parent;
    # this branch catches the residual case where the constant does not
    # match any top-level parent (both parents may be empty/misread) and
    # we have no independent evidence of which parent slot, if either, the
    # constant belongs to. Per null-over-guess, flag only; do NOT assign
    # the constant to a parent slot via heuristic, and do NOT relocate the
    # displaced parent value into an arbitrary child row.
    if len(nonempty_regs) >= 2 and len(set(nonempty_regs)) == 1 and _cnic(nonempty_regs[0]):
        constant = nonempty_regs[0]
        corrections.append(
            f"FLAG child_registration_number: every row has the same value '{constant}'; "
            "a parent CNIC may have been copied into all child rows. Neither parent "
            "slot is auto-populated from this value; the FSO must re-read Column 2 "
            "per row and Columns 3/4 for the parent CNICs (NEEDS_REVIEW)"
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
                # Keep the source value unchanged and lower confidence only for recovered fields.
                for field in (
                    "father_cnic_number",
                    "mother_cnic_number",
                    "applicant_cnic_number",
                ):
                    if field in correction:
                        conf[field] = 0.5
            elif correction.startswith("FLAG"):
                # Force confidence to 0 for flagged fields; validate_extraction will
                # also do this, but doing it here makes the post-processed output explicit.
                if "father_cnic_number" in correction:
                    conf["father_cnic_number"] = 0
                if "mother_cnic_number" in correction:
                    conf["mother_cnic_number"] = 0
                if "applicant_cnic_number" in correction:
                    conf["applicant_cnic_number"] = 0
                if "child_registration_number" in correction:
                    child_conf = conf.get("children")
                    if isinstance(child_conf, list):
                        for cc in child_conf:
                            if isinstance(cc, dict):
                                cc["child_registration_number"] = 0

    # ── Rule E: mother_name transliteration consistency ──
    # The prompt instructs the model to emit both the transliterated
    # mother_name (Roman) and the original Urdu text (_raw_mother_name_urdu)
    # read directly from the B-form cell. If both are present, the Roman
    # name must be a plausible transliteration of the Urdu echo. A large
    # mismatch means the model constructed a name from world knowledge
    # (e.g. "Zahida Begum" when the cell actually reads "عائشہ بی بی"
    # → "Ayesha Bibi") rather than reading the cell — a hallucination
    # that should not pass silently.
    mother_name = str(result.get("mother_name") or "").strip()
    raw_urdu = str(result.get("_raw_mother_name_urdu") or "").strip()

    if mother_name and raw_urdu:
        expected_roman = transliterate_urdu_to_roman(raw_urdu)
        if expected_roman:
            sim = SequenceMatcher(
                None, mother_name.lower(), expected_roman.lower()
            ).ratio()
            if sim < 0.6:
                corrections.append(
                    f"FLAG mother_name: '{mother_name}' does not match "
                    f"transliteration of _raw_mother_name_urdu ('{raw_urdu}' "
                    f"→ '{expected_roman}', similarity {sim:.2f}); "
                    "likely hallucinated (NEEDS_REVIEW)"
                )
                if isinstance(conf, dict):
                    conf["mother_name"] = 0
    elif raw_model_text and mother_name:
        # Fallback: no Urdu echo available — check if mother_name appears
        # anywhere in the raw model output outside the JSON value slot.
        # (Rare path; the model almost always includes its own values.)
        source_norm = " ".join(raw_model_text.split())
        if mother_name not in raw_model_text and " ".join(mother_name.split()) not in source_norm:
            corrections.append(
                f"FLAG mother_name: '{mother_name}' does not appear verbatim "
                "in the model's own response; likely hallucinated (NEEDS_REVIEW)"
            )
            if isinstance(conf, dict):
                conf["mother_name"] = 0

    # ── Rule E (father): father_name transliteration consistency ──
    # Mirror of the mother_name check above. The prompt now instructs the
    # model to emit both the transliterated father_name (Roman) and the
    # original Urdu text (_raw_father_name_urdu) read directly from the
    # B-form's Column 3 cell. A large transliteration mismatch means the
    # model constructed a name from world knowledge (e.g. "Muhammad Aslam"
    # when the cell actually reads "اشتیاق احمد مغل" → "Ishtiaq Ahmed
    # Mughal") rather than reading the cell — a hallucination that must
    # not pass silently, especially because father_name gates the
    # death-certificate cross-check downstream.
    father_name = str(result.get("father_name") or "").strip()
    raw_father_urdu = str(result.get("_raw_father_name_urdu") or "").strip()

    if father_name and raw_father_urdu:
        expected_father_roman = transliterate_urdu_to_roman(raw_father_urdu)
        if expected_father_roman:
            father_sim = SequenceMatcher(
                None, father_name.lower(), expected_father_roman.lower()
            ).ratio()
            if father_sim < 0.6:
                corrections.append(
                    f"FLAG father_name: '{father_name}' does not match "
                    f"transliteration of _raw_father_name_urdu ('{raw_father_urdu}' "
                    f"→ '{expected_father_roman}', similarity {father_sim:.2f}); "
                    "likely hallucinated (NEEDS_REVIEW)"
                )
                if isinstance(conf, dict):
                    conf["father_name"] = 0
    elif raw_model_text and father_name:
        # Fallback: no Urdu echo available — check if father_name appears
        # anywhere in the raw model output outside the JSON value slot.
        source_norm = " ".join(raw_model_text.split())
        if father_name not in raw_model_text and " ".join(father_name.split()) not in source_norm:
            corrections.append(
                f"FLAG father_name: '{father_name}' does not appear verbatim "
                "in the model's own response; likely hallucinated (NEEDS_REVIEW)"
            )
            if isinstance(conf, dict):
                conf["father_name"] = 0

    # ── Rule F: duplicate sibling names (hard fail, no auto-correct) ──
    # Real siblings listed on the same B-form virtually never share an
    # identical full name. Identical child_name values across rows are a
    # strong hallucination signal — the model copied one name into both
    # slots. Confidence is forced to 0 on every affected row; the FSO
    # must re-read the cells.
    child_names: list[tuple[int, str]] = []
    for i, child in enumerate(children):
        if not isinstance(child, dict):
            continue
        nm = child.get("child_name")
        if nm is not None:
            s = str(nm).strip()
            if s:
                child_names.append((i, s))
    if len(child_names) >= 2:
        seen: dict[str, list[int]] = {}
        for i, nm in child_names:
            seen.setdefault(nm.lower(), []).append(i)
        dup_groups = [idxs for idxs in seen.values() if len(idxs) > 1]
        if dup_groups:
            for idxs in dup_groups:
                sample = child_names[idxs[0]][1]
                corrections.append(
                    f"FLAG child_name: rows {idxs} share identical name "
                    f"'{sample}'; real siblings do not — NEEDS_REVIEW"
                )
                if isinstance(conf, dict):
                    child_conf = conf.get("children")
                    if isinstance(child_conf, list):
                        for idx in idxs:
                            if 0 <= idx < len(child_conf) and isinstance(child_conf[idx], dict):
                                child_conf[idx]["child_name"] = 0

    # ── Rule G: child registration number cross-contamination ──
    # Independent of the swap detection above: if a single child's
    # child_registration_number matches a parent CNIC number, that is a
    # wrong-column read for that specific row. Flag and zero confidence
    # even when the swap detector did not fire (e.g. only one child row
    # was mis-read).
    father_cnic_top = str(result.get("father_cnic_number") or "")
    mother_cnic_top = str(result.get("mother_cnic_number") or "")
    parent_cnic_set = {v for v in (father_cnic_top, mother_cnic_top) if _cnic(v)}
    if parent_cnic_set:
        for i, child in enumerate(children):
            if not isinstance(child, dict):
                continue
            cr = str(child.get("child_registration_number") or "")
            if cr in parent_cnic_set:
                corrections.append(
                    f"FLAG children.{i}.child_registration_number: value '{cr}' "
                    "matches a parent CNIC on the same case; wrong-column read (NEEDS_REVIEW)"
                )
                if isinstance(conf, dict):
                    child_conf = conf.get("children")
                    if isinstance(child_conf, list) and 0 <= i < len(child_conf):
                        if isinstance(child_conf[i], dict):
                            child_conf[i]["child_registration_number"] = 0

    # ── B-form CNIC confidence recalibration ──
    # The model routinely emits hedged 0.5 scores for correctly-read CNICs
    # on B-forms. Apply the same floor as postprocess_cnic, but only when
    # no earlier correction has already flagged the field. A flagged CNIC
    # (swap, format failure, contamination) stays at 0 — recalibration
    # must not mask real problems.
    if isinstance(conf, dict):
        flagged_fields = set()
        for c in corrections:
            if "father_cnic_number" in c:
                flagged_fields.add("father_cnic_number")
            if "mother_cnic_number" in c:
                flagged_fields.add("mother_cnic_number")
            if "applicant_cnic_number" in c:
                flagged_fields.add("applicant_cnic_number")

        for cnic_field in (
            "father_cnic_number",
            "mother_cnic_number",
            "applicant_cnic_number",
        ):
            val = str(result.get(cnic_field) or "").strip()
            if not _cnic_match(val):
                continue
            if cnic_field in flagged_fields:
                continue
            current = conf.get(cnic_field)
            if current is not None and isinstance(current, (int, float)) and current >= 0.5:
                conf[cnic_field] = max(float(current), _CNIC_CONFIDENCE_FLOOR)

        # Consistency boost: applicant_cnic_number on a B-form is almost
        # always the father. If it matches father_cnic_number and both are
        # valid, the cross-confirmation justifies the confidence floor.
        applicant_val = str(result.get("applicant_cnic_number") or "").strip()
        father_val = str(result.get("father_cnic_number") or "").strip()
        if (
            _cnic_match(applicant_val)
            and _cnic_match(father_val)
            and applicant_val == father_val
            and "applicant_cnic_number" not in flagged_fields
        ):
            current = conf.get("applicant_cnic_number")
            if current is not None and isinstance(current, (int, float)) and current >= 0.5:
                conf["applicant_cnic_number"] = max(float(current), _CNIC_CONFIDENCE_FLOOR)

    result["_column_corrections"] = corrections
    return result


# ─── CNIC-document post-processing (father_cnic / mother_cnic) ─────────────


def postprocess_cnic(result: dict, doc_type: str) -> dict:
    """
    Postprocess a father_cnic or mother_cnic extraction.

      * Item 4 — confidence recalibration: if the CNIC number is well-
        formatted and no cross-check flagged it, raise the model's self-
        assessed score to at least _CNIC_CONFIDENCE_FLOOR. The model
        routinely emits 0.5 for correctly-read values on worn cards; this
        floor removes that false-negative band without hiding genuinely
        uncertain reads.
      * Item 5 — per-document mix-up signal: if the extracted name is
        empty/missing while father_or_husband_name is populated, the CNIC
        likely belongs to the OTHER parent (father's card uploaded as
        mother's, or vice versa). Flag NEEDS_REVIEW; the FSO can confirm
        against the physical card.
      * Cross-document routing-mixup detection (father_cnic and mother_cnic
        producing identical payloads) is implemented separately in
        compare_father_mother_cnic_extractions() because it needs both
        extractions in scope.
    """
    if doc_type not in ("father_cnic", "mother_cnic"):
        return result

    corrections: list[str] = []
    conf = result.get("confidence")

    cnic_val = str(result.get("cnic_number") or "").strip()
    if _cnic_match(cnic_val):
        # Item 4 — recalibrate upward when format is clean and no swap/
        # contamination flag has already driven confidence to 0.
        if isinstance(conf, dict):
            current = conf.get("cnic_number")
            if current is None or (isinstance(current, (int, float)) and current >= 0.5):
                conf["cnic_number"] = max(float(current or 0), _CNIC_CONFIDENCE_FLOOR)

        # Item 5 — per-document signal: empty 'name' with a populated
        # father_or_husband_name / father_name strongly suggests the wrong
        # card was uploaded for this slot.
        name = str(result.get("name") or "").strip()
        husband_or_father = str(
            result.get("father_or_husband_name") or result.get("father_name") or ""
        ).strip()
        if not name and husband_or_father:
            corrections.append(
                f"FLAG {doc_type}.name: card extracted with no cardholder name "
                f"but '{husband_or_father}' as father/husband — possible wrong card "
                "uploaded for this slot (NEEDS_REVIEW)"
            )
            if isinstance(conf, dict):
                conf["name"] = 0

    result["_cnic_corrections"] = corrections
    return result


def _cnic_match(value: str) -> bool:
    return bool(CNIC_RE.match(str(value or "").strip()))


def compare_father_mother_cnic_extractions(
    father_doc: dict | None,
    mother_doc: dict | None,
) -> list[str]:
    """
    Cross-document item 5 check: if the father_cnic and mother_cnic
    extractions produced identical payloads (same CNIC, or same name AND
    same DOB), the same card was uploaded in both slots or the model
    mis-routed the images. Returns a list of correction strings suitable
    for appending to either document's _cnic_corrections.

    Called by cases.py after both extractions have been saved, typically
    during case compilation or a dedicated cross-check endpoint.
    """
    if not father_doc or not mother_doc:
        return []
    if not isinstance(father_doc, dict) or not isinstance(mother_doc, dict):
        return []

    signals: list[str] = []

    f_cnic = str(father_doc.get("cnic_number") or "").strip()
    m_cnic = str(mother_doc.get("cnic_number") or "").strip()
    if f_cnic and m_cnic and f_cnic == m_cnic:
        signals.append(
            f"FLAG father_cnic.cnic_number == mother_cnic.cnic_number ({f_cnic}): "
            "same CNIC extracted from both cards — routing mix-up or duplicate upload (NEEDS_REVIEW)"
        )

    f_name = str(father_doc.get("name") or "").strip().lower()
    m_name = str(mother_doc.get("name") or "").strip().lower()
    f_dob = str(father_doc.get("date_of_birth") or "").strip()
    m_dob = str(mother_doc.get("date_of_birth") or "").strip()
    if f_name and m_name and f_name == m_name and f_dob and f_dob == m_dob:
        signals.append(
            f"FLAG father_cnic and mother_cnic share name='{f_name}' and "
            f"date_of_birth='{f_dob}': same card was extracted for both slots (NEEDS_REVIEW)"
        )

    return signals
