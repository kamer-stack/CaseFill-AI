"""Generate synthetic B-form HTML fixtures for Step-7 controlled VLM validation.

Each HTML file is a faithful right-to-left table mimicking a Pakistani B-form
(CRC) with seven Urdu-header columns and a three-row header block. The content
is entirely synthetic — no real personal data.

Run:
    venv/Scripts/python.exe tests/fixtures/synthetic_bforms/generate_html.py

This writes test_a.html ... test_f.html into the same directory.
"""

from __future__ import annotations
from pathlib import Path

OUT_DIR = Path(__file__).parent


URDU_HEADERS = [
    "نمبر شمار",                              # Col 1: serial number
    "بچے کا نام اور رجسٹریشن نمبر",           # Col 2: child name + reg#
    "والد کا نام اور شناختی کارڈ نمبر",       # Col 3: father name + CNIC
    "والدہ کا نام اور شناختی کارڈ نمبر",      # Col 4: mother name + CNIC
    "جنس / رشتہ",                             # Col 5: gender/relation
    "تاریخ پیدائش",                           # Col 6: DOB
    "معذوری",                                 # Col 7: remarks
]


CSS = """
* { box-sizing: border-box; }
body {
    margin: 0; padding: 40px;
    background: #fff;
    font-family: 'Noto Nastaliq Urdu', 'Jameel Noori Nastaleeq',
                 'Traditional Arabic', 'Arabic Typesetting',
                 'Segoe UI', Tahoma, sans-serif;
    color: #000;
}
.title {
    text-align: center;
    font-size: 28px;
    font-weight: bold;
    direction: rtl;
    margin-bottom: 24px;
    border-bottom: 2px solid #000;
    padding-bottom: 8px;
}
.subtitle {
    text-align: center;
    font-size: 16px;
    direction: rtl;
    color: #444;
    margin-bottom: 16px;
}
.header-block {
    direction: rtl;
    margin: 20px 0;
    font-size: 18px;
    border: 1px solid #000;
    padding: 12px;
    background: #fafafa;
}
.header-block .row {
    display: flex;
    gap: 30px;
    margin: 8px 0;
    flex-wrap: wrap;
}
.header-block .field {
    flex: 1;
    min-width: 300px;
}
.header-block .label {
    font-weight: bold;
    margin-left: 8px;
}
.header-block .value {
    border-bottom: 1px solid #888;
    padding: 2px 6px;
    display: inline-block;
    min-width: 200px;
}
table.bform {
    width: 100%;
    border-collapse: collapse;
    direction: rtl;
    margin-top: 20px;
    font-size: 16px;
}
table.bform th, table.bform td {
    border: 1px solid #000;
    padding: 10px 8px;
    vertical-align: top;
    text-align: right;
    direction: rtl;
}
table.bform th {
    background: #e8e8e8;
    font-weight: bold;
    font-size: 17px;
}
table.bform td {
    min-height: 50px;
    line-height: 1.6;
}
td.serial { text-align: center; font-weight: bold; font-size: 18px; }
td.child-cell .name, td.parent-cell .name {
    font-size: 17px;
    display: block;
    margin-bottom: 6px;
}
td.child-cell .reg, td.parent-cell .cnic {
    font-family: 'Courier New', monospace;
    font-size: 15px;
    color: #222;
    display: block;
    letter-spacing: 0.5px;
}
td.gender, td.dob, td.remarks {
    text-align: center;
    font-size: 15px;
}
.missing { color: #bbb; font-style: italic; }
.footer {
    margin-top: 24px;
    font-size: 12px;
    color: #666;
    text-align: center;
    direction: ltr;
}
"""


