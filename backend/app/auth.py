import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from .config import SECRET_KEY, TOKEN_HOURS
from .db import get_db
from . import models


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000)
    return f"pbkdf2_sha256$600000${salt}${digest.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    # Legacy hashes are upgraded on successful login, never created anew.
    if len(hashed) == 64 and "$" not in hashed:
        return hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(), hashed)
    try:
        scheme, iterations, salt, expected = hashed.split("$")
        if scheme != "pbkdf2_sha256" or not 100_000 <= int(iterations) <= 1_000_000:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def make_token(user_id: int, org_id: int | None = None) -> str:
    payload = {
        "sub": str(user_id),
        "org": org_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def _decode(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        data = jwt.decode(authorization[7:], SECRET_KEY, algorithms=["HS256"], options={"require": ["sub", "exp"]})
        if not isinstance(data["sub"], str) or not data["sub"].isdigit():
            raise ValueError("Invalid subject")
        if data.get("org") is not None and (type(data["org"]) is not int or data["org"] <= 0):
            raise ValueError("Invalid organization")
        return data
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(401, "Invalid token")


def current_user(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> models.User:
    data = _decode(authorization)
    user = db.get(models.User, int(data["sub"]))
    if not user:
        raise HTTPException(401, "Unknown user")
    return user


def current_membership(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> models.Membership:
    """The membership for the organization selected after login."""
    data = _decode(authorization)
    if not data.get("org"):
        raise HTTPException(400, "Select an organization first")
    m = (
        db.query(models.Membership)
        .filter_by(user_id=int(data["sub"]), org_id=data["org"])
        .first()
    )
    if not m:
        raise HTTPException(403, "Not a member of this organization")
    return m
