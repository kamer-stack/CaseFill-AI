"""
Text-structuring prompts for the OCR.space -> Qwen-plus path.

OCR.space returns raw text, not structured JSON. These prompts ask
Qwen-plus (TEXT model, no image) to turn that raw text into the exact
same JSON shapes the rest of the pipeline already expects:
  - B-form -> the header-keyed shape consumed by
    header_mapping.adapt_header_keyed_to_canonical()
  - CNIC -> the flat schema in extraction_schemas.json (mother_cnic /
    father_cnic), consumed by postprocess_cnic() / validate_extraction()

Both carry the same NULL OVER GUESS discipline as the vision prompts, with
one addition specific to this path: the model is working from OCR TEXT,
not the original image, so it cannot resolve anything the OCR itself
garbled. When OCR noise (dropped characters, merged words, broken table
alignment) makes a field ambiguous, the correct move is null + confidence
0 — never "cleaning up" the OCR text based on what a name/CNIC "should"
look like.
"""

from __future__ import annotations

_TEXT_SOURCE_CAVEAT = """
═══════════════════════════════════════════════════════════════
IMPORTANT — YOU ARE READING OCR TEXT, NOT THE ORIGINAL IMAGE
═══════════════════════════════════════════════════════════════

The text below was extracted by an OCR engine from a photographed Urdu
document. You do NOT have access to the original image. This means:

- Table structure may be flattened or reordered — rows/columns that were
  visually separated may now appear as adjacent lines or run together.
- The OCR itself may have dropped, merged, or corrupted characters.
- You cannot verify a reading against the visual layout the way a vision
  model could.

Given this, NULL OVER GUESS applies even more strictly here:
- If a value's placement in the text is ambiguous (e.g. you cannot tell
  which line belongs to which table column), set it to null with
  confidence 0 rather than guessing based on typical form layout.
- If OCR noise makes a name or number look "almost right" for a common
  Pakistani name/CNIC pattern, do NOT correct it to the common pattern.
  Extract exactly what the OCR text shows, or null it if unreadable.
- Never invent a table row, column, or field that isn't clearly present
  in the text.
"""


