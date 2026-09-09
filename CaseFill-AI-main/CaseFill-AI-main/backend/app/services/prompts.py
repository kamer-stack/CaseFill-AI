"""
Extraction prompts for Qwen-VL document processing.
Ported verbatim from the original prototype's pipeline.py build_bform_prompt().
"""

import json


def build_bform_prompt(doc_schema: dict, target_child_serial_number: int | None) -> str:
    """Build specialized prompt for B-form extraction with enhanced Urdu reading guidance."""

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
- father_cnic_number = the father's CNIC printed in Column 3 (والد کا نام اور شناختی کارڈ نمبر) of the table.
- These are NOT assumed to be the same person. The applicant is often the father, but may also be the mother (e.g. when the father is deceased) or another guardian. Do NOT infer the applicant's identity from family relationship.
- Extract each field exactly as printed under its own label. If they happen to match, emit them both. If they differ, emit them both unchanged — do NOT re-read one to make it agree with the other, do NOT copy the father's CNIC into the applicant slot, and do NOT copy the applicant's CNIC into the father slot.
- If the form header has NO visible applicant CNIC field, set applicant_cnic_number = null and confidence.applicant_cnic_number = 0. Do NOT fill it in from father_cnic_number.
- Include "_consistency_check": {{"applicant_cnic_matches_father_cnic": true/false/null (null if either value is missing), "applicant_cnic_read": "...", "father_cnic_read": "..."}} as a factual report of whether the two emitted values happen to agree — NOT as a signal that either value is wrong.

═══════════════════════════════════════════════════════════════
STEP 2 — TABLE COLUMNS (right-to-left, 7 columns)
═══════════════════════════════════════════════════════════════

The B-form table has 7 columns in right-to-left order:

| # | Urdu Header                        | Meaning                    | Extract                                |
|---|------------------------------------|----------------------------|----------------------------------------|
| 1 | نمبر شمار                           | Serial number              | serial_number (row number)             |
| 2 | بچے کا نام اور رجسٹریشن نمبر        | Child name + registration  | child_name + child_registration_number |
| 3 | والد کا نام اور شناختی کارڈ نمبر    | Father name + CNIC         | father_name + father_cnic_number       |
| 4 | والدہ کا نام اور شناختی کارڈ نمبر   | Mother name + CNIC         | mother_name + mother_cnic_number       |
| 5 | جنس/رشتہ                           | Gender/relation            | gender_relation (son/daughter)         |
| 6 | تاریخ پیدائش                        | Date of birth              | date_of_birth (DD-MM-YYYY)            |
| 7 | معذوری                             | Remarks/disability         | remarks (usually empty)                |

═══════════════════════════════════════════════════════════════
CRITICAL COLUMN DISAMBIGUATION
═══════════════════════════════════════════════════════════════

RULE A — Column 2 vs Columns 3-4:
- Column 2 (بچے کا نام اور رجسٹریشن نمبر): DIFFERENT number each row = child_registration_number
- Column 3 (والد کا نام...): SAME father's CNIC repeated = father_cnic_number
- Column 4 (والدہ کا نام...): SAME mother's CNIC repeated = mother_cnic_number

RULE B — How to distinguish:
- IDENTICAL across all rows → parent CNIC
- DIFFERENT each row → child registration number
- NEVER read parent CNICs from Column 2

RULE C — Verify by reading exact Urdu column headers. Include "_column_headers_read" in output:
{{"col1": "<Urdu text>", "col2": "<Urdu text>", ...}}

RULE D — والد vs والدہ:
- والد (Waalid) = Father — ends with د
- والدہ (Waalida) = Mother — ends with ہ (ہ at the end, one more character)
- Read actual label text — do NOT assume by position!

RULE E — Mother's name (Column 4 header: والدہ کا نام و شناختی کارڈ):
- The mother's name sits in Column 4, ABOVE the mother's CNIC number, on the SAME row.
- COPY the name VERBATIM from that cell. Do NOT infer, construct, or substitute a name from any other part of the document.
- Transliterate the exact Urdu letters visible in the cell into Roman/English. Do NOT substitute any plausible, common, or familiar name that is not visibly supported by the letters in this cell.
- Output BOTH:
  * "mother_name": your Roman/English transliteration, AND
  * "_raw_mother_name_urdu": the exact Urdu letters as printed in the cell, copied character-for-character, no transliteration.
- If you cannot read the mother's name cell clearly, set mother_name = null, _raw_mother_name_urdu = null, confidence.mother_name = 0. Do NOT fill in a plausible-sounding name.

