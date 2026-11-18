import math
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.schemas.camera import (
    CameraCreate,
    CameraUpdate,
    CameraResponse,
    CameraDetailResponse,
    WorkstationZoneSummary,
    CameraHeartbeat,
    CameraHeartbeatBatch,
)
from app.schemas.common import PaginatedResponse
from app.api.deps import (
    require_viewer,
    require_operator,
    require_location_admin,
    has_location_access,
)
from app.services import camera_service
from app.services.edge_bridge_service import edge_bridge_service

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


@router.post(
    "/heartbeat/batch",
    status_code=status.HTTP_200_OK,
    summary="Batch update camera connectivity heartbeats",
    description="Receive batched camera heartbeat telemetry from Edge Ingestion Service and update PostgreSQL connection statuses.",
)
def batch_camera_heartbeat(
    batch_data: CameraHeartbeatBatch,
    current_user: Annotated[User, Depends(require_operator)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, int]:
    updated_count = camera_service.record_batch_heartbeats(db=db, batch_data=batch_data)
    return {"updated": updated_count}


@router.post(
    "/{camera_id}/heartbeat",
    response_model=CameraResponse,
    summary="Update camera connectivity heartbeat",
    description="Receive connection state and telemetry from Edge Ingestion Service, updating connection status and heartbeat timestamp.",
)
def camera_heartbeat(
    camera_id: int,
    heartbeat_data: CameraHeartbeat,
    current_user: Annotated[User, Depends(require_operator)],
    db: Annotated[Session, Depends(get_db)],
) -> CameraResponse:
    camera = camera_service.get_camera_by_id(db=db, camera_id=camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with ID {camera_id} not found.",
        )
    updated = camera_service.record_camera_heartbeat(
        db=db, camera_id=camera_id, heartbeat_data=heartbeat_data
    )
    return CameraResponse.model_validate(updated)


@router.get(
    "/{camera_id}/snapshot",
    summary="Retrieve live JPEG camera snapshot",
    description="Fetch a fresh decoded JPEG frame from the Edge Ingestion Service buffer. Enforces location RBAC and verifies active status without opening a duplicate RTSP connection.",
    responses={
        200: {"content": {"image/jpeg": {}}, "description": "Fresh camera JPEG snapshot"},
        400: {"description": "Camera is deactivated"},
        403: {"description": "Location access denied"},
        404: {"description": "Camera not found"},
        503: {"description": "Camera stream is offline or edge service is unreachable"},
    },
)
async def get_camera_snapshot(
    camera_id: int,
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
    quality: Annotated[int, Query(ge=30, le=100, description="JPEG compression quality")] = 80,
    max_age: Annotated[float, Query(ge=0.5, le=30.0, description="Max frame age in seconds")] = 5.0,
):
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

    if not camera.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Camera '{camera.camera_code}' is deactivated. Activate camera to retrieve snapshots.",
        )

    jpeg_bytes, headers = await edge_bridge_service.get_snapshot(
        camera_id=camera_id,
        quality=quality,
        max_age=max_age,
    )

    return Response(content=jpeg_bytes, media_type="image/jpeg", headers=headers)


@router.get(
    "/{camera_id}/stream",
    summary="Live MJPEG video stream",
    description="Streams multipart/x-mixed-replace JPEG frames directly from the Edge Ingestion Service. Reuses decoded RTSP worker frames without duplicating connections.",
    responses={
        200: {"content": {"multipart/x-mixed-replace; boundary=frame": {}}, "description": "MJPEG video stream"},
        400: {"description": "Camera is deactivated"},
        403: {"description": "Location access denied"},
        404: {"description": "Camera not found"},
        429: {"description": "Maximum concurrent stream viewers exceeded"},
        503: {"description": "Camera stream is offline or edge service unreachable"},
    },
)
async def get_camera_stream(
    camera_id: int,
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
    fps: Annotated[int, Query(ge=1, le=30, description="Target frame rate")] = 15,
    quality: Annotated[int, Query(ge=30, le=95, description="JPEG quality")] = 75,
    max_frames: Annotated[int | None, Query(ge=1, description="Optional max frames limit")] = None,
):
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

    if not camera.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Camera '{camera.camera_code}' is deactivated. Activate camera to view live stream.",
        )

    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "X-Camera-ID": str(camera.id),
        "X-Camera-Code": camera.camera_code,
    }

    return StreamingResponse(
        edge_bridge_service.stream_mjpeg(camera_id=camera_id, fps=fps, quality=quality, max_frames=max_frames),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers=headers,
    )


