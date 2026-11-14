import logging
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, ExpiredSignatureError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User, user_locations
from app.models.location import Location
from app.core.security import decode_access_token
from app.core.permissions import SystemRole, has_minimum_role

logger = logging.getLogger(__name__)

# Bearer token extractor
http_bearer = HTTPBearer(auto_error=True)
http_bearer_optional = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(http_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """
    Authenticate request via JWT Bearer token and retrieve the user from database.

    Raises:
        HTTPException 401: If token is invalid, expired, malformed, or user not found.
        HTTPException 403: If user account is deactivated.
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (JWTError, ValueError) as e:
        logger.warning("JWT validation failed: %s", type(e).__name__)
        raise credentials_exception

    # Load fresh user state directly from the database (do not trust client claims)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        logger.warning("Token user ID %d not found in database", user_id)
        raise credentials_exception

    if not user.is_active:
        logger.warning("Authenticated user %s (ID %d) is deactivated", user.email, user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive. Please contact an administrator.",
        )

    return user


def get_optional_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer_optional)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    """Optional user extractor for public endpoints that support contextual authentication."""
    if credentials is None:
        return None
    try:
        return get_current_user(credentials=credentials, db=db)
    except HTTPException:
        return None


# -----------------------------------------------------------------------------
# ROLE-BASED AUTHORIZATION DEPENDENCIES (Hierarchy Policy)
# -----------------------------------------------------------------------------

def require_super_admin(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Require super_admin role (top-level system authority)."""
    if current_user.system_role != SystemRole.SUPER_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required (super_admin).",
        )
    return current_user


def require_location_admin(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Require location_admin or higher (super_admin, location_admin)."""
    if not has_minimum_role(current_user.system_role, SystemRole.LOCATION_ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location administrative privileges required.",
        )
    return current_user


def require_operator(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Require operator or higher (super_admin, location_admin, operator)."""
    if not has_minimum_role(current_user.system_role, SystemRole.OPERATOR.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or higher privileges required.",
        )
    return current_user


def require_viewer(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Require viewer or higher (any active authenticated user with a recognized role)."""
    if not has_minimum_role(current_user.system_role, SystemRole.VIEWER.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only viewer or higher privileges required.",
        )
    return current_user


def require_roles(allowed_roles: set[str]):
    """Factory dependency for explicit role set matching."""
    def role_checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.system_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of the following roles: {', '.join(sorted(allowed_roles))}.",
            )
        return current_user
    return role_checker


# -----------------------------------------------------------------------------
# LOCATION-BASED AUTHORIZATION DEPENDENCIES
# -----------------------------------------------------------------------------

def has_location_access(db: Session, user: User, location_id: int) -> bool:
    """
    Check if a user is authorized for a given location.
    - super_admin has global access (always True).
    - Other users require an explicit row in user_locations.
    """
    if user.system_role == SystemRole.SUPER_ADMIN.value:
        return True

    assignment = (
        db.query(user_locations)
        .filter(
            user_locations.c.user_id == user.id,
            user_locations.c.location_id == location_id,
        )
        .first()
    )
    return assignment is not None


def require_location_access(
    location_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Location:
    """
    Validate that target location exists and that current_user has access.

    Raises:
        HTTPException 404: If location does not exist in the database.
        HTTPException 403: If user is not authorized for this location.
    """
    location = db.query(Location).filter(Location.id == location_id).first()
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID {location_id} not found.",
        )

    if not has_location_access(db=db, user=current_user, location_id=location_id):
        logger.warning(
            "User %s (ID %d, role %s) denied access to location %d",
            current_user.email,
            current_user.id,
            current_user.system_role,
            location_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized for location ID {location_id}.",
        )

    return location

