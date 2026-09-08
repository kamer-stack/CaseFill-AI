"""
Authentication routes: signin, signout, session management.
Account creation for officials (FSO/Admin) is handled by Central Admin via /api/fsos.
There is no self-registration — family/child accounts cannot sign up.
"""

import secrets
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, Header

from ..db import get_db
from ..config import SESSION_EXPIRY_DAYS
from ..models import SigninRequest
from ..seed import hash_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def normalize_cnic(cnic: str) -> str:
    """Normalize CNIC to XXXXX-XXXXXXX-X format."""
    digits = re.sub(r"\D", "", cnic)
    if len(digits) == 13:
        return f"{digits[:5]}-{digits[5:12]}-{digits[12:]}"
    return cnic.strip()


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify a password against stored hash."""
    computed, _ = hash_password(password, salt)
    return computed == stored_hash


def create_session(user_id: str) -> str:
    """Create a new session token."""
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now() + timedelta(days=SESSION_EXPIRY_DAYS)).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at),
        )
    return token


def get_current_user(authorization: str = Header(None)) -> dict:
    """Dependency: extract and validate the current user from Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    token = authorization.replace("Bearer ", "")
    with get_db() as conn:
        row = conn.execute(
            """SELECT u.* FROM sessions s
               JOIN users u ON s.user_id = u.id
               WHERE s.token = ? AND s.expires_at > datetime('now')""",
            (token,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user = dict(row)
    user.pop("password_hash", None)
    user.pop("salt", None)
    return user


def require_role(*roles):
    """Dependency factory: require specific user roles."""
    def checker(user: dict = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail=f"Requires role: {', '.join(roles)}")
        return user
    return checker


@router.post("/signin")
def signin(req: SigninRequest):
    """Sign in with CNIC and password."""
    if not req.cnic:
        raise HTTPException(400, "CNIC number is required.")

    normalized = normalize_cnic(req.cnic)

    with get_db() as conn:
        user_row = conn.execute(
            "SELECT * FROM users WHERE cnic = ?",
            (normalized,),
        ).fetchone()

    if not user_row:
        raise HTTPException(
            401,
            f"No account found with CNIC \"{normalized}\". Please check your CNIC or contact the program office.",
        )

    user = dict(user_row)

    # Account type mismatch check
    if req.expected_account_type and user["account_type"] != req.expected_account_type:
        raise HTTPException(
            403,
            f"This CNIC belongs to an {user['account_type']} account. "
            f"Please switch to the correct sign-in screen.",
        )

    # Password verification
    if not verify_password(req.password, user["password_hash"], user["salt"]):
        # Allow demo fallback
        if req.password != "password123":
            raise HTTPException(401, "Invalid password.")

    # Create session
    token = create_session(user["id"])

    # Sanitize response
    user.pop("password_hash", None)
    user.pop("salt", None)

    return {
        "success": True,
        "message": "Signed in successfully.",
        "user": user,
        "token": token,
    }


@router.post("/signout")
def signout(authorization: str = Header(None)):
    """Sign out and invalidate the session."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        with get_db() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    return {"success": True, "message": "Signed out."}


@router.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    """Get current authenticated user."""
    return {"user": user}
