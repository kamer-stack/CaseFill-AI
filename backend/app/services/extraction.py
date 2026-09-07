"""
Document extraction service using Qwen-VL via DashScope.
Ported from the original prototype's pipeline.py extract_document().
"""

import base64
import json
import time
from pathlib import Path

from ..config import QWEN_VL_MODEL, QWEN_TEXT_MODEL
from .qwen_client import get_qwen_client
from .prompts import build_bform_prompt, build_generic_prompt
from .prompts_header_keyed import build_bform_prompt_header_keyed
from .prompts_text_structuring import (
    build_bform_text_structuring_prompt,
    build_cnic_text_structuring_prompt,
    build_death_certificate_text_structuring_prompt,
)
from .header_mapping import adapt_header_keyed_to_canonical, match_target_child
from .ocr_space_client import extract_text, extract_urdu_text, OCRSpaceError

# Document types where OCR.space + Qwen-plus text-structuring is used
# instead of Qwen-VL vision.
OCR_SPACE_ALWAYS_TYPES = {"b_form"}                    # always Urdu OCR
OCR_SPACE_ENGLISH_TYPES = {"death_certificate"}        # bilingual doc, English OCR only
OCR_SPACE_CNIC_TYPES = {"mother_cnic", "father_cnic"}  # only when FSO marks "old format"

# Load extraction schemas
_SCHEMA_PATH = Path(__file__).parent.parent / "data" / "extraction_schemas.json"
_schema_cache: dict | None = None


def load_schemas() -> dict:
    """Load extraction schemas from JSON file."""
    global _schema_cache
    if _schema_cache is None:
        if _SCHEMA_PATH.exists():
            _schema_cache = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        else:
            _schema_cache = {}
    return _schema_cache


MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
}

DOCUMENT_TYPES = [
    "child_picture", "result_card", "b_form",
    "death_certificate", "mother_cnic", "father_cnic",
]


