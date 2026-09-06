"""
OCR.space API client.

Used ONLY for two document cases (per project decision, confirmed accuracy
testing on real documents — see project notes):
  - B-form (always dense Urdu table, always routed here)
  - Old-format CNIC (no printed English field labels)

New bilingual CNIC, death certificate, result card, and child picture all
stay on Qwen-VL vision extraction unchanged — this client is never called
for those.

OCR.space returns raw text, not structured fields. The raw text this
returns is meant to be fed into a Qwen-plus TEXT-structuring prompt
(see prompts.py build_bform_text_structuring_prompt /
build_cnic_text_structuring_prompt) which converts it into the same JSON
schema the rest of the pipeline already expects — postprocess_bform,
postprocess_cnic, validate_extraction, and the header-keyed adapter's
majority-vote logic all run unchanged downstream.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from ..config import OCR_SPACE_API_KEY, OCR_SPACE_URL

# OCR.space free tier caps request size; keep a sane timeout so a slow/
# hung request doesn't stall the FSO's upload indefinitely.
_REQUEST_TIMEOUT_SECONDS = 30


class OCRSpaceError(RuntimeError):
    """Raised when OCR.space fails or returns no usable text."""


def extract_urdu_text(image_path: str | Path) -> str:
    """
    Send an image to OCR.space (Engine 3, language=urd) and return the
    raw extracted text.

    Raises OCRSpaceError on any failure (missing API key, network error,
    non-OK API response, or empty result) — callers should NOT silently
    fall back to a guessed value; an extraction failure here must surface
    as an error the FSO sees, per NULL OVER GUESS.
    """
    if not OCR_SPACE_API_KEY:
        raise OCRSpaceError(
            "OCR_SPACE_API_KEY not configured. Set it in .env before "
            "using B-form or old-CNIC extraction."
        )

    image_path = Path(image_path)
    if not image_path.exists():
        raise OCRSpaceError(f"Image not found: {image_path}")

    try:
        with open(image_path, "rb") as f:
            response = httpx.post(
                OCR_SPACE_URL,
                files={"file": (image_path.name, f)},
                data={
                    "apikey": OCR_SPACE_API_KEY,
                    "language": "urd",
                    "OCREngine": "3",
                    "isOverlayRequired": "false",
                    "scale": "true",
                    "detectOrientation": "true",
                },
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
    except httpx.HTTPError as e:
        raise OCRSpaceError(f"OCR.space request failed: {e}") from e

    if response.status_code != 200:
        raise OCRSpaceError(f"OCR.space returned HTTP {response.status_code}: {response.text[:300]}")

    try:
        payload = response.json()
    except ValueError as e:
        raise OCRSpaceError(f"OCR.space returned non-JSON response: {response.text[:300]}") from e

    if payload.get("IsErroredOnProcessing"):
        error_msg = payload.get("ErrorMessage") or payload.get("ErrorDetails") or "unknown error"
        if isinstance(error_msg, list):
            error_msg = "; ".join(str(m) for m in error_msg)
        raise OCRSpaceError(f"OCR.space processing error: {error_msg}")

    parsed_results = payload.get("ParsedResults") or []
    if not parsed_results:
        raise OCRSpaceError("OCR.space returned no ParsedResults.")

    text = parsed_results[0].get("ParsedText") or ""
    text = text.strip()
    if not text:
        raise OCRSpaceError("OCR.space returned empty text for this image.")

    return text
