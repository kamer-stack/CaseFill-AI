"""
Bilingual help chatbot service using Qwen-plus.
"""

import re

from ..config import QWEN_TEXT_MODEL
from .qwen_client import get_qwen_client
from .prompts import HELP_SYSTEM_PROMPT


def sanitize_disallowed_terms(text: str) -> str:
    """Replace disallowed terms with neutral alternatives."""
    if not text:
        return ""
    text = re.sub(r"\bNADRA\b", "National Civil Registration Authority", text, flags=re.IGNORECASE)
    text = re.sub(r"\bNadra\b", "National Civil Registration Authority", text)
    text = re.sub(r"\bPakistani\b", "National", text, flags=re.IGNORECASE)
    text = re.sub(r"\bPakistan\b", "National Civil Registry", text, flags=re.IGNORECASE)
    return text


def chat_completion(
    message: str,
    history: list[dict] | None = None,
    current_role: str = "fso",
    current_task: str = "general_intake",
    task_label: str = "",
    active_step: str = "",
    case_context: dict | None = None,
) -> str:
    """
    Generate a help chatbot response using Qwen-plus.
    Falls back to keyword-based responses if AI is unavailable.
    """
    role_label = {
        "family": "Orphan Family (خاندان)",
        "fso": "Field Support Officer (FSO)",
        "admin": "Central Directorate Admin",
    }.get(current_role, current_role)

    # Build system instruction with context
    system_msg = HELP_SYSTEM_PROMPT + f"""

=== CAPTURED USER & TASK CONTEXT ===
- Active User Role: {role_label}
- Current Active Task: {task_label or current_task or 'General Intake Navigation'}
- Current Active Screen/Step: {active_step or 'Active Workspace'}
"""
    if case_context:
        system_msg += f"- Active Case Reference: #{case_context.get('caseNumber', 'N/A')}, Child: {case_context.get('childName', 'N/A')}\n"

    # Try AI completion
    client = get_qwen_client()
    if client:
        try:
            messages = [{"role": "system", "content": system_msg}]

            # Add history (last 6 turns)
            if history:
                for turn in history[-6:]:
                    role = "user" if turn.get("role") == "user" else "assistant"
                    messages.append({"role": role, "content": turn.get("text", "")})

            messages.append({"role": "user", "content": message})

            response = client.chat.completions.create(
                model=QWEN_TEXT_MODEL,
                messages=messages,
            )

            reply = response.choices[0].message.content
            return sanitize_disallowed_terms(reply)

        except Exception as e:
            print(f"Chat AI error, using fallback: {e}")

    # Fallback: keyword-based responses
    return sanitize_disallowed_terms(
        _generate_fallback_reply(message, current_role, current_task)
    )


def _generate_fallback_reply(query: str, role: str, current_task: str) -> str:
    """Generate a deterministic help reply based on keyword matching."""
    q = query.lower()

    if current_task == "document_upload" or any(w in q for w in ["upload", "camera", "scan", "photo"]):
        return """### Guide: Step 1 Document Uploading & Camera Capture
When uploading the 8 mandatory documents:
1. **Clear Lighting & Flat Framing:** Ensure scans or photos are well-lit, non-reflective, and show all 4 borders of the document.
2. **Key Requirements:**
   - **Child Picture:** Centered passport-style portrait.
   - **13-digit CRC (B-Form):** Must show the complete registration number and family member list.
   - **Death Certificate:** Official demise document with UC registration number.
   - **School Marksheet:** Current academic year showing enrolled grade.
3. **Missing Father CNIC:** Toggle "Not Provided" and provide an explanatory note."""

    if current_task == "ocr_review" or any(w in q for w in ["ocr", "mismatch", "confidence", "review"]):
        return """### Guide: Step 2 OCR Review & Field Verification
1. **Side-by-Side Comparison:** Compare AI-extracted fields against the original scan.
2. **Resolving Cross-Check Flags:** Click the edit icon to correct discrepancies before proceeding.
3. **Confidence Scores:** Green (high), Amber (moderate), Red (low - manual check required).
4. **Editable Fields:** All extracted data can be corrected before generating the final summary."""

    if any(w in q for w in ["alter", "wrong", "edit", "change"]):
        return """### How to Alter & Correct an Uploaded Application
1. Log into your Family Portal with your registered CNIC.
2. Click "Alter / Correct Uploaded Application" on your active case.
3. Re-upload or replace files for any of the 8 document slots.
4. Update address or other details and add a change note.
5. Your assigned Field Support Officer will receive the updated files."""

    if any(w in q for w in ["fso", "provision", "manage"]) and any(w in q for w in ["add", "create", "delete"]):
        return """### Admin Guide: FSO Account Management
1. **Provision New Officer:** Click "+ Provision FSO", enter name, CNIC, phone, cluster.
2. **Roster Search:** Filter by cluster, search by name/CNIC.
3. **Edit & Password Reset:** Update credentials or transfer clusters.
4. **Deactivate/Delete:** Revoke credentials and unassign pending cases."""

    if any(w in q for w in ["duplicate", "crc", "cnic"]):
        return """### Cross-Case Duplicate Detection Rules
- The system validates Child CRC, Mother CNIC, and Father CNIC against all existing cases.
- Duplicate warnings display matched Case Number, Child Name, and Status.
- Resolution happens during the FSO home visit by inspecting physical documents."""

    if any(w in q for w in ["document", "b-form", "death", "marksheet"]):
        return """### The 8 Mandatory Intake Documents
1. **Child Photograph:** Recent portrait with clear facial visibility.
2. **School Result Card:** Active schooling proof (Grade 1-10).
3. **Child Registration Certificate (B-Form/CRC):** 13-digit birth certificate.
4. **Union Council Death Certificate:** Father's demise certificate.
5. **Mother's Smart CNIC:** Front and back of identity card.
6. **Father's CNIC:** Deceased father's card (or "Not Provided").
7. **Residential Address:** Full address for regional routing.
8. **Mother's Education Level:** For vocational grant eligibility."""

    return """### Welcome to CaseFill-AI Help Support (OFSP 2026)
I can assist you with:
- **Document Standards:** Rules for B-Form, Death Certificate, Marksheet, CNICs
- **Document Alteration:** How families correct files on submitted cases
- **FSO Management:** Admin CRUD for Field Support Officers
- **Duplicate & Cross-Check Rules:** Preventing double registrations
- **Regional Routing:** How cases are assigned to officers

Ask your question in English, اردو (Urdu), or Roman Urdu!"""
