"""
Seed data for CaseFill-AI database.
Populates default regions, FSOs, admin, and demo family accounts.
"""

import json
import hashlib
import secrets
from datetime import datetime

from .db import get_db


def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """Hash a password using PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = secrets.token_hex(16)
    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 200000
    )
    return hash_bytes.hex(), salt


DEFAULT_REGIONS = [
    {
        "id": "region_multan",
        "name": "Multan & Punjab South",
        "urdu_name": "ملتان اور جنوبی پنجاب کلسٹر",
        "assigned_fso_id": "FSO-PK-782",
        "keywords": ["multan", "shujabad", "lodhran", "khanewal", "bahawalpur",
                      "muzaffargarh", "rahim yar khan", "dg khan", "dera ghazi khan",
                      "layyah", "vehari", "mian channu", "jalalpur"],
        "active": 1,
    },
    {
        "id": "region_rwp_isb",
        "name": "Rawalpindi & Islamabad",
        "urdu_name": "راولپنڈی اور اسلام آباد کلسٹر",
        "assigned_fso_id": "FSO-PK-614",
        "keywords": ["rawalpindi", "islamabad", "rwp", "isb", "murree", "taxila",
                      "attock", "gujar khan", "wah cantt", "kahuta", "chakwal", "jhelum"],
        "active": 1,
    },
    {
        "id": "region_lahore",
        "name": "Lahore Central & North",
        "urdu_name": "لاہور سینٹرل اور شمالی پنجاب",
        "assigned_fso_id": "FSO-PK-301",
        "keywords": ["lahore", "kasur", "sheikhupura", "muridke", "shahdara",
                      "nankana sahib", "pattoki", "chunian", "raiwind", "gulberg",
                      "johar town", "shadman", "iqbal town", "cantt lahore"],
        "active": 1,
    },
    {
        "id": "region_faisalabad",
        "name": "Faisalabad & Sialkot",
        "urdu_name": "فیصل آباد اور سیالکوٹ کلسٹر",
        "assigned_fso_id": "FSO-PK-450",
        "keywords": ["faisalabad", "sialkot", "gujranwala", "gujrat", "jhang",
                      "daska", "sambrial", "wazirabad", "hafizabad",
                      "toba tek singh", "gojra", "samundri"],
        "active": 1,
    },
    {
        "id": "region_peshawar",
        "name": "Peshawar & KP",
        "urdu_name": "پشاور اور خیبر پختونخوا کلسٹر",
        "assigned_fso_id": "FSO-PK-520",
        "keywords": ["peshawar", "mardan", "charsadda", "nowshera", "swabi",
                      "kohat", "abbottabad", "haripur", "mansehra", "swat",
                      "mingora", "bannu", "di khan"],
        "active": 1,
    },
]

DEFAULT_FSOS = [
    {
        "id": "FSO-PK-782", "name": "Tariq Mehmood",
        "email": "tariq.mehmood@ofsp.org.pk", "phone": "+92-300-8472910",
        "cnic": "36302-9876543-1",
        "badge": "FSO Punjab South (Senior Officer)",
        "assigned_region_ids": ["region_multan"],
        "password": "password123",
    },
    {
        "id": "FSO-PK-614", "name": "Ayesha Siddiqui",
        "email": "ayesha.siddiqui@ofsp.org.pk", "phone": "+92-333-5129841",
        "cnic": "37405-5678901-2",
        "badge": "FSO Rawalpindi / Islamabad",
        "assigned_region_ids": ["region_rwp_isb"],
        "password": "password123",
    },
    {
        "id": "FSO-PK-301", "name": "Zahid Hussain",
        "email": "zahid.hussain@ofsp.org.pk", "phone": "+92-321-4458901",
        "cnic": "35201-4458901-3",
        "badge": "FSO Lahore Cluster",
        "assigned_region_ids": ["region_lahore"],
        "password": "password123",
    },
    {
        "id": "FSO-PK-450", "name": "Farhan Ali",
        "email": "farhan.ali@ofsp.org.pk", "phone": "+92-345-7788123",
        "cnic": "33101-7788123-5",
        "badge": "FSO Faisalabad & Industrial Belt",
        "assigned_region_ids": ["region_faisalabad"],
        "password": "password123",
    },
    {
        "id": "FSO-PK-520", "name": "Imran Khattak",
        "email": "imran.khattak@ofsp.org.pk", "phone": "+92-313-9098765",
        "cnic": "17301-9098765-7",
        "badge": "FSO KP & Peshawar Cluster",
        "assigned_region_ids": ["region_peshawar"],
        "password": "password123",
    },
]


def seed_database():
    """Seed the database with default regions, FSOs, admin, and demo family."""
    with get_db() as conn:
        # Seed FSOs + their user accounts FIRST (regions reference FSO IDs)
        for f in DEFAULT_FSOS:
            pw_hash, salt = hash_password(f["password"])
            user_id = f"fso_{f['id'].lower().replace('-', '_')}"
            conn.execute(
                """INSERT OR IGNORE INTO users
                   (id, name, cnic, phone, email, password_hash, salt, role, account_type,
                    designation, badge, fso_id, assigned_region_ids, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'fso', 'official', 'Field Support Officer',
                           ?, ?, ?, ?)""",
                (user_id, f["name"], f["cnic"], f["phone"], f["email"],
                 pw_hash, salt, f["badge"], f["id"],
                 json.dumps(f["assigned_region_ids"]),
                 datetime.now().isoformat()),
            )
            conn.execute(
                """INSERT OR IGNORE INTO fsos (id, user_id, name, cnic, email, phone, badge, assigned_region_ids)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (f["id"], user_id, f["name"], f["cnic"], f["email"],
                 f["phone"], f["badge"], json.dumps(f["assigned_region_ids"])),
            )

        # Seed regions AFTER FSOs (regions reference assigned_fso_id → fsos.id)
        for r in DEFAULT_REGIONS:
            conn.execute(
                """INSERT OR IGNORE INTO regions (id, name, urdu_name, assigned_fso_id, keywords, active)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (r["id"], r["name"], r["urdu_name"], r["assigned_fso_id"],
                 json.dumps(r["keywords"]), r["active"]),
            )

        # Seed admin account
        admin_pw_hash, admin_salt = hash_password("password123")
        conn.execute(
            """INSERT OR IGNORE INTO users
               (id, name, cnic, phone, email, password_hash, salt, role, account_type,
                designation, badge, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'admin', 'official', ?, ?, ?)""",
            ("admin_directorate", "Central Directorate Admin", "61101-1122334-5",
             "051-9201450", "admin@ofsp.org.pk", admin_pw_hash, admin_salt,
             "Program Director / Central Oversight", "HQ Directorate OFSP",
             datetime.now().isoformat()),
        )

        # Seed demo family account
        fam_pw_hash, fam_salt = hash_password("password123")
        conn.execute(
            """INSERT OR IGNORE INTO users
               (id, name, cnic, phone, email, password_hash, salt, role, account_type,
                area_address, city, assigned_region_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'family', 'family', ?, ?, ?, ?)""",
            ("fam_nasreen", "Nasreen Akhtar", "35202-8472910-2",
             "0300-8472910", "nasreen.akhtar@example.com", fam_pw_hash, fam_salt,
             "House #14, Street 3, Mohalla Gulzar-e-Madina, Multan", "Multan",
             "region_multan", datetime.now().isoformat()),
        )