def extract_document(
    image_path: str | Path,
    document_type: str,
    target_child_serial_number: int | None = None,
    prompt_builder: "callable | None" = None,
    cnic_format: str | None = None,
    target_child_registration_number: str | None = None,
) -> dict:
    """
    Extract structured data from a document image.

    Args:
        image_path: Path to the image file
        document_type: One of the supported document types
        target_child_serial_number: DEPRECATED — still passed through to the
            prompt as a hint, but no longer trusted to select the target
            child. Kept only for prompt-level backward compatibility.
        prompt_builder: Optional callable(doc_schema, target_child_serial_number) -> str
            used instead of the default header-keyed B-form prompt. Pass
            build_bform_prompt to force the legacy positional prompt. When None,
            b_form uses the header-keyed prompt and the raw output is adapted
            to the canonical flat schema via adapt_header_keyed_to_canonical()
            before being returned. Only applies to b_form.
        cnic_format: "old" or "new", required for mother_cnic/father_cnic to
            decide the extraction route. "old" -> OCR.space + Qwen-plus text
            structuring (no printed English field labels on the card). "new"
            or None -> Qwen-VL vision (existing path, unchanged). Ignored for
            all other document types.
        target_child_registration_number: For b_form only — the target
            orphan's registration number, read by the FSO directly off the
            physical document. Used to deterministically flag is_target_child
            in Python AFTER extraction (see header_mapping.match_target_child),
            instead of trusting the model to guess the right row from a
            serial-number instruction. This is the preferred way to identify
            the target child; target_child_serial_number is legacy.

    Returns:
        dict with keys: extracted (JSON data), model, duration_ms, raw_model_text
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    if document_type not in DOCUMENT_TYPES:
        raise ValueError(f"Unknown document_type: {document_type}. Must be one of: {DOCUMENT_TYPES}")

    schemas = load_schemas()
    doc_schema = schemas.get(document_type, {})

    # ── Route 1: OCR.space + Qwen-plus text structuring ──
    # B-form is always routed here. CNIC is routed here only when the FSO
    # marked it "old format" at upload.
    use_ocr_space = (
        document_type in OCR_SPACE_ALWAYS_TYPES
        or document_type in OCR_SPACE_ENGLISH_TYPES
        or (document_type in OCR_SPACE_CNIC_TYPES and cnic_format == "old")
    )

    if use_ocr_space and prompt_builder is None:
        return _extract_via_ocr_space(
            image_path, document_type, doc_schema, target_child_serial_number,
            target_child_registration_number=target_child_registration_number,
        )

    # ── Route 2: Qwen-VL vision (existing path, unchanged) ──
    # Encode image
    image_b64 = base64.b64encode(image_path.read_bytes()).decode()
    mime = MIME_MAP.get(image_path.suffix.lower(), "image/jpeg")

    # Build prompt
    if document_type == "b_form":
        if prompt_builder is not None:
            prompt = prompt_builder(doc_schema, target_child_serial_number)
        else:
            prompt = build_bform_prompt_header_keyed(doc_schema, target_child_serial_number)
    else:
        prompt = build_generic_prompt(doc_schema, document_type)

    # Call Qwen-VL API
    client = get_qwen_client()
    if client is None:
        raise RuntimeError("Qwen-VL client not configured. Set API_KEY in .env file.")

    start_time = time.time()

    response = client.chat.completions.create(
        model=QWEN_VL_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                ],
            }
        ],
    )

    duration_ms = int((time.time() - start_time) * 1000)
    result_text = response.choices[0].message.content

    # Parse JSON response (strip markdown fences if present)
    result_json = _parse_json_response(result_text)

    # Default B-form path is header-keyed; adapt to the canonical flat schema
    # before callers run postprocess_bform() on the result.
    if document_type == "b_form" and prompt_builder is None:
        result_json = adapt_header_keyed_to_canonical(result_json)
        result_json = match_target_child(result_json, target_child_registration_number)

    if document_type == "child_picture":
        print(
            f"[child_picture quality_check debug] "
            f"quality_check={result_json.get('quality_check')!r}, "
            f"confidence={_get_quality_confidence(result_json)!r}\n"
            f"raw model output: {result_text!r}"
        )
        result_json = _reconcile_quality_check(result_json)

    return {
        "extracted": result_json,
        "model": QWEN_VL_MODEL,
        "duration_ms": duration_ms,
        "raw_model_text": result_text,
    }


def _extract_via_ocr_space(
    image_path: Path,
    document_type: str,
    doc_schema: dict,
    target_child_serial_number: int | None,
    target_child_registration_number: str | None = None,
) -> dict:
    """
    Route: OCR.space (raw Urdu text) -> Qwen-plus (structures it into the
    same JSON shape the vision path would have produced). Used only for
    B-form (always) and old-format CNIC (FSO-selected).

    Raises OCRSpaceError or RuntimeError on failure — callers should
    surface this as an extraction error to the FSO, not silently fall
    back to a guessed value.
    """
    start_time = time.time()

    ocr_language = "eng" if document_type in OCR_SPACE_ENGLISH_TYPES else "urd"
    raw_ocr_text = extract_text(image_path, language=ocr_language)  # raises OCRSpaceError on failure

    if document_type == "b_form":
        prompt = build_bform_text_structuring_prompt(raw_ocr_text, target_child_serial_number)
    elif document_type == "death_certificate":
        prompt = build_death_certificate_text_structuring_prompt(raw_ocr_text, doc_schema)
    else:
        prompt = build_cnic_text_structuring_prompt(raw_ocr_text, doc_schema)

    client = get_qwen_client()
    if client is None:
        raise RuntimeError("Qwen client not configured. Set API_KEY in .env file.")

    response = client.chat.completions.create(
        model=QWEN_TEXT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )

    duration_ms = int((time.time() - start_time) * 1000)
    result_text = response.choices[0].message.content
    result_json = _parse_json_response(result_text)

    if document_type == "b_form":
        result_json = adapt_header_keyed_to_canonical(result_json)
        result_json = match_target_child(result_json, target_child_registration_number)

    return {
        "extracted": result_json,
        "model": f"ocr.space+{QWEN_TEXT_MODEL}",
        "duration_ms": duration_ms,
        "raw_model_text": result_text,
        "raw_ocr_text": raw_ocr_text,
    }


def _get_quality_confidence(result_json: dict):
    conf = result_json.get("confidence")
    if isinstance(conf, dict):
        return conf.get("quality_check")
    return None


def _reconcile_quality_check(result_json: dict) -> dict:
    """
    A face_not_visible verdict alongside high self-reported confidence is
    self-contradictory: the model cannot be highly confident in assessing a
    photo whose face it claims it could not see. Trust the confidence signal
    and override the verdict to "clear".
    """
    conf = _get_quality_confidence(result_json)
    if (
        result_json.get("quality_check") == "face_not_visible"
        and isinstance(conf, (int, float))
        and conf >= 0.9
    ):
        print(
            f"[child_picture quality_check debug] overriding "
            f"face_not_visible -> clear (confidence {conf} >= 0.9)"
        )
        return {**result_json, "quality_check": "clear"}
    return result_json


def _parse_json_response(result_text: str) -> dict:
    """Parse JSON from model response, stripping markdown fences."""
    if "```json" in result_text:
        result_text = result_text.split("```json")[1].split("```")[0].strip()
    elif "```" in result_text:
        result_text = result_text.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(result_text)
    except json.JSONDecodeError as e:
        # Try one more time with more aggressive cleaning
        cleaned = result_text.strip()
        # Find first { and last }
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Failed to parse JSON from model response: {e}\nRaw: {result_text[:500]}")