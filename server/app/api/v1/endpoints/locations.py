from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.models.location import Location
from app.schemas.location import (
    LocationCreate,
    LocationUpdate,
    LocationResponse,
    LocationDetailResponse,
)
from app.api.deps import (
    get_current_user,
    require_super_admin,
    require_location_admin,
    require_viewer,
    has_location_access,
)
from app.services import location_service

router = APIRouter()


@router.get(
    "",
    response_model=list[LocationResponse],
    summary="List accessible locations",
    description="Retrieve list of locations accessible to current user (super_admin has global access).",
)
def list_locations(
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
    is_active: Annotated[bool | None, Query(description="Filter by active status")] = None,
) -> list[LocationResponse]:
    locations = location_service.list_accessible_locations(
        db=db, user=current_user, is_active=is_active
    )
    return [LocationResponse.model_validate(loc) for loc in locations]


@router.post(
    "",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create location",
    description="Create a new location branch. Requires global super_admin authority.",
)
def create_location(
    data: LocationCreate,
    _: Annotated[User, Depends(require_super_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> LocationResponse:
    location = location_service.create_location(db=db, data=data)
    return LocationResponse.model_validate(location)


@router.get(
    "/{location_id}",
    response_model=LocationDetailResponse,
    summary="Get location details",
    description="Retrieve location details including department and employee counts. Requires access to this location.",
)
def get_location(
    location_id: int,
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
) -> LocationDetailResponse:
    location = location_service.get_location_by_id(db=db, location_id=location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID {location_id} not found.",
        )

    if not has_location_access(db=db, user=current_user, location_id=location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized for location ID {location_id}.",
        )

    return location_service.get_location_detail_response(db=db, location=location)


@router.patch(
    "/{location_id}",
    response_model=LocationResponse,
    summary="Update location",
    description="Update location attributes. Requires location_admin privileges for this location or super_admin.",
)
def update_location(
    location_id: int,
    data: LocationUpdate,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> LocationResponse:
    location = location_service.get_location_by_id(db=db, location_id=location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID {location_id} not found.",
        )

    if not has_location_access(db=db, user=current_user, location_id=location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized to update location ID {location_id}.",
        )

    updated = location_service.update_location(db=db, location=location, data=data)
    return LocationResponse.model_validate(updated)


@router.delete(
    "/{location_id}",
    response_model=LocationResponse,
    summary="Deactivate location",
    description="Soft-deactivate a location. Requires location_admin privileges for this location or super_admin.",
)
def deactivate_location(
    location_id: int,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> LocationResponse:
    location = location_service.get_location_by_id(db=db, location_id=location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID {location_id} not found.",
        )

    if not has_location_access(db=db, user=current_user, location_id=location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized to deactivate location ID {location_id}.",
        )

    deactivated = location_service.deactivate_location(db=db, location=location)
    return LocationResponse.model_validate(deactivated)

