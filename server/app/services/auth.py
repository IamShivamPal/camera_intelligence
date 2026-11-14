from datetime import datetime, timezone
import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.core.security import verify_password, create_access_token
from app.schemas.auth import TokenResponse, UserResponse

logger = logging.getLogger(__name__)


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> User:
    """
    Authenticate a user by email and password.

    Raises:
        HTTPException 401: If credentials do not match or user does not exist.
        HTTPException 403: If the user account is inactive.
    """
    clean_email = email.strip().lower()
    user = (
        db.query(User)
        .filter(func.lower(User.email) == clean_email)
        .first()
    )

    # Use generic message to prevent user enumeration attacks
    if not user or not verify_password(password, user.password_hash):
        logger.warning("Failed login attempt for email: %s", clean_email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning("Login rejected for inactive user: %s", clean_email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive. Please contact an administrator.",
        )

    # Update last_login_at timestamp upon successful authentication
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    logger.info("User logged in successfully: %s (ID: %d)", user.email, user.id)
    return user


def create_user_token_response(user: User) -> TokenResponse:
    """Generate signed JWT token and assemble the TokenResponse payload."""
    token, expires_at, expires_in = create_access_token(
        subject=str(user.id),
        extra_claims={
            "email": user.email,
            "role": user.system_role,
        },
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        expires_at=expires_at,
        user=UserResponse.model_validate(user),
    )

