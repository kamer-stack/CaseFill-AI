"""
Urdu-to-Roman transliteration service.
Converts Urdu/Arabic script text to English (Roman) transliteration
using the Qwen-plus text model with in-memory caching.
"""

import re

from ..config import QWEN_TEXT_MODEL
from .qwen_client import get_qwen_client

# In-memory cache to avoid repeated API calls for the same text
_cache: dict[str, str] = {}


def transliterate_urdu_to_roman(text: str) -> str | None:
    """
    Transliterate Urdu/Arabic script text to Roman/English.

    Uses the Qwen-plus text model for accurate transliteration.
    Results are cached in-memory for the lifetime of the process.

    Args:
        text: Text in Urdu/Arabic script to transliterate.

    Returns:
        Roman/English transliteration string, or None if transliteration fails.
    """
    if not text or not text.strip():
        return None

    normalized_key = text.strip()

    # Check cache first
    if normalized_key in _cache:
        return _cache[normalized_key]

    client = get_qwen_client()
    if client is None:
        return None

    prompt = (
        "You are an expert Urdu-to-English transliterator for official documents.\n"
        "Transliterate the following Urdu/Arabic script text into its standard "
        "Roman/English equivalent as it would appear on an official document.\n\n"
        "Rules:\n"
        "1. Use the most common Roman spelling for names.\n"
        "2. Preserve proper capitalization (first letter of each word capitalized).\n"
        "3. Output ONLY the transliterated text, nothing else.\n"
        "4. Do not translate, only transliterate (convert script, not meaning).\n"
        "5. If the text is already in Roman/English, return it exactly as-is.\n\n"
        f"Text to transliterate: {normalized_key}\n\n"
        "Transliteration:"
    )

    try:
        response = client.chat.completions.create(
            model=QWEN_TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )
        result = response.choices[0].message.content.strip()

        # Clean up: remove quotes the model might wrap with
        if len(result) > 2 and result[0] == '"' and result[-1] == '"':
            result = result[1:-1]
        if len(result) > 2 and result[0] == "'" and result[-1] == "'":
            result = result[1:-1]

        # Cache the result
        _cache[normalized_key] = result
        return result

    except Exception as e:
        print(f"Transliteration error for '{normalized_key}': {e}")
        return None


def batch_transliterate(texts: list[str]) -> dict[str, str | None]:
    """
    Transliterate multiple Urdu texts in a batch.
    Returns a dict mapping original text to transliterated text.
    """
    results = {}
    for text in texts:
        results[text] = transliterate_urdu_to_roman(text)
    return results


def is_urdu_only(text: str) -> bool:
    """Check if text contains only Urdu/Arabic characters (no Latin)."""
    has_arabic = bool(re.search(
        r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]", text
    ))
    has_latin = bool(re.search(r"[A-Za-z]", text))
    return has_arabic and not has_latin


def is_roman_only(text: str) -> bool:
    """Check if text contains only Latin/Roman characters (no Arabic)."""
    has_latin = bool(re.search(r"[A-Za-z]", text))
    has_arabic = bool(re.search(
        r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]", text
    ))
    return has_latin and not has_arabic
