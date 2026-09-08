"""
Admin management routes: FSO CRUD, region CRUD, admin credentials.
"""

import json
import re
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends

from ..db import get_db
from ..models import FSOCreateRequest, FSOUpdateRequest, RegionCreateRequest
from ..seed import hash_password
from .auth import get_current_user, require_role, normalize_cnic

router = APIRouter(tags=["admin"])


# ─── Region CRUD ────────────────────────────────────────────────────────────────

@router.get("/api/regions")
def list_regions(user: dict = Depends(get_current_user)):
    """List all regions."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM regions").fetchall()
    return {"regions": [dict(r) for r in rows]}


@router.post("/api/regions")
def create_region(
    req: RegionCreateRequest,
    user: dict = Depends(require_role("admin")),
):
    """Create a new region."""
    region_id = req.name.lower().replace(" ", "_").replace("&", "and")
    if not region_id.startswith("region_"):
        region_id = f"region_{region_id}"

    with get_db() as conn:
        conn.execute(
            """INSERT INTO regions (id, name, urdu_name, assigned_fso_id, keywords, active)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (region_id, req.name, req.urdu_name, req.assigned_fso_id,
             json.dumps(req.keywords), 1 if req.active else 0),
        )

    return {"success": True, "region": {"id": region_id, "name": req.name}}


@router.put("/api/regions/{region_id}")
def update_region(
    region_id: str,
    body: dict,
    user: dict = Depends(require_role("admin")),
):
    """Update a region."""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT * FROM regions WHERE id = ?", (region_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(404, "Region not found")

        updates = {}
        if "name" in body:
            updates["name"] = body["name"]
        if "urdu_name" in body:
            updates["urdu_name"] = body["urdu_name"]
        if "keywords" in body:
            updates["keywords"] = json.dumps(body["keywords"])
        if "assigned_fso_id" in body:
            updates["assigned_fso_id"] = body["assigned_fso_id"]
        if "active" in body:
            updates["active"] = 1 if body["active"] else 0

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
            conn.execute(
                f"UPDATE regions SET {set_clause} WHERE id = ?",
                (*updates.values(), region_id),
            )

    return {"success": True}


# ─── FSO CRUD ────────────────────────────────────────────────────────────────────

@router.get("/api/fsos")
def list_fsos(user: dict = Depends(get_current_user)):
    """List all FSOs."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM fsos WHERE active = 1").fetchall()
    return {"fsos": [dict(r) for r in rows]}


@router.post("/api/fsos")
def create_fso(
    req: FSOCreateRequest,
    user: dict = Depends(require_role("admin")),
):
    """Provision a new FSO account."""
    if not req.name or not req.name.strip():
        raise HTTPException(400, "Officer name is required")
    if not req.cnic or not req.cnic.strip():
        raise HTTPException(400, "13-digit CNIC is required")

    normalized_cnic = normalize_cnic(req.cnic)

    # Check uniqueness
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE cnic = ?", (normalized_cnic,)
        ).fetchone()
        if existing:
            raise HTTPException(409, f"CNIC {normalized_cnic} already registered.")

    # Collision-safe FSO ID (fsos.id is the primary key)
    with get_db() as conn:
        base_num = 100 + int(datetime.now().timestamp()) % 900
        fso_id = f"FSO-PK-{base_num}"
        suffix = 0
        while conn.execute("SELECT 1 FROM fsos WHERE id = ?", (fso_id,)).fetchone():
            suffix += 1
            fso_id = f"FSO-PK-{base_num}{suffix}"
    region_ids = req.assigned_region_ids or []

    # Get region names
    with get_db() as conn:
        if region_ids:
            placeholders = ",".join(["?"] * len(region_ids))
            region_rows = conn.execute(
                f"SELECT name FROM regions WHERE id IN ({placeholders})", region_ids
            ).fetchall()
            region_names = [r["name"] for r in region_rows]
        else:
            region_names = []

    pw_hash, salt = hash_password(req.password or "password123")
    user_id = f"fso_{int(datetime.now().timestamp())}"

    with get_db() as conn:
        # Create the user login FIRST (fsos.user_id has a foreign key to users.id)
        conn.execute(
            """INSERT INTO users
               (id, name, cnic, phone, email, password_hash, salt, role, account_type,
                designation, badge, fso_id, assigned_region_ids, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'fso', 'official', 'Field Support Officer',
                       ?, ?, ?, ?)""",
            (user_id, req.name.strip(), normalized_cnic, req.phone or "",
             req.email or "", pw_hash, salt,
             req.badge or f"{req.name.strip()} ({region_names[0] if region_names else 'Field Officer'})",
             fso_id, json.dumps(region_ids), datetime.now().isoformat()),
        )

        # Then the FSO roster record
        conn.execute(
            """INSERT INTO fsos (id, user_id, name, cnic, email, phone, badge, assigned_region_ids)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (fso_id, user_id, req.name.strip(), normalized_cnic,
             req.email or "", req.phone or "",
             req.badge or f"{req.name.strip()} ({region_names[0] if region_names else 'Field Officer'})",
             json.dumps(region_ids)),
        )

        # Update region assignments (only regions that are still unassigned)
        for rid in region_ids:
            conn.execute(
                """UPDATE regions SET assigned_fso_id = ?
                   WHERE id = ? AND (assigned_fso_id IS NULL OR assigned_fso_id = '')""",
                (fso_id, rid),
            )

    return {
        "success": True,
        "fso": {
            "id": fso_id,
            "name": req.name.strip(),
            "cnic": normalized_cnic,
            "email": req.email,
            "phone": req.phone,
            "badge": req.badge or f"{req.name.strip()} ({region_names[0] if region_names else 'Field Officer'})",
            "assignedRegionIds": region_ids,
            "assignedRegionNames": region_names,
        },
    }