RULE E (father) — Father's name (Column 3 header: والد کا نام و شناختی کارڈ):
- The father's name sits in Column 3, ABOVE the father's CNIC number, on the SAME row.
- COPY the name VERBATIM from that cell. Do NOT infer, construct, or substitute a name from any other part of the document, from memory, or from common-name lists.
- Transliterate the exact Urdu letters visible in the cell into Roman/English. Do NOT substitute any plausible, common, or familiar name that is not visibly supported by the letters in this cell. Never emit a name from memory or world knowledge unless you actually read those exact letters in this cell.
- Output BOTH:
  * "father_name": your Roman/English transliteration, AND
  * "_raw_father_name_urdu": the exact Urdu letters as printed in the cell, copied character-for-character, no transliteration.
- If you cannot read the father's name cell clearly, set father_name = null, _raw_father_name_urdu = null, confidence.father_name = 0. Do NOT fill in a plausible-sounding name.

RULE F — Child name per row (Column 2 header: بچے کا نام اور رجسٹریشن نمبر):
- For EACH row of the table, read the child's name from Column 2 OF THAT ROW ONLY, tied to that row's serial_number (Column 1).
- Do NOT copy a name from a different row, from the mother cell, or from memory. Real siblings have DISTINCT names — if two rows would produce identical child_name values, you have misread one of them; re-read both cells carefully.
- If the child's name cell for a specific row is genuinely unreadable, set that row's child_name = null, append null to _raw_child_names_urdu for that row, and set its confidence to 0. Do NOT substitute a plausible sibling name.
- Output BOTH per child:
  * "child_name": Roman/English transliteration for that row (or null), AND
  * append to "_raw_child_names_urdu" (an array, one entry per row, in serial_number order) the exact Urdu letters as printed in that cell (or null if unreadable).
- Never reuse the same transliterated name for two different serial numbers without re-reading the cells.

RULE G — Child registration number source:
- child_registration_number comes from Column 2 ONLY — the same cell as the child's name, typically printed BELOW or BESIDE the name.
- NEVER read child_registration_number from Column 3 (father CNIC) or Column 4 (mother CNIC), even if a CNIC-formatted number appears there.
- Sanity check before emitting: if a child's child_registration_number equals the father_cnic_number or mother_cnic_number, you have read the wrong column — re-read Column 2 for that row.
- child_registration_number is DIFFERENT per row (Rule B). A valid CNIC repeated across rows belongs in the parent slot, not the child slot.
- If the registration number in Column 2 for a specific row is genuinely unreadable, set that row's child_registration_number = null and its confidence to 0. Do NOT reconstruct missing digits from a parent CNIC, a sibling row, a pattern, or memory.

═══════════════════════════════════════════════════════════════
STEP 3 — OUTPUT STRUCTURE
═══════════════════════════════════════════════════════════════

Return ONLY valid JSON — no markdown, no explanation:

{json.dumps(doc_schema, indent=2)}

Plus diagnostic fields: "_column_headers_read", "_consistency_check", "_raw_father_name_urdu", "_raw_mother_name_urdu", "_raw_child_names_urdu"

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
NEVER output Urdu/Arabic script in any name field.{target_instruction}"""

    return prompt


def build_generic_prompt(doc_schema: dict, document_type: str) -> str:
    """Build a generic extraction prompt for non-B-form documents with enhanced Urdu reading."""
    schema_json = json.dumps(doc_schema, indent=2)

    # Document-specific Urdu field labels
    doc_specific_labels = {
        "death_certificate": """
COMMON URDU LABELS ON DEATH CERTIFICATES:
- سرٹیفکیٹ وفات / وفات نامہ = Death Certificate
- نام متوفی = Name of Deceased
- تاریخ وفات = Date of Death
- نام والد / نام شوہر = Father's/Husband's Name
- نمبر رجسٹریشن = Registration Number
- یونین کونسل = Union Council
- جاری کنندہ = Issuing Authority
""",
        "mother_cnic": """
COMMON URDU LABELS ON CNIC CARDS:
- قومی شناختی کارڈ = National Identity Card
- نام = Name
- نام والد / نام شوہر = Father's/Husband's Name
- شناختی کارڈ نمبر = CNIC Number
- تاریخ پیدائش = Date of Birth
- مستقل پتہ = Permanent Address
- جنس = Gender
- ملکیت = Citizenship
""",
        "father_cnic": """
