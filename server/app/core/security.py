from datetime import datetime, timezone, timedelta
from typing import Any
from jose import jwt, JWTError, ExpiredSignatureError
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import settings

# Configure password hasher with Argon2
password_context = PasswordHash((Argon2Hasher(),))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against an Argon2 hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return password_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash a plain-text password using Argon2."""
    if not password:
        raise ValueError("Password cannot be empty.")
    return password_context.hash(password)


def create_access_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, datetime, int]:
    """
    Generate a signed JWT access token.

    Args:
        subject: Unique subject identifier (typically user ID as a string).
        expires_delta: Optional custom duration for token validity.
        extra_claims: Optional non-sensitive claims (e.g. email, role).

    Returns:
        tuple of (encoded_token, expires_at_datetime, expires_in_seconds)
    """
    now = datetime.now(timezone.utc)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    expires_in_seconds = int((expire - now).total_seconds())

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
    }

    if extra_claims:
        # Prevent collision with standard claims
        for k, v in extra_claims.items():
            if k not in to_encode:
                to_encode[k] = v

    token = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token, expire, expires_in_seconds


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT access token.

    Raises:
        ExpiredSignatureError: If the token has expired.
        JWTError: If the token signature is invalid, malformed, or missing required claims.
    """
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    if "sub" not in payload:
        raise JWTError("Token payload is missing the 'sub' subject claim.")
    return payload
