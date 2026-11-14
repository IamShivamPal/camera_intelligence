import math
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.schemas.camera import (
    CameraCreate,
    CameraUpdate,
    CameraResponse,
    CameraDetailResponse,
    WorkstationZoneSummary,
)
from app.schemas.common import PaginatedResponse
from app.api.deps import (
    require_viewer,
    require_location_admin,
    has_location_access,
)
from app.services import camera_service

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[CameraResponse],
    summary="List accessible cameras with pagination and filters",
    description="Retrieve paginated camera inventory within accessible locations. Supports filtering by location, role, stream type, status, active flag, and text search.",
)
def list_cameras(
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    location_id: Annotated[int | None, Query(description="Filter by location ID")] = None,
    camera_role: Annotated[str | None, Query(description="Filter by camera role")] = None,
    stream_type: Annotated[str | None, Query(description="Filter by stream ingestion type")] = None,
    connection_status: Annotated[str | None, Query(description="Filter by connection status")] = None,
    is_active: Annotated[bool | None, Query(description="Filter by active status")] = None,
    search: Annotated[str | None, Query(description="Search by name or camera code")] = None,
) -> PaginatedResponse[CameraResponse]:
    items, total = camera_service.list_cameras(
        db=db,
        user=current_user,
        page=page,
        size=size,
        location_id=location_id,
        camera_role=camera_role,
        stream_type=stream_type,
        connection_status=connection_status,
        is_active=is_active,
        search=search,
    )

    pages = math.ceil(total / size) if total > 0 else 0

    return PaginatedResponse[CameraResponse](
        items=[CameraResponse.model_validate(c) for c in items],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.post(
    "",
    response_model=CameraDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register camera",
    description="Register a new CCTV camera. Validates camera code uniqueness, location authorization, and sanitizes stream credentials.",
)
def create_camera(
    data: CameraCreate,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> CameraDetailResponse:
    camera = camera_service.create_camera(
        db=db, data=data, current_user=current_user
    )
    return camera_service.format_camera_detail(db=db, camera=camera)


@router.get(
    "/{camera_id}",
    response_model=CameraDetailResponse,
    summary="Get camera details",
    description="Retrieve camera metadata and configuration details. Requires access to the camera's location.",
)
def get_camera(
    camera_id: int,
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
) -> CameraDetailResponse:
    camera = camera_service.get_camera_by_id(db=db, camera_id=camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with ID {camera_id} not found.",
        )

    if not has_location_access(db=db, user=current_user, location_id=camera.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized for camera location ID {camera.location_id}.",
        )

    return camera_service.format_camera_detail(db=db, camera=camera)


@router.patch(
    "/{camera_id}",
    response_model=CameraDetailResponse,
    summary="Update camera configuration",
    description="Update camera configuration, role, status, or location. Enforces unique codes and location authorization.",
)
def update_camera(
    camera_id: int,
    data: CameraUpdate,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> CameraDetailResponse:
    camera = camera_service.get_camera_by_id(db=db, camera_id=camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with ID {camera_id} not found.",
        )

    updated = camera_service.update_camera(
        db=db, camera=camera, data=data, current_user=current_user
    )
    return camera_service.format_camera_detail(db=db, camera=updated)


@router.delete(
    "/{camera_id}",
    response_model=CameraResponse,
    summary="Deactivate camera",
    description="Soft-deactivate camera (sets is_active=False). Requires location_admin privileges for the camera's location.",
)
def deactivate_camera(
    camera_id: int,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> CameraResponse:
    camera = camera_service.get_camera_by_id(db=db, camera_id=camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with ID {camera_id} not found.",
        )

    deactivated = camera_service.deactivate_camera(
        db=db, camera=camera, current_user=current_user
    )
    return CameraResponse.model_validate(deactivated)


@router.post(
    "/{camera_id}/zones/{zone_id}",
    response_model=CameraDetailResponse,
    summary="Associate workstation zone with camera",
    description="Associate an existing workstation zone with this camera. Validates that camera and workstation zone belong to the same location.",
)
def associate_workstation_zone(
    camera_id: int,
    zone_id: int,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> CameraDetailResponse:
    camera = camera_service.get_camera_by_id(db=db, camera_id=camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with ID {camera_id} not found.",
        )

    camera_service.associate_workstation_zone(
        db=db, camera=camera, zone_id=zone_id, current_user=current_user
    )
    return camera_service.format_camera_detail(db=db, camera=camera)


@router.get(
    "/{camera_id}/zones",
    response_model=list[WorkstationZoneSummary],
    summary="List camera workstation zones",
    description="Retrieve all workstation zones currently linked to this camera.",
)
def list_camera_zones(
    camera_id: int,
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
) -> list[WorkstationZoneSummary]:
    camera = camera_service.get_camera_by_id(db=db, camera_id=camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with ID {camera_id} not found.",
        )

    if not has_location_access(db=db, user=current_user, location_id=camera.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized for camera location ID {camera.location_id}.",
        )

    return [WorkstationZoneSummary.model_validate(z) for z in camera.workstation_zones]

