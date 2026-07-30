"""
security.py — password hashing and JWT helpers.

Passwords are hashed with bcrypt (cost factor 12) via passlib. Plaintext
passwords are never logged, returned, or stored.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _pwd_context.verify(plain_password, password_hash)


def create_access_token(officer_id: UUID, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
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
