"""Header-keyed B-form prompt — Step 9 experiment.

Replaces the positional col1..col7 representation with extraction keyed by
the ACTUAL visible Urdu column headers. The VLM reads each header, then
associates cells underneath with that header — never with a numbered column.

The model output schema is intentionally different from the canonical schema
in extraction_schemas.json. An adapter in header_mapping.py converts the
header-keyed result back to the canonical flat shape without guessing or
swapping values.

This module is used ONLY by the Step 9 A/B runner; production extraction
continues to use build_bform_prompt() in prompts.py.
"""

from __future__ import annotations

import json


# Canonical Urdu column headers from the B-form (CRC) table.
# Used as exact-match reference for the header→semantic mapping.
# Order here matches the DOM order in generate_html.py but the prompt does
# NOT assume this order — the VLM must read headers from the image.
CANONICAL_HEADERS = {
    "serial": "نمبر شمار",
    "child": "بچے کا نام اور رجسٹریشن نمبر",
    "father": "والد کا نام اور شناختی کارڈ نمبر",
    "mother": "والدہ کا نام اور شناختی کارڈ نمبر",
    "gender_relation": "جنس / رشتہ",
    "date_of_birth": "تاریخ پیدائش",
    "remarks": "معذوری",
}


def build_bform_prompt_header_keyed(
    doc_schema: dict,
    target_child_serial_number: int | None,
) -> str:
    """Build the header-keyed B-form prompt for the Step 9 experiment.

    Signature matches build_bform_prompt() so it can be passed as the
    prompt_builder= argument to extract_document().
    """
    target_instruction = ""
    if target_child_serial_number is not None:
        target_instruction = f"""

TARGET CHILD: serial_number = {target_child_serial_number}
- After extracting all children, find the child whose serial_number matches {target_child_serial_number}
- Set "is_target_child": true for that child, and "is_target_child": false for all others"""

    prompt = f"""You are a document data extraction assistant specializing in Pakistani B-form (CRC) documents.
These documents are primarily in URDU (Nastaliq script) — read all text carefully RIGHT-TO-LEFT.

═══════════════════════════════════════════════════════════════
URDU READING FUNDAMENTALS
═══════════════════════════════════════════════════════════════

URDU ALPHABET (39 letters):
ا ب پ ت ٹ ث ج چ ح خ د ڈ ذ ر ڑ ز ژ س ش ص ض ط ظ ع غ ف ق ک گ ل م ن ں و ہ ھ ی ے ء

KEY DISTINCTIONS (commonly confused):
- ہ (gol hay) vs ھ (do-chashmi hay - two dots above)
- ن (noon - dot above) vs ں (noon ghunna - no dot)
- ی (choti ye - dots below) vs ے (bari ye - curved tail, no dots)
- ک (kaf) vs گ (gaf - extra stroke)
- ڈ (ḍal - mark above) vs د (dal - plain)

EASTERN ARABIC NUMERALS → WESTERN:
۰→0, ۱→1, ۲→2, ۳→3, ۴→4, ۵→5, ۶→6, ۷→7, ۸→8, ۹→9

═══════════════════════════════════════════════════════════════
NULL OVER GUESS — FUNDAMENTAL RULE
═══════════════════════════════════════════════════════════════

For EVERY field on the B-form:

- If the cell is clearly visible → extract the value exactly as printed.
- If the cell is partially visible but enough evidence supports a faithful reading → extract only what the document shows.
- If the cell is genuinely unreadable, ambiguous, cropped, obscured, smudged, torn, or absent on the form → set the value to null and its confidence to 0.

Do NOT, under any circumstances:
- guess a plausible value
- infer a name or CNIC from family relationships (father, mother, applicant, sibling)
- copy a value from another row, column, or document
- substitute a common Pakistani name when the cell is unclear
- reconstruct missing digits of a CNIC or registration number from pattern or context
- emit a value merely because the JSON schema expects one
- change one field's value to make it agree with another field

A valid-looking 13-digit CNIC is NOT evidence that the digits are correct. A common Pakistani name is NOT evidence that the cell was read correctly. When in doubt, abstain: null + confidence 0. The FSO will re-read the cell manually.

Minor transliteration variation (e.g. "Ahmed" vs "Ahmad", "Ishtiaq" vs "Ishtiaque") is acceptable and should NOT be nulled — null only applies when the source cell itself does not support a faithful reading.

═══════════════════════════════════════════════════════════════
STEP 1 — TOP SECTION (above the table)
═══════════════════════════════════════════════════════════════

Extract from the form header:
- crc_number: The CRC/form registration number at the top. If not visible or unreadable, set to null with confidence 0; do not guess or reconstruct digits.
- applicant_name: From field labeled "درخواست دہندہ کا نام" (Applicant's Name). Copy exactly as printed; do not infer the applicant's relationship to the child. If the cell is unreadable, set to null with confidence 0.
- applicant_cnic_number: From field labeled "درخواست دہندہ کا شناختی کارڈ نمبر". Preserve dashes: 00000-0000000-0. If the digits are unclear or the field is absent, set to null with confidence 0; do not reconstruct missing digits from father_cnic_number or any other CNIC.

APPLICANT vs. FATHER — SEPARATE FIELDS:
- applicant_cnic_number = the CNIC printed next to the "applicant / درخواست دہندہ" label on the form header.
- father_cnic_number = the father's CNIC printed in the table column whose header reads "والد کا نام اور شناختی کارڈ نمبر" (the header containing والد = father, ending in د).
- These are NOT assumed to be the same person. The applicant is often the father, but may also be the mother (e.g. when the father is deceased) or another guardian. Do NOT infer the applicant's identity from family relationship.
- Extract each field exactly as printed under its own label. If they happen to match, emit them both. If they differ, emit them both unchanged — do NOT re-read one to make it agree with the other, do NOT copy the father's CNIC into the applicant slot, and do NOT copy the applicant's CNIC into the father slot.
- If the form header has NO visible applicant CNIC field, set applicant_cnic_number = null and confidence.applicant_cnic_number = 0. Do NOT fill it in from father_cnic_number.
- Include "_consistency_check": {{"applicant_cnic_matches_father_cnic": true/false/null (null if either value is missing), "applicant_cnic_read": "...", "father_cnic_read": "..."}} as a factual report of whether the two emitted values happen to agree — NOT as a signal that either value is wrong.

═══════════════════════════════════════════════════════════════
STEP 2 — TABLE COLUMNS (HEADER-KEYED, NOT POSITIONAL)
═══════════════════════════════════════════════════════════════

The B-form table has columns identified by their VISIBLE URDU HEADERS.

Do NOT assume:
- any left-to-right or right-to-left numbering
- any DOM/source order
- that column N means a specific field
- that the serial number column is the first one you should enumerate
- that neighboring columns reveal what an unreadable column is

Instead:
1. Visually locate EVERY column header on the table.
2. For EACH header, copy the Urdu text VERBATIM into "_raw_column_headers" as an array, listing them in the order you encountered them.
3. For EACH header, determine its semantic role by reading the header text itself:
   - Header containing "بچے کا نام" = child column (child_name + child_registration_number)
   - Header containing "والد کا نام" (ends with والد, no trailing ہ) = father column
   - Header containing "والدہ کا نام" (ends with والدہ, has trailing ہ) = mother column
   - Header containing "نمبر شمار" = serial number column
   - Header containing "جنس" or "رشتہ" = gender/relation column
   - Header containing "تاریخ پیدائش" = date of birth column
   - Header containing "معذوری" = remarks column
4. Report the mapping in "_header_mapping": {{ "<verbatim header>": "<semantic key>" }}.
   Valid semantic keys: serial, child, father, mother, gender_relation, date_of_birth, remarks.
5. If a header is unreadable, ambiguous, or does not match any known semantic key, set its mapping to "NEEDS_REVIEW". DO NOT assign it to a different field. DO NOT infer from neighboring columns. DO NOT fall back to position.
6. If TWO headers would map to the SAME semantic key, set BOTH to "NEEDS_REVIEW" (do not pick one).

Read actual label text — do NOT assume by position!

CRITICAL DISTINCTIONS:
- والد (Waalid) = Father — ends with د
- والدہ (Waalida) = Mother — ends with ہ (one more character)

STRUCTURAL SIGNALS (use as a sanity check, never as a substitute for the header text):
- The child-registration number is DIFFERENT per row.
- The father's CNIC is the SAME across all rows (repeated per child).
- The mother's CNIC is the SAME across all rows (repeated per child).
If the value patterns contradict your header reading, mark the column NEEDS_REVIEW rather than silently reassigning it.

═══════════════════════════════════════════════════════════════
STEP 3 — OUTPUT STRUCTURE (HEADER-KEYED)
═══════════════════════════════════════════════════════════════

Return ONLY valid JSON — no markdown, no explanation.

Structure (table data keyed by the VISIBLE URDU HEADER, not by column number):

{{
  "crc_number": "...",
  "applicant_name": "...",
  "applicant_cnic_number": "...",
  "table_headers": [
     "<header as you read it, verbatim>",
     "<header>", ...
  ],
  "table_rows": [
    {{
      "serial_number": <number or null>,
      "<verbatim header for child column>": {{
          "name": "...",
          "registration_number": "..."
      }},
      "<verbatim header for father column>": {{
          "name": "...",
          "cnic": "..."
      }},
      "<verbatim header for mother column>": {{
          "name": "...",
          "cnic": "..."
      }},
      "<verbatim header for gender column>": "...",
      "<verbatim header for DOB column>": "...",
      "<verbatim header for remarks column>": "..."
    }}
  ],
  "_raw_column_headers": ["<header1>", "<header2>", ...],
  "_header_mapping": {{
      "<header1>": "serial" | "child" | "father" | "mother" | "gender_relation" | "date_of_birth" | "remarks" | "NEEDS_REVIEW",
      "<header2>": "..."
  }},
  "_raw_father_name_urdu": "<verbatim Urdu text from the father column for row 1>",
  "_raw_mother_name_urdu": "<verbatim Urdu text from the mother column for row 1>",
  "_raw_child_names_urdu": ["<verbatim Urdu text from the child column for row 1>", ...],
  "_consistency_check": {{
      "applicant_cnic_matches_father_cnic": true | false | null,
      "applicant_cnic_read": "...",
      "father_cnic_read": "..."
  }},
  "confidence": {{
      "crc_number": 0-1,
      "applicant_name": 0-1,
      "applicant_cnic_number": 0-1,
      "father_name": 0-1,
      "father_cnic_number": 0-1,
      "mother_name": 0-1,
      "mother_cnic_number": 0-1,
      "children": [
         {{
            "serial_number": 0-1,
            "child_name": 0-1,
            "child_registration_number": 0-1,
            "gender_relation": 0-1,
            "date_of_birth": 0-1,
            "remarks": 0-1
         }}
      ]
  }}
}}

Rules for the header-keyed output:
- The keys inside each table_rows entry MUST be the VERBATIM Urdu header text as you read it on the form. Do NOT translate, transliterate, normalize, or reorder the header text.
- Each parent column value is an object {{name, cnic}}. The child column value is an object {{name, registration_number}}. Scalar columns (gender, DOB, remarks) are plain strings.
- Include the same name and CNIC values in BOTH places:
  * inside table_rows under the verbatim header key, AND
  * inside _raw_father_name_urdu / _raw_mother_name_urdu / _raw_child_names_urdu for forensic cross-check.
- Never reuse the same header text as a key for two different semantic roles.
- If the same semantic key would be needed for two different headers, set both to NEEDS_REVIEW in _header_mapping and set the corresponding name/cnic values to null with confidence 0.

═══════════════════════════════════════════════════════════════
NAME TRANSLITERATION (MANDATORY)
═══════════════════════════════════════════════════════════════

ALL name fields MUST be output in Roman/English script.
Read each Urdu letter carefully, then transliterate:

TRANSLITERATION GUIDANCE:
- Pakistani names typically consist of one or more given-name components, sometimes followed by a family name, title, or honorific suffix.
- Common structural patterns: single given name, two-word compound given name, given name + family name, given name + title/suffix.
- Common Urdu titles and suffixes include terms meaning lord, leader, lady, or religious honorifics. Transliterate these exactly as written — do not add or omit a component.
- Multiple Roman spellings may be acceptable for the same Urdu letters (e.g. variations in vowel representation). Use the spelling that most closely matches the visible letters.
- If a name component is a religious or honorific prefix, transliterate it as written — do not assume the rest of the name from the prefix alone.

If name is already in Roman/English, output exactly as shown.
NEVER output Urdu/Arabic script in any name field (except in the dedicated _raw_*_urdu fields).{target_instruction}"""

    return prompt