COMMON URDU LABELS ON CNIC CARDS:
- قومی شناختی کارڈ = National Identity Card
- نام = Name
- نام والد = Father's Name
- شناختی کارڈ نمبر = CNIC Number
- تاریخ پیدائش = Date of Birth
- جنس = Gender
""",
        "result_card": """
COMMON URDU LABELS ON SCHOOL RESULT CARDS:
- نام طالب علم / نام شاگرد = Student Name
- نام والد = Father's Name
- جماعت / درجہ = Class/Grade
- حاصل کردہ نمبر = Marks Obtained
- کل نمبر = Total Marks
- فیصد = Percentage
- سال = Year
- اسکول کا نام = School Name
- بورڈ = Board
""",
        "child_picture": """
CHILD PHOTO QUALITY CHECK — DECISION CRITERIA (use exactly one):
- "clear": the child's face is visible and identifiable — facing the camera (front or near-front), unobstructed, and sharp enough to recognize the child.
- "blurry": the face is visible but out of focus, low-resolution, or motion-blurred.
- "face_not_visible": the face is turned away from the camera, covered, or cropped out of the frame — not enough of it is visible to identify the child.
The verdict MUST be consistent with your confidence score: if you can clearly see and identify the face, report "clear" with high confidence (0.9-1.0). Only report "blurry" or "face_not_visible" when your confidence in that assessment is genuinely low (below 0.7). Never report a negative verdict together with a high confidence score — that is a contradiction.
""",
    }

    doc_label_section = doc_specific_labels.get(document_type, "")

    return f"""You are a document data extraction assistant specializing in Pakistani official documents.
Your task is to accurately read and extract data from this {document_type.replace('_', ' ')} image.

═══════════════════════════════════════════════════════════════
URDU/NASTALIQ SCRIPT READING GUIDE (CRITICAL)
═══════════════════════════════════════════════════════════════

Pakistani documents use Urdu in NASTALIQ script which has these characteristics:
- Written RIGHT-TO-LEFT
- Letters are CURSIVE and CONNECTED (like Arabic but with a distinctive slanting/cascading style)
- Letters change shape based on position (initial, medial, final, isolated)

URDU ALPHABET KEY CHARACTERS:
ا (alif) - ب (be) - پ (pe) - ت (te) - ٹ (ṭe) - ث (se) - ج (jim) - چ (che)
ح (he) - خ (khe) - د (dal) - ڈ (ḍal) - ذ (zal) - ر (re) - ڑ (ṛe) - ز (ze)
ژ (zhe) - س (sin) - ش (shin) - ص (suad) - ض (zuad) - ط (toe) - ظ (zoe)
ع (ain) - غ (ghain) - ف (fe) - ق (qaf) - ک (kaf) - گ (gaf) - ل (lam)
م (mim) - ن (noon) - ں (noon ghunna) - و (waw) - ہ (gol hay) - ھ (do-chashmi hay)
ی (choti ye) - ے (bari ye) - ء (hamza)

CRITICAL DISTINCTIONS (commonly confused):
- ہ (gol hay - round) vs ھ (do-chashmi hay - two dots above)
- ن (noon - with dot) vs ں (noon ghunna - no dot, small v above)
- ی (choti ye - two dots below) vs ے (bari ye - no dots, curved tail)
- ک (kaf) vs گ (gaf - has extra stroke)
- ڈ (ḍal - has small mark above) vs د (dal - plain)

EASTERN ARABIC NUMERALS:
Urdu documents use these numerals: ۰ ۱ ۲ ۳ ۴ ۵ ۶ ۷ ۸ ۹
Convert to Western: ۰→0, ۱→1, ۲→2, ۳→3, ۴→4, ۵→5, ۶→6, ۷→7, ۸→8, ۹→9
CNIC format: ۳۵۲۰۱-۱۲۳۴۵۶۷-۱ becomes 35201-1234567-1
{doc_label_section}
═══════════════════════════════════════════════════════════════
EXTRACTION INSTRUCTIONS
═══════════════════════════════════════════════════════════════

1. FIRST: Scan the entire document to identify all text regions (both Urdu and English)
2. READ URDU TEXT: Carefully read each Urdu word letter-by-letter using the alphabet guide above
3. TRANSLITERATE NAMES: Convert Urdu names to standard Roman/English spelling
4. CONVERT NUMBERS: Convert Eastern Arabic numerals to Western digits
5. OUTPUT JSON: Return only valid JSON matching the schema below

Return ONLY valid JSON — no markdown, no explanation, no extra text.

JSON Schema:
{schema_json}

