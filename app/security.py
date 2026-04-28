import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext

from .models import UserInDB

# Compatibility for passlib 1.7.4 with newer bcrypt packages.
# requirements.txt pins bcrypt==4.0.1, but this keeps local runs friendlier.
try:
    import bcrypt

    if not hasattr(bcrypt, "__about__"):
        class _BcryptAbout:
            __version__ = getattr(bcrypt, "__version__", "unknown")

        bcrypt.__about__ = _BcryptAbout()
except Exception:
    pass

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-secret-in-env")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {"create", "read", "update", "delete"},
    "user": {"read", "update"},
    "guest": {"read"},
}


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def find_user_by_username(username: str, users_db: dict[str, UserInDB]) -> UserInDB | None:
    """Search by username with secrets.compare_digest to reduce timing leaks."""
    for stored_username, user in users_db.items():
        if secrets.compare_digest(stored_username, username):
            return user
    return None


def create_access_token(username: str, role: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": username,
        "role": role,
        "exp": expires_at,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def basic_auth_exception(detail: str = "Invalid credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Basic"},
    )
