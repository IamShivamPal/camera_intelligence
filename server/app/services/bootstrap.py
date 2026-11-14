import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from email_validator import validate_email, EmailNotValidError

from app.models.user import User
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH = 8


def normalize_email(email: str) -> str:
    """Validate and normalize an email address."""
    if not email or not email.strip():
        raise ValueError("Email address cannot be empty.")
    try:
        validated = validate_email(
            email.strip(),
            check_deliverability=False,
            globally_deliverable=False,
        )
        return validated.normalized
    except EmailNotValidError as e:
        raise ValueError(f"Invalid email address: {e}") from e


def bootstrap_super_admin(
    db: Session,
    email: str,
    password: str,
    full_name: str = "System Administrator",
) -> tuple[User, bool, str]:
    """
    Idempotently bootstrap the initial super_admin user.

    Returns:
        (user, created, message)

    Raises:
        ValueError: If inputs are invalid or an ordinary user already exists with this email.
    """
    clean_email = normalize_email(email)
    clean_name = (full_name or "").strip() or "System Administrator"

    if not password:
        raise ValueError("Password cannot be empty.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )

    # Check for existing user with this email (case-insensitive)
    existing_user = (
        db.query(User)
        .filter(func.lower(User.email) == clean_email.lower())
        .first()
    )

    if existing_user:
        if existing_user.system_role == "super_admin":
            logger.info("Super admin user already exists: %s", clean_email)
            return (
                existing_user,
                False,
                f"Super admin user '{clean_email}' already exists. No changes made.",
            )
        else:
            # Refuse to silently promote an ordinary user
            raise ValueError(
                f"Cannot bootstrap super_admin: User '{clean_email}' already exists with role "
                f"'{existing_user.system_role}'. Refusing to silently alter existing user roles."
            )

    # Create new super_admin
    password_hash = get_password_hash(password)
    new_user = User(
        email=clean_email,
        full_name=clean_name,
        password_hash=password_hash,
        system_role="super_admin",
        is_active=True,
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info(
            "Super admin user created successfully: %s (ID: %d)",
            clean_email,
            new_user.id,
        )
        return (
            new_user,
            True,
            f"Super admin user '{clean_email}' created successfully (ID: {new_user.id}).",
        )
    except IntegrityError as e:
        db.rollback()
        # Handle concurrent bootstrap attempt
        existing_again = (
            db.query(User)
            .filter(func.lower(User.email) == clean_email.lower())
            .first()
        )
        if existing_again and existing_again.system_role == "super_admin":
            return (
                existing_again,
                False,
                f"Super admin user '{clean_email}' already exists (race condition resolved).",
            )
        raise ValueError(
            f"Database integrity error while creating super_admin: {e}"
        ) from e
