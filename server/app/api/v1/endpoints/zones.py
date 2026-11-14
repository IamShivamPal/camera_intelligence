import math
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.schemas.workstation_zone import (
    WorkstationZoneCreate,
    WorkstationZoneUpdate,
    WorkstationZoneResponse,
    WorkstationZoneDetailResponse,
    ZoneEmployeeAssign,
)
from app.schemas.common import PaginatedResponse
from app.api.deps import (
    require_viewer,
    require_location_admin,
    has_location_access,
)
from app.services import workstation_zone_service

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[WorkstationZoneResponse],
    summary="List workstation zones with pagination and filters",
    description="Retrieve paginated workstation zones in accessible locations. Filter by location, camera, employee, active status, or search.",
)
def list_zones(
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    location_id: Annotated[int | None, Query(description="Filter by location ID")] = None,
    camera_id: Annotated[int | None, Query(description="Filter by camera ID")] = None,
    assigned_employee_id: Annotated[int | None, Query(description="Filter by assigned employee ID")] = None,
    is_active: Annotated[bool | None, Query(description="Filter by active status")] = None,
    search: Annotated[str | None, Query(description="Search by zone code or name")] = None,
) -> PaginatedResponse[WorkstationZoneResponse]:
    items, total = workstation_zone_service.list_zones(
        db=db,
        user=current_user,
        page=page,
        size=size,
        location_id=location_id,
        camera_id=camera_id,
        assigned_employee_id=assigned_employee_id,
        is_active=is_active,
        search=search,
    )

    pages = math.ceil(total / size) if total > 0 else 0

    return PaginatedResponse[WorkstationZoneResponse](
        items=[WorkstationZoneResponse.model_validate(z) for z in items],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.post(
    "",
    response_model=WorkstationZoneDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create workstation zone",
    description="Define a new workstation zone with polygon vertices. Validates camera location consistency and polygon geometry.",
)
def create_zone(
    data: WorkstationZoneCreate,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkstationZoneDetailResponse:
    zone = workstation_zone_service.create_zone(
        db=db, data=data, current_user=current_user
    )
    return workstation_zone_service.format_zone_detail(db=db, zone=zone)


@router.get(
    "/{zone_id}",
    response_model=WorkstationZoneDetailResponse,
    summary="Get workstation zone details",
    description="Retrieve workstation zone metadata, polygon vertices, and camera/employee associations.",
)
def get_zone(
    zone_id: int,
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkstationZoneDetailResponse:
    zone = workstation_zone_service.get_zone_by_id(db=db, zone_id=zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workstation zone with ID {zone_id} not found.",
        )

    if not has_location_access(db=db, user=current_user, location_id=zone.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized for zone location ID {zone.location_id}.",
        )

    return workstation_zone_service.format_zone_detail(db=db, zone=zone)


@router.patch(
    "/{zone_id}",
    response_model=WorkstationZoneDetailResponse,
    summary="Update workstation zone",
    description="Update zone attributes, polygon coordinates, camera association, or inactivity threshold.",
)
def update_zone(
    zone_id: int,
    data: WorkstationZoneUpdate,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkstationZoneDetailResponse:
    zone = workstation_zone_service.get_zone_by_id(db=db, zone_id=zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workstation zone with ID {zone_id} not found.",
        )

    updated = workstation_zone_service.update_zone(
        db=db, zone=zone, data=data, current_user=current_user
    )
    return workstation_zone_service.format_zone_detail(db=db, zone=updated)


@router.delete(
    "/{zone_id}",
    response_model=WorkstationZoneResponse,
    summary="Deactivate workstation zone",
    description="Soft-deactivate a workstation zone (sets is_active=False).",
)
def deactivate_zone(
    zone_id: int,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkstationZoneResponse:
    zone = workstation_zone_service.get_zone_by_id(db=db, zone_id=zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workstation zone with ID {zone_id} not found.",
        )

    deactivated = workstation_zone_service.deactivate_zone(
        db=db, zone=zone, current_user=current_user
    )
    return WorkstationZoneResponse.model_validate(deactivated)


@router.post(
    "/{zone_id}/assign-employee",
    response_model=WorkstationZoneDetailResponse,
    summary="Assign employee to workstation zone",
    description="Assign an employee to this zone. Validates that the employee belongs to the same location as the zone.",
)
def assign_employee(
    zone_id: int,
    data: ZoneEmployeeAssign,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkstationZoneDetailResponse:
    zone = workstation_zone_service.get_zone_by_id(db=db, zone_id=zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workstation zone with ID {zone_id} not found.",
        )

    updated = workstation_zone_service.assign_employee_to_zone(
        db=db, zone=zone, employee_id=data.employee_id, current_user=current_user
    )
    return workstation_zone_service.format_zone_detail(db=db, zone=updated)


@router.delete(
    "/{zone_id}/assign-employee",
    response_model=WorkstationZoneDetailResponse,
    summary="Remove employee assignment from workstation zone",
    description="Clear the assigned employee on this workstation zone.",
)
def remove_employee(
    zone_id: int,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkstationZoneDetailResponse:
    zone = workstation_zone_service.get_zone_by_id(db=db, zone_id=zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workstation zone with ID {zone_id} not found.",
        )

    updated = workstation_zone_service.remove_employee_from_zone(
        db=db, zone=zone, current_user=current_user
    )
    return workstation_zone_service.format_zone_detail(db=db, zone=updated)