def build_bform_text_structuring_prompt(raw_ocr_text: str, target_child_serial_number: int | None) -> str:
    """
    Build the Qwen-plus prompt that structures OCR.space's raw B-form text
    into the SAME header-keyed JSON shape as prompts_header_keyed.py's
    vision prompt, so header_mapping.adapt_header_keyed_to_canonical()
    (including its majority-vote father/mother resolution) works unchanged.
    """
    target_instruction = ""
    if target_child_serial_number is not None:
        target_instruction = f"""

TARGET CHILD: serial_number = {target_child_serial_number}
- After extracting all children, find the child whose serial_number matches {target_child_serial_number}
- Set "is_target_child": true for that child, and "is_target_child": false for all others"""

    return f"""You are a document data extraction assistant. You will structure OCR-extracted
text from a Pakistani B-form (CRC — Child Registration Certificate) into JSON.
The original document is primarily in URDU.
{_TEXT_SOURCE_CAVEAT}
═══════════════════════════════════════════════════════════════
NULL OVER GUESS — FUNDAMENTAL RULE
═══════════════════════════════════════════════════════════════

For EVERY field:
- If the OCR text clearly supports a value → extract it exactly as shown.
- If the OCR text is garbled, ambiguous, or the field isn't present → null, confidence 0.

Do NOT, under any circumstances:
- guess a plausible value
- infer a name or CNIC from family relationships (father, mother, applicant, sibling)
- copy a value from another row, column, or document
- substitute a common Pakistani name when the text is unclear
- reconstruct missing digits of a CNIC or registration number from pattern or context
- emit a value merely because the JSON schema expects one

═══════════════════════════════════════════════════════════════
TABLE STRUCTURE (HEADER-KEYED)
═══════════════════════════════════════════════════════════════

The B-form has a table with these possible column headers (read the actual
text to find which ones are present and in what form the OCR rendered them):
- نمبر شمار (serial number)
- بچے کا نام اور رجسٹریشن نمبر (child name + registration number)
- والد کا نام اور شناختی کارڈ نمبر (father name + CNIC — ends in والد, no trailing ہ)
- والدہ کا نام اور شناختی کارڈ نمبر (mother name + CNIC — ends in والدہ, trailing ہ)
- جنس / رشتہ (gender/relation)
- تاریخ پیدائش (date of birth)
- معذوری (remarks)

STRUCTURAL SIGNALS (sanity check only, never a substitute for reading the text):
- The father's CNIC and mother's CNIC repeat identically across every child row.
- The child's registration number differs per row.

═══════════════════════════════════════════════════════════════
CHILD vs MOTHER — DO NOT CONFUSE (most common failure mode)
═══════════════════════════════════════════════════════════════

Child, father, and mother columns all look structurally identical in flattened
OCR text: each is just "a name followed by a number." This is exactly why they
get swapped — and on a form with only ONE child row, there is no cross-row
pattern to lean on, so the ONLY reliable anchor is the header label itself.

- The header label immediately governs what follows it. Text that comes after
  بچے کا نام اور رجسٹریشن نمبر (child name + registration) is the CHILD's,
  full stop — regardless of whether that name looks similar to, or sits near,
  the mother's or applicant's name elsewhere in the text.
- Text that comes after والدہ کا نام اور شناختی کارڈ نمبر (mother name + CNIC)
  is the MOTHER's — never copy it into the child slot even if the mother is
  also the applicant and her name/CNIC legitimately repeats elsewhere in the
  document (applicant section, etc.). Each label's own following text is the
  only valid source for that label's fields.
- Do NOT let a name matching the applicant's or mother's name elsewhere in the
  document cause you to substitute the mother's CNIC for the child's
  registration number, or vice versa. A shared name is normal (a mother can
  be the applicant); it is never a reason to swap in a different field's
  number.
- Only when there are 2+ child rows, use this as an extra check: a number
  that repeats identically across every row is a parent's, one that differs
  per row is the child's. This confirms the header-based reading above — it
  does not override it, and it does not apply at all to single-row forms.
- If the header label's own following text is genuinely absent or unreadable
  for a field, set it null with confidence 0 — do NOT fill it from a
  different label's text just because a value is expected there.

FATHER CNIC — DO NOT SKIP:
- Each father/mother table cell contains TWO lines of text: the name, then the CNIC number below it. Extract BOTH into the cell's "name" and "cnic" keys.
- The father cell is read with the exact same care as the mother cell. If you can find and extract the mother's CNIC digits from her cell, apply that same effort to the father's cell — do not leave "cnic" empty for father while filling it for mother.
- Only leave a cell's "cnic" null if the OCR text genuinely contains no legible number for that cell — never because the name line was the only part you looked at.

═══════════════════════════════════════════════════════════════
FATHER vs MOTHER — WALID vs WALIDAH (character-level check, not optional)
═══════════════════════════════════════════════════════════════

The single most common column-swap in this document is father's name/CNIC
landing in the mother's fields, or vice versa, or both ending up copied into
the applicant. The header words look almost identical — check them letter
by letter every time, using this exact breakdown:

- والد (WALID = father) is FOUR letters: و ا ل د — it ends in د (daal).
  Example header: والد کا نام اور شناختی کارڈ نمبر
- والدہ (WALIDAH = mother) is FIVE letters: و ا ل د ہ — it has ONE extra
  letter, ہ (heh), at the end. Example header: والدہ کا نام اور شناختی کارڈ نمبر
- If OCR renders the header without a clear trailing ہ → treat it as والد
  (father). If OCR renders it WITH a trailing ہ → treat it as والدہ (mother).
  This single extra letter is the ONLY reliable way to tell the two headers
  apart — they are otherwise identical. Do not guess from column position,
  row order, or which name "sounds like" a father's or mother's name.
- Do this check independently for EVERY occurrence of a والد/والدہ-rooted
  header in the text (top section, table header row) before assigning any
  name/CNIC pair to father_name/father_cnic or mother_name/mother_cnic.

KNOWN FAILURE MODES TO ACTIVELY AVOID:
- Father's name/CNIC ending up written into the mother_name/mother_cnic
  fields (or the reverse) — prevented by the letter-count check above.
- Mother's name/CNIC leaking into applicant_name/applicant_cnic_number just
  because the mother is often the applicant — the applicant fields come
  ONLY from the درخواست دہندہ label's own text (see next section), never
  copied from the mother cell even when the values would end up identical.
- Mother's own row cell being left null/empty while her data appears only
  under applicant — if the والدہ column itself has readable name/CNIC text,
  it MUST populate mother_name/mother_cnic_number directly, independent of
  whatever the applicant fields end up being.

Also extract from the top section (before the table):
- crc_number, applicant_name, applicant_cnic_number (label: درخواست دہندہ)

═══════════════════════════════════════════════════════════════
APPLICANT IS A SEPARATE FIELD — DO NOT COPY FROM FATHER/MOTHER
═══════════════════════════════════════════════════════════════

applicant_name and applicant_cnic_number come ONLY from the top-section
field labeled درخواست دہندہ (applicant). The applicant is OFTEN the mother
or father (e.g. the mother applies when the father is deceased), but this
is NOT guaranteed — read the applicant's own name/CNIC text independently
from wherever درخواست دہندہ appears in the OCR text.

Do NOT:
- assume the applicant is the mother (or father) and reuse that reading
- copy mother_name/mother_cnic_number or father_name/father_cnic_number
  into applicant_name/applicant_cnic_number just because they are likely
  the same person
- fill in the applicant fields when the درخواست دہندہ label itself is not
  present or its value is not clearly readable in the OCR text — null +
  confidence 0 instead

If the applicant's reading and a parent's reading turn out to be the same
value, that's fine — emit them both, independently arrived at. But if you
cannot find the درخواست دہندہ label's own text in the OCR output, do NOT
substitute a parent's name/CNIC as a stand-in.

═══════════════════════════════════════════════════════════════
NAME TRANSLITERATION (MANDATORY)
═══════════════════════════════════════════════════════════════
ALL name fields MUST be output in Roman/English script, transliterated from
the Urdu text. If a name is already in Roman script in the OCR text, output
it exactly as shown.

═══════════════════════════════════════════════════════════════
OUTPUT — return ONLY this JSON, no markdown, no explanation
═══════════════════════════════════════════════════════════════

{{
  "crc_number": "...",
  "applicant_name": "...",
  "applicant_cnic_number": "...",
  "table_headers": ["<verbatim header as seen in OCR text>", ...],
  "table_rows": [
    {{
      "serial_number": <number or null>,
      "<verbatim header for child column>": {{"name": "...", "registration_number": "..."}},
      "<verbatim header for father column>": {{"name": "...", "cnic": "..."}},
      "<verbatim header for mother column>": {{"name": "...", "cnic": "..."}},
      "<verbatim header for gender column>": "...",
      "<verbatim header for DOB column>": "...",
      "<verbatim header for remarks column>": "..."
    }}
  ],
  "_raw_column_headers": ["<header1>", ...],
  "_header_mapping": {{"<header1>": "serial" | "child" | "father" | "mother" | "gender_relation" | "date_of_birth" | "remarks" | "NEEDS_REVIEW"}},
  "_raw_father_name_urdu": "<verbatim Urdu text for father, row 1>",
  "_raw_mother_name_urdu": "<verbatim Urdu text for mother, row 1>",
  "_raw_child_names_urdu": ["<verbatim Urdu text for child, per row>"],
  "confidence": {{
    "crc_number": 0-1, "applicant_name": 0-1, "applicant_cnic_number": 0-1,
    "children": [{{"serial_number": 0-1, "child_name": 0-1, "child_registration_number": 0-1,
                   "gender_relation": 0-1, "date_of_birth": 0-1, "remarks": 0-1,
                   "father_name": 0-1, "father_cnic_number": 0-1,
                   "mother_name": 0-1, "mother_cnic_number": 0-1}}]
  }}
}}{target_instruction}

═══════════════════════════════════════════════════════════════
RAW OCR TEXT TO STRUCTURE
═══════════════════════════════════════════════════════════════

{raw_ocr_text}"""