═══════════════════════════════════════════════════════════════
NAME TRANSLITERATION RULES
═══════════════════════════════════════════════════════════════

ALL name fields MUST be output in Roman/English (Latin) script.
Read each Urdu letter carefully, then transliterate:

COMMON PAKISTANI NAMES (for reference):
Male: Muhammad/Mohammad (محمد), Ahmed/Ahmad (احمد), Ali (علی), Khan (خان),
      Hussain (حسین), Hassan (حسن), Abdullah (عبداللہ), Ibrahim (ابراہیم),
      Imran (عمران), Tariq (طارق), Nasir (ناصر), Rashid (راشد), Zahid (زاہد)
Female: Fatima (فاطمہ), Ayesha (عائشہ), Zainab (زینب), Bano (بانو),
        Bibi (بی بی), Begum (بیگم), Naseem (نسیم), Nasreen (نسرین)

Examples:
- "نصیرہ بانو" → "Naseera Bano"
- "محمد ابراہیم" → "Muhammad Ibrahim"
- "فاطمہ زہرا" → "Fatima Zahra"
- "عبد الرزاق" → "Abdul Razzaq"

If a name is already in Roman/English, output it exactly as shown.
NEVER output Urdu/Arabic script in any name field.

═══════════════════════════════════════════════════════════════
FINAL OUTPUT RULES
═══════════════════════════════════════════════════════════════

- Preserve CNIC numbers with dashes: 00000-0000000-0
- Include confidence scores (0-1) for each field
- If a field is not visible, use null and confidence 0
- For dates, use DD-MM-YYYY format"""


# Routing prompt for address → region classification
def build_routing_prompt(address: str, region_summaries: str) -> str:
    """Build prompt for AI-based geographic routing."""
    return f"""You are an automated geographic routing assistant for the Orphan Family Support Program (OFSP).
Analyze this address:
"{address}"

Compare it against the official operational regions:
{region_summaries}

Rules:
1. If the address clearly belongs to or is within one of these region clusters or their surrounding districts, return that region's ID with high confidence (0.85 - 0.99).
2. If the address is ambiguous, vague (e.g. "Chak 48 near canal" with no city), or does not match any operational region, return matchedRegionId as null and confidence <= 0.3.
3. Return strict JSON ONLY matching this schema:
{{
  "matchedRegionId": string | null,
  "confidence": number,
  "detectedCityOrDistrict": string,
  "reasoning": string
}}"""


## Help chatbot system instruction
HELP_SYSTEM_PROMPT = """You are the AI Help Assistant for CaseFill-AI (Orphan Family Support Program).

CONFIDENTIALITY — NEVER disclose: API keys, model names, database structure, server details, source code, passwords, or internal architecture. If asked, say: "That information is confidential."

RESPONSE STYLE:
- Be BRIEF and DIRECT — answer in 1-3 sentences maximum
- No lengthy explanations unless absolutely necessary
- No bullet points or headers for simple questions
- Answer only what is asked — do not add extra information
- If user asks in Urdu, reply in Urdu. If in English, reply in English.

KEY KNOWLEDGE:
- No self-registration: there is NO Sign Up. Family accounts are registered in person by a Field Support Officer; FSO/Admin accounts are provisioned by Central Admin. Families cannot create accounts, cases, or upload documents themselves — they only track case status.
- Child logins: after an FSO verifies a case, the FSO can generate a read-only child login. The username is the child's B-Form/CNIC registration number (never chosen). Child logins are strictly read-only — no upload, no editing.
- Donor status & aid transfers: on Verified cases only the FSO can toggle donor_arranged and add aid transfer entries (date + amount). The child's profile shows these read-only.
- FSO accounts are created and deleted only by Central Admin. A case an FSO submits appears instantly in that FSO's own queue and in the Admin dashboard, attributed to the submitting FSO.
- 8 required documents: Child Photo, School Result Card, B-Form (CRC), Death Certificate, Mother's CNIC, Father's CNIC, Residential Address, Mother's Education Level
- Before submission, the FSO can delete and re-upload any document image and manually correct any AI-extracted field
- Case statuses: draft, pending_verification, unassigned, flagged, verified, rejected
- Cross-check statuses: MATCH (green), SIMILAR (yellow), MISMATCH (red), NEEDS_REVIEW (orange)
- User roles: Family (view status), FSO (intake + verification), Admin (manage all)
- B-Form has 7 columns with Urdu headers — system auto-transliterates names to English
- Cases are auto-routed to regions based on address; unassigned if ambiguous

If unsure, say: "Please contact the program office for assistance."
"""
