"""
Qwen-VL/Qwen-plus client via DashScope's OpenAI-compatible API.
Ported from the original prototype's pipeline.py approach.
"""

from openai import OpenAI
from ..config import API_KEY, BASE_URL

# Module-level singleton client
_client: OpenAI | None = None


def get_qwen_client() -> OpenAI | None:
    """Get or create the DashScope OpenAI-compatible client."""
    global _client
    if _client is None and API_KEY:
        _client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    return _client


def is_ai_available() -> bool:
    """Check if the Qwen AI client is configured and available."""
    return get_qwen_client() is not None
