from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.models.location import Location
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse, LogoutResponse
from app.services.auth import authenticate_user, create_user_token_response
from app.api.deps import (
    get_current_user,
    require_super_admin,
    require_location_admin,
    require_operator,
    require_viewer,
    require_location_access,
)

router = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticate with email and password to receive a JWT access token.",
)
def login(
    login_data: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Authenticate credentials and issue JWT access token."""
    user = authenticate_user(
        db=db,
        email=login_data.email,
        password=login_data.password,
    )
    return create_user_token_response(user)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Current User Profile",
    description="Retrieve the profile of the currently authenticated user.",
)
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Return authenticated user profile (never exposes password hash)."""
    return UserResponse.model_validate(current_user)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="User Logout",
    description="Instruct client to dispose of stored tokens.",
)
def logout(
    current_user: Annotated[User, Depends(get_current_user)],
) -> LogoutResponse:
    """Stateless logout confirmation."""
    return LogoutResponse()


# -----------------------------------------------------------------------------
# AUTHORIZATION TEST & VERIFICATION PROBE ENDPOINTS
# -----------------------------------------------------------------------------

@router.get(
    "/test/super-admin-only",
    status_code=status.HTTP_200_OK,
    summary="Super Admin Verification Probe",
)
def probe_super_admin(
    admin: Annotated[User, Depends(require_super_admin)],
):
    return {"message": "Access granted: super_admin verified", "user_id": admin.id}


@router.get(
    "/test/location-admin",
    status_code=status.HTTP_200_OK,
    summary="Location Admin Verification Probe",
)
def probe_location_admin(
    admin: Annotated[User, Depends(require_location_admin)],
):
    return {"message": "Access granted: location_admin or higher", "user_id": admin.id}


@router.get(
    "/test/operator",
    status_code=status.HTTP_200_OK,
    summary="Operator Verification Probe",
)
def probe_operator(
    operator: Annotated[User, Depends(require_operator)],
):
    return {"message": "Access granted: operator or higher", "user_id": operator.id}


@router.get(
    "/test/viewer",
    status_code=status.HTTP_200_OK,
    summary="Viewer Verification Probe",
)
def probe_viewer(
    viewer: Annotated[User, Depends(require_viewer)],
):
    return {"message": "Access granted: viewer or higher", "user_id": viewer.id}


@router.get(
    "/test/locations/{location_id}",
    status_code=status.HTTP_200_OK,
    summary="Location Access Verification Probe",
)
def probe_location_access(
    location: Annotated[Location, Depends(require_location_access)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return {
        "message": f"Access granted to location '{location.name}'",
        "location_id": location.id,
        "location_name": location.name,
        "user_id": current_user.id,
        "user_role": current_user.system_role,
    }

