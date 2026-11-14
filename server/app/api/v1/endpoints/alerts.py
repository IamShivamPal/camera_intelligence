import math
from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.api.deps import require_operator, require_viewer
from app.schemas.common import PaginatedResponse
from app.schemas.alert import (
    AlertCreate,
    AlertUpdate,
    AlertResolveRequest,
    AlertResponse,
    AlertDetailResponse,
)
from app.services import alert_service

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[AlertResponse],
    summary="List alerts",
    description=(
        "Retrieve operational and security alerts with pagination and filtering. "
        "Scoped to authorized locations for non-super_admin users. Supports filtering by "
        "status, severity, alert type, location, camera, and employee."
    ),
)
def list_alerts(
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
    location_id: Annotated[int | None, Query(description="Filter by location ID")] = None,
    camera_id: Annotated[int | None, Query(description="Filter by camera ID")] = None,
    employee_id: Annotated[int | None, Query(description="Filter by employee ID")] = None,
    workstation_zone_id: Annotated[int | None, Query(description="Filter by workstation zone ID")] = None,
    alert_type: Annotated[str | None, Query(description="Filter by alert type")] = None,
    severity: Annotated[str | None, Query(description="Filter by severity (low, medium, high, critical)")] = None,
    status: Annotated[str | None, Query(description="Filter by status (open, acknowledged, resolved, false_positive)")] = None,
    from_time: Annotated[datetime | None, Query(description="Filter alerts after timestamp")] = None,
    to_time: Annotated[datetime | None, Query(description="Filter alerts before timestamp")] = None,
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 50,
) -> PaginatedResponse[AlertResponse]:
    alerts, total = alert_service.list_alerts(
        db=db,
        user=current_user,
        page=page,
        size=size,
        location_id=location_id,
        camera_id=camera_id,
        employee_id=employee_id,
        workstation_zone_id=workstation_zone_id,
        alert_type=alert_type,
        severity=severity,
        status_filter=status,
        from_time=from_time,
        to_time=to_time,
    )
    pages = math.ceil(total / size) if total > 0 else 0
    return PaginatedResponse(
        items=[AlertResponse.model_validate(a) for a in alerts],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.post(
    "",
    response_model=AlertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create security alert",
    description=(
        "Manually or programmatically create an operational or security alert. "
        "Requires operator or higher privileges. Validates location authorization and consistency."
    ),
)
def create_alert(
    payload: AlertCreate,
    current_user: Annotated[User, Depends(require_operator)],
    db: Annotated[Session, Depends(get_db)],
) -> AlertResponse:
    alert = alert_service.create_alert(
        db=db,
        user=current_user,
        payload=payload,
    )
    return AlertResponse.model_validate(alert)


@router.get(
    "/{alert_id}",
    response_model=AlertDetailResponse,
    summary="Get alert details",
    description="Retrieve complete alert details including associated location, camera, employee, zone, and triage history.",
)
def get_alert_details(
    alert_id: int,
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
) -> AlertDetailResponse:
    alert = alert_service.get_alert_by_id(
        db=db,
        user=current_user,
        alert_id=alert_id,
    )
    return alert_service.format_alert_detail(alert)


@router.post(
    "/{alert_id}/acknowledge",
    response_model=AlertResponse,
    summary="Acknowledge alert",
    description=(
        "Acknowledge an open alert. Records the acknowledging user ID and timestamp. "
        "Rejects transitions from closed or already acknowledged alerts."
    ),
)
def acknowledge_alert(
    alert_id: int,
    current_user: Annotated[User, Depends(require_operator)],
    db: Annotated[Session, Depends(get_db)],
) -> AlertResponse:
    alert = alert_service.acknowledge_alert(
        db=db,
        user=current_user,
        alert_id=alert_id,
    )
    return AlertResponse.model_validate(alert)


@router.post(
    "/{alert_id}/resolve",
    response_model=AlertResponse,
    summary="Resolve alert",
    description=(
        "Resolve an open or acknowledged alert. Supports setting status to 'resolved' "
        "or 'false_positive'. Records resolution notes, user ID, and timestamp."
    ),
)
def resolve_alert(
    alert_id: int,
    payload: AlertResolveRequest,
    current_user: Annotated[User, Depends(require_operator)],
    db: Annotated[Session, Depends(get_db)],
) -> AlertResponse:
    alert = alert_service.resolve_alert(
        db=db,
        user=current_user,
        alert_id=alert_id,
        payload=payload,
    )
    return AlertResponse.model_validate(alert)


@router.patch(
    "/{alert_id}",
    response_model=AlertResponse,
    summary="Update alert metadata",
    description=(
        "Update permitted non-protected alert fields (title, description, severity, resolution_notes). "
        "Status transitions must use dedicated acknowledge or resolve endpoints."
    ),
)
def update_alert(
    alert_id: int,
    payload: AlertUpdate,
    current_user: Annotated[User, Depends(require_operator)],
    db: Annotated[Session, Depends(get_db)],
) -> AlertResponse:
    alert = alert_service.update_alert(
        db=db,
        user=current_user,
        alert_id=alert_id,
        payload=payload,
    )
    return AlertResponse.model_validate(alert)