def html_for(spec: dict) -> str:
    """Render a complete B-form HTML page from a spec dict.

    spec keys:
        test_id, title_urdu, subtitle,
        crc_number, applicant_name_urdu, applicant_cnic,
        children: [{serial, child_name_urdu, child_reg,
                    father_name_urdu, father_cnic,
                    mother_name_urdu, mother_cnic,
                    gender_urdu, dob, remarks}],
        notes (optional footer note)
    """
    header = f"""
<!DOCTYPE html>
<html lang="ur" dir="rtl">
<head>
<meta charset="utf-8">
<title>B-form synthetic - {spec['test_id']}</title>
<style>{CSS}</style>
</head>
<body>
<div class="title">{spec['title_urdu']}</div>
<div class="subtitle">{spec['subtitle']}</div>

<div class="header-block">
  <div class="row">
    <div class="field">
      <span class="label">نمبر رجسٹریشن / CRC:</span>
      <span class="value" style="font-family: monospace;">{spec['crc_number']}</span>
    </div>
  </div>
  <div class="row">
    <div class="field">
      <span class="label">درخواست دہندہ کا نام:</span>
      <span class="value">{spec['applicant_name_urdu']}</span>
    </div>
    <div class="field">
      <span class="label">درخواست دہندہ کا شناختی کارڈ نمبر:</span>
      <span class="value" style="font-family: monospace;">{spec['applicant_cnic']}</span>
    </div>
  </div>
</div>

<table class="bform">
<thead>
<tr>
"""
    cols = "".join(f"<th>{h}</th>" for h in URDU_HEADERS)
    body_rows = []
    for c in spec["children"]:
        child_cell = (
            f'<span class="name">{c["child_name_urdu"]}</span>'
            f'<span class="reg">{c["child_reg"]}</span>'
        )
        father_cell = (
            f'<span class="name">{c["father_name_urdu"]}</span>'
            f'<span class="cnic">{c["father_cnic"]}</span>'
        )
        mother_cell = (
            f'<span class="name">{c["mother_name_urdu"]}</span>'
            f'<span class="cnic">{c["mother_cnic"]}</span>'
        )
        remarks = c.get("remarks") or '<span class="missing">—</span>'
        body_rows.append(
            f'<tr>'
            f'<td class="serial">{c["serial"]}</td>'
            f'<td class="child-cell">{child_cell}</td>'
            f'<td class="parent-cell">{father_cell}</td>'
            f'<td class="parent-cell">{mother_cell}</td>'
            f'<td class="gender">{c["gender_urdu"]}</td>'
            f'<td class="dob">{c["dob"]}</td>'
            f'<td class="remarks">{remarks}</td>'
            f'</tr>'
        )
    footer_note = spec.get("notes", f"Synthetic test {spec['test_id']} — not a real document.")
    return (
        header + cols + "</thead><tbody>" + "".join(body_rows) +
        "</tbody></table>"
        f'<div class="footer">{footer_note}</div>'
        "</body></html>"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic test data — all identities are fictional.
# CNICs use prefix 99xxx (reserved here as clearly-synthetic marker).
# ─────────────────────────────────────────────────────────────────────────────


TEST_A = {
    "test_id": "A",
    "title_urdu": "فارم ب — مصنوعی دستاویز الف",
    "subtitle": "Synthetic B-form — Test A: all identities distinct",
    "crc_number": "99-TEST-A-2024",
    "applicant_name_urdu": "شفیق الرحمن صدیقی",        # Shafiq-ur-Rehan Siddiqui
    "applicant_cnic": "99101-7111111-1",
    "children": [
        {
            "serial": 1,
            "child_name_urdu": "عمران شفیق",            # Imran Shafiq
            "child_reg": "99-2024-111111",
            "father_name_urdu": "شفیق الرحمن صدیقی",    # = applicant
            "father_cnic": "99101-7111111-1",
            "mother_name_urdu": "زرقونہ شفیق",          # Zarghuna Shafiq (distinct)
            "mother_cnic": "99102-8222222-2",
            "gender_urdu": "بیٹا",
            "dob": "15-03-2018",
            "remarks": "",
        },
    ],
}


TEST_B = {
    "test_id": "B",
    "title_urdu": "فارم ب — مصنوعی دستاویز ب",
    "subtitle": "Synthetic B-form — Test B: applicant == father (legitimately same)",
    "crc_number": "99-TEST-B-2024",
    "applicant_name_urdu": "برکت علی ہاشمی",           # Barkat Ali Hashmi
    "applicant_cnic": "99201-7333333-3",
    "children": [
        {
            "serial": 1,
            "child_name_urdu": "سعد برکت",              # Saad Barkat
            "child_reg": "99-2024-333333",
            "father_name_urdu": "برکت علی ہاشمی",       # identical to applicant
            "father_cnic": "99201-7333333-3",           # identical to applicant CNIC
            "mother_name_urdu": "حوریاں برکت",          # Hoorain Barkat
            "mother_cnic": "99202-8444444-4",
            "gender_urdu": "بیٹا",
            "dob": "22-07-2019",
            "remarks": "",
        },
    ],
}


TEST_C = {
    "test_id": "C",
    "title_urdu": "فارم ب — مصنوعی دستاویز ج",
    "subtitle": "Synthetic B-form — Test C: applicant != father (e.g. mother is applicant)",
    "crc_number": "99-TEST-C-2024",
    # Applicant = mother of the child (father absent/deceased scenario)
    "applicant_name_urdu": "مہ جبین پرواز",            # Mahjabeen Parwaz (the mother)
    "applicant_cnic": "99301-8555555-5",                # mother's CNIC as applicant
    "children": [
        {
            "serial": 1,
            "child_name_urdu": "یاسر پرواز",            # Yasir Parwaz
            "child_reg": "99-2024-555555",
            "father_name_urdu": "پرواز حسین شاہ",       # Parwaz Hussain Shah (different person)
            "father_cnic": "99302-7666666-6",
            "mother_name_urdu": "مہ جبین پرواز",        # same as applicant (mother)
            "mother_cnic": "99301-8555555-5",
            "gender_urdu": "بیٹا",
            "dob": "10-11-2020",
            "remarks": "",
        },
    ],
}


TEST_D = {
    "test_id": "D",
    "title_urdu": "فارم ب — مصنوعی دستاویز د",
    "subtitle": "Synthetic B-form — Test D: father/mother names look similar in Urdu",
    "crc_number": "99-TEST-D-2024",
    "applicant_name_urdu": "عبد القادر مہمند",         # Abdul Qadir Mohmand
    "applicant_cnic": "99401-7777777-7",
    "children": [
        {
            "serial": 1,
            "child_name_urdu": "حماد عبد القادر",       # Hammad Abdul Qadir
            "child_reg": "99-2024-777777",
            # Father and mother names share structure but are clearly different:
            "father_name_urdu": "عبد القادر مہمند",     # Abdul Qadir Mohmand
            "father_cnic": "99401-7777777-7",
            "mother_name_urdu": "عبدہ القادر مہمند",    # Abda Al-Qadir Mohmand (deliberately similar)
            "mother_cnic": "99402-8888888-8",
            "gender_urdu": "بیٹا",
            "dob": "05-02-2017",
            "remarks": "",
        },
    ],
}


TEST_E = {
    "test_id": "E",
    "title_urdu": "فارم ب — مصنوعی دستاویز ہ",
    "subtitle": "Synthetic B-form — Test E: mother name cell intentionally left empty",
    "crc_number": "99-TEST-E-2024",
    "applicant_name_urdu": "فضل کریم اعوان",           # Fazal Karim Awan
    "applicant_cnic": "99501-7999999-9",
    "children": [
        {
            "serial": 1,
            "child_name_urdu": "نبیل فضل",              # Nabeel Fazal
            "child_reg": "99-2024-999999",
            "father_name_urdu": "فضل کریم اعوان",
            "father_cnic": "99501-7999999-9",
            # Mother cell deliberately blank — model should emit null, NOT invent a name
            "mother_name_urdu": "",
            "mother_cnic": "",
            "gender_urdu": "بیٹا",
            "dob": "28-09-2021",
            "remarks": "",
        },
    ],
    "notes": (
        "Synthetic test E — the mother cell (column 4) is intentionally empty. "
        "Correct extraction: mother_name=null, mother_cnic_number=null, confidences=0."
    ),
}


TEST_F = {
    "test_id": "F",
    "title_urdu": "فارم ب — مصنوعی دستاویز و",
    "subtitle": "Synthetic B-form — Test F: structural mirror of historical failure (3 children)",
    "crc_number": "99-TEST-F-2024",
    "applicant_name_urdu": "احتشام احمد مگھر",         # Ihtisham Ahmed Maghar
    "applicant_cnic": "99601-7101010-1",
    "children": [
        {
            "serial": 1,
            "child_name_urdu": "ریحان احتشام",          # Rehan Ihtisham
            "child_reg": "99-2024-101010",
            "father_name_urdu": "احتشام احمد مگھر",
            "father_cnic": "99601-7101010-1",
            "mother_name_urdu": "رمضانہ احتشام",        # Ramzana Ihtisham
            "mother_cnic": "99602-8202020-2",
            "gender_urdu": "بیٹا",
            "dob": "12-04-2016",
            "remarks": "",
        },
        {
            "serial": 2,
            "child_name_urdu": "عائشہ احتشام",          # Aisha Ihtisham — intentionally uses
            # a common Pakistani name as the REAL cell value, to see if model reads it
            # faithfully rather than substituting a different common name.
            "child_reg": "99-2024-303030",
            "father_name_urdu": "احتشام احمد مگھر",
            "father_cnic": "99601-7101010-1",
            "mother_name_urdu": "رمضانہ احتشام",
            "mother_cnic": "99602-8202020-2",
            "gender_urdu": "بیٹی",
            "dob": "08-01-2019",
            "remarks": "",
        },
        {
            "serial": 3,
            "child_name_urdu": "زیاد احتشام",           # Ziyad Ihtisham
            "child_reg": "99-2024-505050",
            "father_name_urdu": "احتشام احمد مگھر",
            "father_cnic": "99601-7101010-1",
            "mother_name_urdu": "رمضانہ احتشام",
            "mother_cnic": "99602-8202020-2",
            "gender_urdu": "بیٹا",
            "dob": "30-06-2022",
            "remarks": "",
        },
    ],
}


SPECS = [TEST_A, TEST_B, TEST_C, TEST_D, TEST_E, TEST_F]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for spec in SPECS:
        path = OUT_DIR / f"test_{spec['test_id'].lower()}.html"
        path.write_text(html_for(spec), encoding="utf-8")
        print(f"wrote {path.name}  ({len(html_for(spec))} bytes)")


if __name__ == "__main__":
    main()