def build_death_certificate_text_structuring_prompt(raw_ocr_text: str, doc_schema: dict) -> str:
    """
    Build the Qwen-plus prompt that structures OCR.space's raw English-OCR
    death certificate text into the flat schema in extraction_schemas.json,
    so validate_extraction() runs unchanged.
    """
    import json as _json
    schema_json = _json.dumps(doc_schema, indent=2, ensure_ascii=False)

    return f"""You are a document data extraction assistant. You will structure OCR-extracted
text from a Pakistani Death Registration Certificate into JSON. The certificate is
printed bilingually (English + Urdu); the OCR text below was extracted in English only.
{_TEXT_SOURCE_CAVEAT}
═══════════════════════════════════════════════════════════════
THIS DOCUMENT HAS THREE DIFFERENT NUMBERS — DO NOT CONFUSE THEM
═══════════════════════════════════════════════════════════════

A death certificate prints up to three distinct identifiers. Only ONE of
them is "registration_number" — the other two must NEVER be used for it:

- "Tracking Id" (a long numeric string, e.g. 91100012359161) — this is a
  system tracking ID, NOT the registration number. Do not use it.
- "CRMS No" (an alphanumeric code, e.g. D197413448) — this is the CRMS
  system's own reference number, NOT the registration number. Do not use it.
- "OLD/M REG #" — a short, often HANDWRITTEN number near the top of the
  certificate (e.g. a number like 874 written by hand, not printed). THIS
  is the correct value for registration_number.

If the OCR text does not clearly contain a value explicitly labeled
"OLD/M REG" (or a close OCR variant of that label), set registration_number
to null with confidence 0 — do NOT substitute the Tracking Id or CRMS No
just because a number is expected there.

═══════════════════════════════════════════════════════════════
NULL OVER GUESS
═══════════════════════════════════════════════════════════════
If the OCR text clearly supports a value, extract it exactly. If garbled,
ambiguous, or absent, set null with confidence 0. Do not guess, do not
reconstruct missing digits, do not substitute a common name.

Return ONLY this JSON schema, no markdown, no explanation:
{schema_json}

═══════════════════════════════════════════════════════════════
RAW OCR TEXT TO STRUCTURE
═══════════════════════════════════════════════════════════════

{raw_ocr_text}"""


