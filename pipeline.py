import base64
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load from local file if it exists, otherwise rely on environment variables
_env_file = Path("API_Key.env")
if _env_file.exists():
    load_dotenv(str(_env_file))

# Initialize OpenAI client
client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("BASE_URL"),
)

# Load schema
schema = json.loads(Path("schema.json").read_text(encoding="utf-8"))

# Initialize SQLite database
db_path = Path("extractions.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS extractions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_type TEXT NOT NULL,
        extracted_json TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
""")
conn.commit()

MIME_MAP = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def build_bform_prompt(doc_schema: dict, target_child_serial_number: int | None) -> str:
    """Build specialized prompt for B-form extraction with Urdu label awareness."""
    
    target_instruction = ""
    if target_child_serial_number is not None:
        target_instruction = f"""

TARGET CHILD: serial_number = {target_child_serial_number}
- After extracting all children, find the child whose serial_number matches {target_child_serial_number}
- Set "is_target_child": true for that child, and "is_target_child": false for all others"""
    
    prompt = f"""You are a document data extraction assistant specializing in Pakistani B-form (CRC) documents.

═══════════════════════════════════════════════════════════════
STEP 1 — TOP SECTION (above the table)
═══════════════════════════════════════════════════════════════

Extract from the form header:
- crc_number: The CRC/form registration number at the top of the form.
- applicant_name: Read from the field labeled "درخواست دہندہ کا نام" (Applicant's Name). This is usually the father.
- applicant_cnic_number: Read from the field labeled "درخواست دہندہ کا شناختی کارڈ نمبر" (Applicant's CNIC Number). Preserve dashes: 00000-0000000-0.

INTERNAL CONSISTENCY CHECK:
- applicant_cnic_number MUST equal father_cnic_number (both are the father's CNIC).
- If they differ, re-read both values carefully and use the one from the table column for father_cnic_number and the one from the top header for applicant_cnic_number. Report both exactly as read.
- Include a field "_consistency_check" in your JSON output:
  {{"applicant_cnic_matches_father_cnic": true/false, "applicant_cnic_read": "...", "father_cnic_read": "..."}}

═══════════════════════════════════════════════════════════════
STEP 2 — TABLE COLUMNS (right-to-left, 7 columns)
═══════════════════════════════════════════════════════════════

The B-form table has exactly 7 columns in this right-to-left order:

| # | Urdu Header                              | Transliteration / Meaning                    | What to extract                          |
|---|------------------------------------------|----------------------------------------------|------------------------------------------|
| 1 | نمبر شمار                                 | Serial number                                | serial_number (row number)               |
| 2 | بچے کا نام اور رجسٹریشن نمبر              | Child's name & registration number           | child_name + child_registration_number   |
| 3 | والد کا نام اور شناختی کارڈ نمبر          | Father's name & CNIC                         | father_name + father_cnic_number         |
| 4 | والدہ کا نام اور شناختی کارڈ نمبر         | Mother's name & CNIC                         | mother_name + mother_cnic_number         |
| 5 | جنس/رشتہ                                 | Gender / relation                            | gender_relation (son/daughter)           |
| 6 | تاریخ پیدائش                              | Date of birth                                | date_of_birth (DD-MM-YYYY)              |
| 7 | معذوری                                   | Remarks / disability                          | remarks (usually empty)                  |

═══════════════════════════════════════════════════════════════
CRITICAL COLUMN DISAMBIGUATION RULES
═══════════════════════════════════════════════════════════════

RULE A — Column 2 (child registration number) vs Columns 3-4 (parent CNICs):
- Column 2 (بچے کا نام اور رجسٹریشن نمبر) contains a DIFFERENT number on every row — this is the child_registration_number.
- Column 3 (والد کا نام اور شناختی کارڈ نمبر) contains the SAME father's CNIC repeated on every row — this is father_cnic_number.
- Column 4 (والدہ کا نام اور شناختی کارڈ نمبر) contains the SAME mother's CNIC repeated on every row — this is mother_cnic_number.

RULE B — How to distinguish them:
- If a number is IDENTICAL across all rows → it is a parent CNIC (father or mother).
- If a number is DIFFERENT on each row → it is a child registration number.
- NEVER read father_cnic_number or mother_cnic_number from Column 2.

RULE C — Before extracting, verify by reading and reporting the exact Urdu label of each column header you are pulling from. In your JSON, include a "_column_headers_read" object:
{{
  "_column_headers_read": {{
    "col1": "<exact Urdu text you read for serial number column>",
    "col2": "<exact Urdu text you read for child name/registration column>",
    "col3": "<exact Urdu text you read for father name/CNIC column>",
    "col4": "<exact Urdu text you read for mother name/CNIC column>",
    "col5": "<exact Urdu text you read for gender column>",
    "col6": "<exact Urdu text you read for DOB column>",
    "col7": "<exact Urdu text you read for remarks column>"
  }}
}}

RULE D — والد vs والدہ:
- والد (Waalid) = Father — 5 characters
- والدہ (Waalida) = Mother — 6 characters (ہ at the end)
- These differ by only ONE character. Do NOT assume by position — read the actual label text.

═══════════════════════════════════════════════════════════════
STEP 3 — OUTPUT STRUCTURE
═══════════════════════════════════════════════════════════════

Return ONLY valid JSON — no markdown, no explanation, no extra text.
The JSON must match this exact structure:

{json.dumps(doc_schema, indent=2)}

Plus these diagnostic fields at the top level:
- "_column_headers_read": (object described in RULE C above)
- "_consistency_check": (object described in STEP 1 above)

IMPORTANT:
- Preserve all CNIC numbers with dashes: 00000-0000000-0
- If a field is not visible, use null and confidence 0
- Extract EVERY child row visible in the form
- Include confidence scores (0-1) for each field in the "confidence" object{target_instruction}"""
    
    return prompt


def extract_document(image_path: str | Path, document_type: str, target_child_serial_number: int | None = None) -> dict:
    """
    Extract structured data from a document image using Qwen-VL.
    
    Args:
        image_path: Path to the image file
        document_type: One of: mother_cnic, father_cnic, b_form, death_certificate, result_card
        target_child_serial_number: For b_form only — the row number (1, 2, 3...) to mark as is_target_child: true
    
    Returns:
        Extracted JSON matching the schema for the given document_type
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    if document_type not in schema:
        raise ValueError(f"Unknown document_type: {document_type}. Must be one of: {list(schema.keys())}")
    
    # Get schema section for this document type
    doc_schema = schema[document_type]
    
    # Encode image
    image_b64 = base64.b64encode(image_path.read_bytes()).decode()
    mime = MIME_MAP.get(image_path.suffix.lower(), "image/jpeg")
    
    # Build prompt
    if document_type == "b_form":
        prompt = build_bform_prompt(doc_schema, target_child_serial_number)
    else:
        schema_json = json.dumps(doc_schema, indent=2)
        prompt = f"""You are a document data extraction assistant.
Look at this {document_type.replace('_', ' ')} image and extract the required fields.
Return ONLY valid JSON — no markdown, no explanation, no extra text.

The JSON must match this exact structure with confidence scores (0-1) for each field:

{schema_json}

IMPORTANT: 
- Preserve CNIC/identity numbers exactly as printed with dashes in format: 00000-0000000-0
- Use the exact field names shown above
- Include a confidence score (0-1) for each extracted field in the "confidence" object
- If a field is not visible or readable, use null for the value and 0 for confidence
- For dates, use DD-MM-YYYY format as specified"""
    
    # Call API
    response = client.chat.completions.create(
        model="qwen-vl-max",
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
    
    # Parse response
    result_text = response.choices[0].message.content
    
    # Try to extract JSON if wrapped in markdown
    if "```json" in result_text:
        result_text = result_text.split("```json")[1].split("```")[0].strip()
    elif "```" in result_text:
        result_text = result_text.split("```")[1].split("```")[0].strip()
    
    try:
        result_json = json.loads(result_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from model response: {e}\nRaw response: {result_text}")
    
    # Save to database
    timestamp = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO extractions (document_type, extracted_json, timestamp) VALUES (?, ?, ?)",
        (document_type, json.dumps(result_json, ensure_ascii=False), timestamp)
    )
    conn.commit()
    
    return result_json


def get_all_extractions() -> list:
    """Retrieve all extractions from the database."""
    cursor.execute("SELECT document_type, extracted_json, timestamp FROM extractions ORDER BY id")
    rows = cursor.fetchall()
    return [
        {
            "document_type": row[0],
            "extracted_json": json.loads(row[1]),
            "timestamp": row[2]
        }
        for row in rows
    ]


if __name__ == "__main__":
    # Quick test
    print("Pipeline ready. Use extract_document(image_path, document_type) to extract data.")
