"""
db/security.py — SQL RULE: no queries here, but this module is the only
place password hashes and JWTs are produced/checked. Nothing outside
this file should call passlib or jose directly.

bcrypt via passlib (cost factor 12). Hash on creation; never log, never
return, never store plaintext. Verify with passlib.verify(), never `==`.
"""

import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*-_="


def generate_strong_password(length: int = 14) -> str:
    """Used by the admin reset-password endpoint. secrets, not random —
    this becomes a real officer's login credential."""
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _pwd_context.verify(plain_password, password_hash)
    except ValueError:
        # Malformed hash (should never happen with our own hash_password) —
        # treat as a failed verification rather than raising into a route.
        return False


def create_access_token(officer_id: uuid.UUID, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(officer_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