def build_cnic_text_structuring_prompt(raw_ocr_text: str, doc_schema: dict) -> str:
    """
    Build the Qwen-plus prompt that structures OCR.space's raw old-format
    CNIC text into the same flat schema used by the existing Qwen-VL CNIC
    path (extraction_schemas.json), so postprocess_cnic() and
    validate_extraction() run unchanged.
    """
    import json as _json
    schema_json = _json.dumps(doc_schema, indent=2, ensure_ascii=False)

    return f"""You are a document data extraction assistant. You will structure OCR-extracted
text from a Pakistani CNIC (old format, no printed English field labels) into JSON.
{_TEXT_SOURCE_CAVEAT}
COMMON URDU LABELS ON OLD-FORMAT CNIC CARDS:
- قومی شناختی کارڈ = National Identity Card
- نام = Name
- نام والد / نام شوہر = Father's/Husband's Name
- شناختی کارڈ نمبر = CNIC Number (format: 00000-0000000-0)
- تاریخ پیدائش = Date of Birth
- مستقل پتہ = Permanent Address

═══════════════════════════════════════════════════════════════
NULL OVER GUESS
═══════════════════════════════════════════════════════════════
If the OCR text clearly supports a value, extract it exactly. If garbled,
ambiguous, or absent, set null with confidence 0. Do not guess, do not
reconstruct missing CNIC digits, do not substitute a common name.

ALL name fields MUST be transliterated to Roman/English script.

Return ONLY this JSON schema, no markdown, no explanation:
{schema_json}

═══════════════════════════════════════════════════════════════
RAW OCR TEXT TO STRUCTURE
═══════════════════════════════════════════════════════════════

{raw_ocr_text}"""