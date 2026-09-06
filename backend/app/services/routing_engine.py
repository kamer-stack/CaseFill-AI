"""
AI-based geographic routing engine.
Uses Qwen-plus for intelligent address classification with keyword fallback.
"""

import json
import re

from ..config import QWEN_TEXT_MODEL
from ..db import get_db
from .qwen_client import get_qwen_client
from .prompts import build_routing_prompt


def get_active_regions() -> list[dict]:
    """Fetch all active regions from the database."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM regions WHERE active = 1"
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_regions() -> list[dict]:
    """Fetch all regions from the database."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM regions").fetchall()
        return [dict(r) for r in rows]


def route_address(address: str) -> dict:
    """
    Route an address to the appropriate region using AI + keyword fallback.

    Returns:
        dict with routing result (isAssigned, regionId, regionName, etc.)
    """
    if not address or not isinstance(address, str):
        return _unassigned_result("Empty address provided")

    normalized = address.lower()
    regions = get_active_regions()

    if not regions:
        return _unassigned_result("No active regions configured")

    # Try AI-based routing first
    try:
        ai_result = _ai_route(address, regions)
        if ai_result and ai_result.get("matchedRegionId"):
            # Verify the region exists
            matched = next((r for r in regions if r["id"] == ai_result["matchedRegionId"]), None)
            if matched:
                import json as _json
                keywords = _json.loads(matched.get("keywords", "[]")) if isinstance(matched.get("keywords"), str) else matched.get("keywords", [])
                return {
                    "isAssigned": True,
                    "regionId": matched["id"],
                    "regionName": matched["name"],
                    "urduName": matched.get("urdu_name", ""),
                    "assignedFsoId": matched.get("assigned_fso_id"),
                    "confidence": ai_result.get("confidence", 0.95),
                    "detectedLocation": ai_result.get("detectedCityOrDistrict", ""),
                    "reason": ai_result.get("reasoning", f"AI matched to {matched['name']}"),
                }
    except Exception as e:
        print(f"AI routing failed, falling back to keywords: {e}")

    # Fallback: keyword matching
    return _keyword_route(normalized, regions)


def _ai_route(address: str, regions: list[dict]) -> dict | None:
    """Attempt AI-based routing using Qwen-plus."""
    client = get_qwen_client()
    if client is None:
        return None

    # Build region summaries for the prompt
    region_lines = []
    for r in regions:
        keywords = json.loads(r.get("keywords", "[]")) if isinstance(r.get("keywords"), str) else r.get("keywords", [])
        region_lines.append(
            f'Region ID: "{r["id"]}", Name: "{r["name"]}", '
            f'Keywords/Districts: [{", ".join(keywords)}], '
            f'In-Charge FSO: "{r.get("assigned_fso_id", "Unassigned")}"'
        )
    region_summaries = "\n".join(region_lines)

    prompt = build_routing_prompt(address, region_summaries)

    response = client.chat.completions.create(
        model=QWEN_TEXT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )

    text = response.choices[0].message.content
    # Clean and parse
    text = re.sub(r"```json", "", text).replace("```", "").strip()
    return json.loads(text)


def _keyword_route(normalized_address: str, regions: list[dict]) -> dict:
    """Fallback keyword-based routing."""
    best_match = None

    for region in regions:
        keywords = json.loads(region.get("keywords", "[]")) if isinstance(region.get("keywords"), str) else region.get("keywords", [])
        for kw in keywords:
            if kw.lower() in normalized_address:
                score = len(kw)  # Longer keyword = more specific match
                if best_match is None or score > best_match["score"]:
                    best_match = {
                        "region": region,
                        "score": score,
                        "matchedKeyword": kw,
                    }

    if best_match and best_match["score"] >= 3:
        r = best_match["region"]
        return {
            "isAssigned": True,
            "regionId": r["id"],
            "regionName": r["name"],
            "urduName": r.get("urdu_name", ""),
            "assignedFsoId": r.get("assigned_fso_id"),
            "confidence": 0.94,
            "detectedLocation": best_match["matchedKeyword"],
            "reason": f'Matched "{best_match["matchedKeyword"]}" to {r["name"]}',
        }

    return _unassigned_result(
        "Address could not be mapped unambiguously to an active operational cluster. Routed to Admin Unassigned Queue."
    )


def _unassigned_result(reason: str) -> dict:
    """Return an unassigned routing result."""
    return {
        "isAssigned": False,
        "regionId": None,
        "regionName": "Unassigned (Ambiguous Address)",
        "assignedFsoId": None,
        "confidence": 0.2,
        "detectedLocation": "Unknown",
        "reason": reason,
    }
