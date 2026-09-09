"""
Prompt-decontamination test for build_bform_prompt().

Step 5 (forensic investigation) established that the B-form extraction prompt
contained concrete personal-name examples that could seed the VLM with
candidate names when a name cell is unclear:

  * "Ayesha Bibi" as a positive transliteration example (Rule E mother)
  * "Muhammad Aslam" / "Muhammad Ibrahim" as negative examples (Rule E father)
  * A COMMON NAME PATTERNS list with 18+ concrete Pakistani personal names
  * Concrete transliteration examples ("Noor Zaman", "Ahmed Tariq", "Fatima Zahra")

Step 6 removed all concrete personal-name seeds and replaced them with
abstract transliteration guidance. This test locks that decontamination in.

IMPORTANT DISTINCTION:
  - This test CAN prove: "the rendered prompt no longer contains candidate names."
  - This test CANNOT prove: "Qwen-VL will never hallucinate a name again."
  The VLM's own training data contains millions of Pakistani names; prompt
  decontamination removes one vector, not all possible sources.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.prompts import build_bform_prompt  # noqa: E402

_SCHEMA_PATH = _BACKEND / "app" / "data" / "extraction_schemas.json"


@pytest.fixture(scope="module")
def bform_prompt() -> str:
    """Render the B-form prompt once for the whole module."""
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        schemas = json.load(f)
    return build_bform_prompt(schemas.get("b_form", {}), target_child_serial_number=2)


# ── Removed positive/negative examples must not appear ──────────────────────

REMOVED_NAMES = [
    "Ayesha Bibi",
    "Muhammad Aslam",
    "Muhammad Ibrahim",
    "Zahida",
    "Naseem",
    "Ishtiaq Ahmed Mughal",
]


@pytest.mark.parametrize("name", REMOVED_NAMES)
def test_removed_name_not_in_prompt(bform_prompt: str, name: str):
    """A concrete personal-name example removed in Step 6 must not reappear."""
    assert name not in bform_prompt, (
        f"removed personal-name example '{name}' still appears in the B-form prompt"
    )


# ── COMMON NAME PATTERNS list must be gone ──────────────────────────────────

COMMON_NAME_LIST_NAMES = [
    "Muhammad", "Mohammad", "Ahmed", "Ahmad", "Ali",
    "Khan", "Hussain", "Hassan", "Abdullah", "Ibrahim", "Tariq",
    "Fatima", "Ayesha", "Zainab", "Bano", "Bibi", "Begum",
    "Noor", "Reza", "Raza", "Zaman",
]


def test_common_name_patterns_section_removed(bform_prompt: str):
    """The COMMON NAME PATTERNS heading must no longer exist."""
    assert "COMMON NAME PATTERNS" not in bform_prompt


@pytest.mark.parametrize("name", COMMON_NAME_LIST_NAMES)
def test_common_name_list_entry_absent(bform_prompt: str, name: str):
    """No entry from the old COMMON NAME PATTERNS list should survive.

    Uses word-boundary matching to avoid false positives from substrings
    inside unrelated words (e.g. 'Ali' inside 'specializing').
    """
    pattern = r"\b" + re.escape(name) + r"\b"
    matches = list(re.finditer(pattern, bform_prompt, re.IGNORECASE))
    # Filter out matches that are inside the NULL OVER GUESS transliteration-
    # variation example ("Ahmed" vs "Ahmad") — those are legitimate linguistic
    # guidance, not candidate personal-name seeds.
    for m in matches:
        ctx_start = max(0, m.start() - 80)
        ctx_end = min(len(bform_prompt), m.end() + 80)
        context = bform_prompt[ctx_start:ctx_end]
        assert "transliteration variation" in context, (
            f"COMMON NAME PATTERNS entry '{name}' found outside the "
            f"transliteration-variation example; context: ...{context}..."
        )


# ── Concrete transliteration examples must be gone ─────────────────────────

REMOVED_TRANSLITERATION_EXAMPLES = [
    "Noor Zaman",
    "Ahmed Tariq",
    "Fatima Zahra",
]


@pytest.mark.parametrize("example", REMOVED_TRANSLITERATION_EXAMPLES)
def test_concrete_transliteration_example_absent(bform_prompt: str, example: str):
    """A concrete transliteration example removed in Step 6 must not reappear."""
    assert example not in bform_prompt, (
        f"removed transliteration example '{example}' still in prompt"
    )


# ── Raw-evidence architecture must be preserved ─────────────────────────────

def test_raw_father_name_urdu_instruction_present(bform_prompt: str):
    """The prompt must still require _raw_father_name_urdu."""
    assert "_raw_father_name_urdu" in bform_prompt


def test_raw_mother_name_urdu_instruction_present(bform_prompt: str):
    """The prompt must still require _raw_mother_name_urdu."""
    assert "_raw_mother_name_urdu" in bform_prompt


def test_raw_child_names_urdu_instruction_present(bform_prompt: str):
    """The prompt must still require _raw_child_names_urdu."""
    assert "_raw_child_names_urdu" in bform_prompt


def test_rule_e_mother_still_present(bform_prompt: str):
    """Rule E mother-name instruction block must survive decontamination."""
    assert "RULE E" in bform_prompt
    assert "mother_name" in bform_prompt


def test_rule_e_father_still_present(bform_prompt: str):
    """Rule E father-name instruction block must survive decontamination."""
    assert "father_name" in bform_prompt
    assert "father_cnic_number" in bform_prompt


def test_null_over_guess_still_present(bform_prompt: str):
    """NULL OVER GUESS principle must survive decontamination."""
    assert "NULL OVER GUESS" in bform_prompt


def test_transliteration_guidance_present(bform_prompt: str):
    """Abstract TRANSLITERATION GUIDANCE section must replace COMMON NAME PATTERNS."""
    assert "TRANSLITERATION GUIDANCE" in bform_prompt


# ── Urdu document labels must be preserved ──────────────────────────────────

URDU_LABELS = [
    "درخواست دہندہ کا نام",
    "والد کا نام",
    "والدہ کا نام",
    "بچے کا نام",
]


@pytest.mark.parametrize("label", URDU_LABELS)
def test_urdu_document_label_preserved(bform_prompt: str, label: str):
    """Urdu B-form field labels are document instructions, not name seeds."""
    assert label in bform_prompt, (
        f"Urdu document label '{label}' was removed — it should be preserved"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