@router.patch("/api/fsos/{fso_id}")
def update_fso(
    fso_id: str,
    req: FSOUpdateRequest,
    user: dict = Depends(require_role("admin")),
):
    """Update an FSO's profile, regions, or password."""
    with get_db() as conn:
        fso_row = conn.execute("SELECT * FROM fsos WHERE id = ?", (fso_id,)).fetchone()
        if not fso_row:
            raise HTTPException(404, "Officer not found")

        updates = {}
        if req.name:
            updates["name"] = req.name.strip()
        if req.phone:
            updates["phone"] = req.phone.strip()
        if req.email:
            updates["email"] = req.email.strip()
        if req.badge:
            updates["badge"] = req.badge.strip()
        if req.assigned_region_ids is not None:
            updates["assigned_region_ids"] = json.dumps(req.assigned_region_ids)

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
            conn.execute(
                f"UPDATE fsos SET {set_clause} WHERE id = ?",
                (*updates.values(), fso_id),
            )

        # Update user record too
        user_updates = {}
        if req.name:
            user_updates["name"] = req.name.strip()
        if req.phone:
            user_updates["phone"] = req.phone.strip()
        if req.email:
            user_updates["email"] = req.email.strip()
        if req.badge:
            user_updates["badge"] = req.badge.strip()
        if req.assigned_region_ids is not None:
            user_updates["assigned_region_ids"] = json.dumps(req.assigned_region_ids)
        if req.password and len(req.password) >= 6:
            pw_hash, salt = hash_password(req.password)
            user_updates["password_hash"] = pw_hash
            user_updates["salt"] = salt

        if user_updates:
            set_clause = ", ".join(f"{k} = ?" for k in user_updates.keys())
            conn.execute(
                f"UPDATE users SET {set_clause} WHERE fso_id = ?",
                (*user_updates.values(), fso_id),
            )

    return {"success": True}


@router.delete("/api/fsos/{fso_id}")
def delete_fso(
    fso_id: str,
    user: dict = Depends(require_role("admin")),
):
    """Delete an FSO account."""
    with get_db() as conn:
        fso_row = conn.execute("SELECT * FROM fsos WHERE id = ?", (fso_id,)).fetchone()
        if not fso_row:
            raise HTTPException(404, "Officer not found")

        # Deactivate FSO
        conn.execute("UPDATE fsos SET active = 0 WHERE id = ?", (fso_id,))

        # Remove user login
        conn.execute("DELETE FROM users WHERE fso_id = ?", (fso_id,))

        # Unassign from regions
        conn.execute(
            "UPDATE regions SET assigned_fso_id = NULL WHERE assigned_fso_id = ?",
            (fso_id,),
        )

    return {"success": True, "message": "Officer account deactivated."}


# ─── Admin Credentials ──────────────────────────────────────────────────────────

@router.patch("/api/admin/credentials")
def update_admin_credentials(
    body: dict,
    user: dict = Depends(require_role("admin")),
):
    """Admin updates their own credentials."""
    with get_db() as conn:
        if body.get("currentPassword"):
            row = conn.execute(
                "SELECT password_hash, salt FROM users WHERE id = ?", (user["id"],)
            ).fetchone()
            if row:
                from .auth import verify_password
                if not verify_password(body["currentPassword"], row["password_hash"], row["salt"]):
                    raise HTTPException(401, "Current password incorrect")

        updates = {}
        if body.get("name"):
            updates["name"] = body["name"].strip()
        if body.get("phone"):
            updates["phone"] = body["phone"].strip()
        if body.get("email"):
            updates["email"] = body["email"].strip()
        if body.get("newPassword") and len(body["newPassword"]) >= 6:
            pw_hash, salt = hash_password(body["newPassword"])
            updates["password_hash"] = pw_hash
            updates["salt"] = salt

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
            conn.execute(
                f"UPDATE users SET {set_clause} WHERE id = ?",
                (*updates.values(), user["id"]),
            )

    return {"success": True, "message": "Credentials updated."}
