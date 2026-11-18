import math
from datetime import datetime
from typing import Annotated, Any
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.api.deps import require_operator, require_viewer
from app.schemas.common import PaginatedResponse
from app.schemas.detection_event import (
    DetectionEventCreate,
    DetectionEventResponse,
    DetectionEventDetailResponse,
)
from app.services import event_service

router = APIRouter()


@router.post(
    "",
    response_model=DetectionEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest detection event",
    description=(
        "Record an AI detection event from camera streams. Enforces location consistency "
        "between camera, employee, and workstation zone. Validates confidence score and event type. "
        "Ephemeral tracker IDs are accepted as stream telemetry but never treated as employee identities."
    ),
)
def ingest_event(
    payload: DetectionEventCreate,
    current_user: Annotated[User, Depends(require_operator)],
    db: Annotated[Session, Depends(get_db)],
) -> DetectionEventResponse:
    event = event_service.ingest_detection_event(
        db=db,
        user=current_user,
        payload=payload,
    )
    return DetectionEventResponse.model_validate(event)


@router.get(
    "",
    response_model=PaginatedResponse[DetectionEventResponse],
    summary="List detection events",
    description=(
        "Retrieve paginated detection telemetry events. Super admins see all locations; "
        "other users see only events within authorized locations. Supports filtering by camera, "
        "employee, zone, event type, tracker ID, and timestamp range."
    ),
)
def list_events(
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
    location_id: Annotated[int | None, Query(description="Filter by location ID")] = None,
    camera_id: Annotated[int | None, Query(description="Filter by camera ID")] = None,
    employee_id: Annotated[int | None, Query(description="Filter by employee ID")] = None,
    event_type: Annotated[str | None, Query(description="Filter by event type")] = None,
    workstation_zone_id: Annotated[int | None, Query(description="Filter by workstation zone ID")] = None,
    from_time: Annotated[datetime | None, Query(description="Filter events after this timestamp")] = None,
    to_time: Annotated[datetime | None, Query(description="Filter events before this timestamp")] = None,
    tracker_id: Annotated[str | None, Query(description="Filter by stream tracker ID")] = None,
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 50,
) -> PaginatedResponse[DetectionEventResponse]:
    events, total = event_service.list_detection_events(
        db=db,
        user=current_user,
        page=page,
        size=size,
        location_id=location_id,
        camera_id=camera_id,
        employee_id=employee_id,
        event_type=event_type,
        workstation_zone_id=workstation_zone_id,
        from_time=from_time,
        to_time=to_time,
        tracker_id=tracker_id,
    )
    pages = math.ceil(total / size) if total > 0 else 0
    return PaginatedResponse(
        items=[DetectionEventResponse.model_validate(e) for e in events],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get(
    "/{event_id}",
    response_model=DetectionEventDetailResponse,
    summary="Get detection event details",
    description="Retrieve comprehensive detection event telemetry including joined camera, employee, zone, and alert IDs.",
)
def get_event_details(
    event_id: int,
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
) -> DetectionEventDetailResponse:
    event = event_service.get_detection_event_by_id(
        db=db,
        user=current_user,
        event_id=event_id,
    )
    return event_service.format_detection_event_detail(event)


@router.post(
    "/reconcile-sessions",
    status_code=status.HTTP_200_OK,
    summary="Reconcile orphaned presence sessions",
    description="Scan and close open presence sessions associated with offline cameras or stale heartbeats.",
)
def reconcile_sessions(
    current_user: Annotated[User, Depends(require_operator)],
    db: Annotated[Session, Depends(get_db)],
    max_stale_seconds: Annotated[float, Query(ge=1.0, description="Session idle threshold in seconds")] = 900.0,
    offline_camera_grace_seconds: Annotated[float, Query(ge=1.0, description="Camera offline grace period in seconds")] = 60.0,
    location_id: Annotated[int | None, Query(description="Filter reconciliation by location ID")] = None,
    camera_id: Annotated[int | None, Query(description="Filter reconciliation by camera ID")] = None,
) -> dict[str, Any]:
    closed = event_service.reconcile_stale_presence_sessions(
        db=db,
        max_stale_seconds=max_stale_seconds,
        offline_camera_grace_seconds=offline_camera_grace_seconds,
        location_id=location_id,
        camera_id=camera_id,
    )
    return {
        "status": "success",
        "reconciled_sessions_count": len(closed),
        "reconciled_session_ids": [s.id for s in closed],
    }
