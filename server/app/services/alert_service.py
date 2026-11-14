import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.alert import Alert
from app.models.location import Location
from app.models.camera import Camera
from app.models.employee import Employee
from app.models.workstation_zone import WorkstationZone
from app.models.detection_event import DetectionEvent
from app.models.presence_session import PresenceSession
from app.models.guest_visit import GuestVisit
from app.models.user import User, user_locations
from app.schemas.alert import (
    AlertCreate,
    AlertUpdate,
    AlertResolveRequest,
    AlertResponse,
    AlertDetailResponse,
)
from app.core.permissions import SystemRole, has_minimum_role
from app.api.deps import has_location_access

logger = logging.getLogger(__name__)


def create_alert(
    db: Session,
    user: User,
    payload: AlertCreate,
) -> Alert:
    """
    Create an operational security or monitoring alert.
    - Role restriction: Requires operator or higher (super_admin, location_admin, operator).
    - Validates location authorization.
    - Validates that associated camera, employee, zone, event belong to the same location.
    - Initial status is 'open'.
    """
    if not has_minimum_role(user.system_role, SystemRole.OPERATOR.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or higher privileges required to create alerts.",
        )

    # 1. Validate Location
    loc = db.query(Location).filter(Location.id == payload.location_id).first()
    if loc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID {payload.location_id} not found.",
        )

    if not has_location_access(db=db, user=user, location_id=payload.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized for location ID {payload.location_id}.",
        )

    # 2. Validate Optional Associated Entities & Location Consistency
    if payload.camera_id is not None:
        cam = db.query(Camera).filter(Camera.id == payload.camera_id).first()
        if cam is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Camera with ID {payload.camera_id} not found.",
            )
        if cam.location_id != payload.location_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Camera {payload.camera_id} belongs to location {cam.location_id}, "
                    f"which does not match alert location {payload.location_id}."
                ),
            )

    if payload.employee_id is not None:
        emp = db.query(Employee).filter(Employee.id == payload.employee_id).first()
        if emp is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {payload.employee_id} not found.",
            )
        if emp.location_id != payload.location_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Employee {payload.employee_id} belongs to location {emp.location_id}, "
                    f"which does not match alert location {payload.location_id}."
                ),
            )

    if payload.workstation_zone_id is not None:
        zone = (
            db.query(WorkstationZone)
            .filter(WorkstationZone.id == payload.workstation_zone_id)
            .first()
        )
        if zone is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workstation zone with ID {payload.workstation_zone_id} not found.",
            )
        if zone.location_id != payload.location_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Workstation zone {payload.workstation_zone_id} belongs to location "
                    f"{zone.location_id}, which does not match alert location {payload.location_id}."
                ),
            )

    if payload.detection_event_id is not None:
        ev = (
            db.query(DetectionEvent)
            .filter(DetectionEvent.id == payload.detection_event_id)
            .first()
        )
        if ev is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Detection event with ID {payload.detection_event_id} not found.",
            )
        if ev.location_id != payload.location_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Detection event {payload.detection_event_id} belongs to location "
                    f"{ev.location_id}, which does not match alert location {payload.location_id}."
                ),
            )

    if payload.presence_session_id is not None:
        sess = (
            db.query(PresenceSession)
            .filter(PresenceSession.id == payload.presence_session_id)
            .first()
        )
        if sess is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Presence session with ID {payload.presence_session_id} not found.",
            )
        if sess.location_id != payload.location_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Presence session {payload.presence_session_id} belongs to location "
                    f"{sess.location_id}, which does not match alert location {payload.location_id}."
                ),
            )

    if payload.guest_visit_id is not None:
        visit = (
            db.query(GuestVisit)
            .filter(GuestVisit.id == payload.guest_visit_id)
            .first()
        )
        if visit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Guest visit with ID {payload.guest_visit_id} not found.",
            )
        if visit.location_id != payload.location_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Guest visit {payload.guest_visit_id} belongs to location "
                    f"{visit.location_id}, which does not match alert location {payload.location_id}."
                ),
            )

    alert = Alert(
        location_id=payload.location_id,
        camera_id=payload.camera_id,
        alert_type=payload.alert_type,
        severity=payload.severity,
        status="open",
        title=payload.title,
        description=payload.description,
        employee_id=payload.employee_id,
        workstation_zone_id=payload.workstation_zone_id,
        presence_session_id=payload.presence_session_id,
        guest_visit_id=payload.guest_visit_id,
        detection_event_id=payload.detection_event_id,
        triggered_at=payload.triggered_at or datetime.now(timezone.utc),
    )

    try:
        db.add(alert)
        db.commit()
        db.refresh(alert)
        logger.info(
            "Created alert ID %d (type=%s, sev=%s, loc=%d) by user %s",
            alert.id,
            alert.alert_type,
            alert.severity,
            alert.location_id,
            user.email,
        )
        return alert
    except Exception as e:
        db.rollback()
        logger.error("Failed to create alert: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create alert: {str(e)}",
        )


def list_alerts(
    db: Session,
    user: User,
    page: int = 1,
    size: int = 50,
    location_id: int | None = None,
    camera_id: int | None = None,
    employee_id: int | None = None,
    workstation_zone_id: int | None = None,
    alert_type: str | None = None,
    severity: str | None = None,
    status_filter: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> tuple[list[Alert], int]:
    """
    List alerts with pagination and filtering.
    Enforces location scoping: non-super_admin users can only view alerts for assigned locations.
    """
    query = db.query(Alert)

    # 1. Location Scoping
    if location_id is not None:
        if not has_location_access(db=db, user=user, location_id=location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorized for location ID {location_id}.",
            )
        query = query.filter(Alert.location_id == location_id)
    else:
        if user.system_role != SystemRole.SUPER_ADMIN.value:
            accessible_loc_ids = [
                r[0]
                for r in db.query(user_locations.c.location_id)
                .filter(user_locations.c.user_id == user.id)
                .all()
            ]
            query = query.filter(Alert.location_id.in_(accessible_loc_ids))

    # 2. Filters
    if camera_id is not None:
        query = query.filter(Alert.camera_id == camera_id)
    if employee_id is not None:
        query = query.filter(Alert.employee_id == employee_id)
    if workstation_zone_id is not None:
        query = query.filter(Alert.workstation_zone_id == workstation_zone_id)
    if alert_type is not None:
        query = query.filter(Alert.alert_type == alert_type)
    if severity is not None:
        query = query.filter(Alert.severity == severity)
    if status_filter is not None:
        query = query.filter(Alert.status == status_filter)
    if from_time is not None:
        query = query.filter(Alert.triggered_at >= from_time)
    if to_time is not None:
        query = query.filter(Alert.triggered_at <= to_time)

    total = query.count()
    offset = (page - 1) * size
    alerts = (
        query.order_by(Alert.triggered_at.desc(), Alert.id.desc())
        .offset(offset)
        .limit(size)
        .all()
    )
    return alerts, total


def get_alert_by_id(
    db: Session,
    user: User,
    alert_id: int,
) -> Alert:
    """Retrieve alert by ID, enforcing location authorization."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID {alert_id} not found.",
        )

    if not has_location_access(db=db, user=user, location_id=alert.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized for location ID {alert.location_id}.",
        )

    return alert


def acknowledge_alert(
    db: Session,
    user: User,
    alert_id: int,
) -> Alert:
    """
    Acknowledge an alert:
    - Requires operator or higher role.
    - Validates location access.
    - State transition: Only 'open' alerts can be acknowledged.
    - Sets status='acknowledged', acknowledged_by_user_id, acknowledged_at.
    """
    if not has_minimum_role(user.system_role, SystemRole.OPERATOR.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or higher privileges required to acknowledge alerts.",
        )

    alert = get_alert_by_id(db=db, user=user, alert_id=alert_id)

    # State transition check
    if alert.status == "acknowledged":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert is already in 'acknowledged' status.",
        )
    if alert.status in ("resolved", "false_positive"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot acknowledge alert: It is already closed with status '{alert.status}'.",
        )
    if alert.status != "open":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state transition: Cannot acknowledge alert with status '{alert.status}'.",
        )

    alert.status = "acknowledged"
    alert.acknowledged_by_user_id = user.id
    alert.acknowledged_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(alert)
    logger.info("Alert ID %d acknowledged by user %s (ID %d)", alert.id, user.email, user.id)
    return alert


def resolve_alert(
    db: Session,
    user: User,
    alert_id: int,
    payload: AlertResolveRequest,
) -> Alert:
    """
    Resolve an alert:
    - Requires operator or higher role.
    - Validates location access.
    - State transition: 'open' or 'acknowledged' -> 'resolved' or 'false_positive'.
    - If already resolved/false_positive: rejects transition with HTTP 400.
    - Sets resolved_by_user_id, resolved_at, resolution_notes.
    """
    if not has_minimum_role(user.system_role, SystemRole.OPERATOR.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or higher privileges required to resolve alerts.",
        )

    alert = get_alert_by_id(db=db, user=user, alert_id=alert_id)

    # State transition check
    if alert.status in ("resolved", "false_positive"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Alert is already closed with status '{alert.status}'.",
        )

    target_status = "false_positive" if payload.is_false_positive else "resolved"
    alert.status = target_status
    alert.resolved_by_user_id = user.id
    alert.resolved_at = datetime.now(timezone.utc)
    if payload.resolution_notes is not None:
        alert.resolution_notes = payload.resolution_notes

    db.commit()
    db.refresh(alert)
    logger.info(
        "Alert ID %d marked as %s by user %s (ID %d)",
        alert.id,
        target_status,
        user.email,
        user.id,
    )
    return alert


def update_alert(
    db: Session,
    user: User,
    alert_id: int,
    payload: AlertUpdate,
) -> Alert:
    """
    Update permitted alert fields (title, description, severity, resolution_notes).
    Protected fields (status, timestamps, audit user IDs) are rejected/ignored.
    """
    if not has_minimum_role(user.system_role, SystemRole.OPERATOR.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or higher privileges required to update alerts.",
        )

    alert = get_alert_by_id(db=db, user=user, alert_id=alert_id)

    if payload.title is not None:
        alert.title = payload.title
    if payload.description is not None:
        alert.description = payload.description
    if payload.severity is not None:
        alert.severity = payload.severity
    if payload.resolution_notes is not None:
        alert.resolution_notes = payload.resolution_notes

    db.commit()
    db.refresh(alert)
    logger.info("Alert ID %d updated by user %s", alert.id, user.email)
    return alert


def format_alert_detail(alert: Alert) -> AlertDetailResponse:
    """Format detailed alert response with joined relationship entities."""
    loc_name = alert.location.name if alert.location else None
    cam_name = alert.camera.name if alert.camera else None
    cam_code = alert.camera.camera_code if alert.camera else None
    emp_name = alert.employee.full_name if alert.employee else None
    emp_code = alert.employee.employee_code if alert.employee else None
    zone_name = alert.workstation_zone.zone_name if alert.workstation_zone else None
    ack_email = alert.acknowledged_by_user.email if alert.acknowledged_by_user else None
    res_email = alert.resolved_by_user.email if alert.resolved_by_user else None

    return AlertDetailResponse(
        id=alert.id,
        location_id=alert.location_id,
        camera_id=alert.camera_id,
        alert_type=alert.alert_type,
        severity=alert.severity,
        status=alert.status,
        title=alert.title,
        description=alert.description,
        employee_id=alert.employee_id,
        workstation_zone_id=alert.workstation_zone_id,
        presence_session_id=alert.presence_session_id,
        guest_visit_id=alert.guest_visit_id,
        detection_event_id=alert.detection_event_id,
        triggered_at=alert.triggered_at,
        acknowledged_by_user_id=alert.acknowledged_by_user_id,
        acknowledged_at=alert.acknowledged_at,
        resolved_by_user_id=alert.resolved_by_user_id,
        resolved_at=alert.resolved_at,
        resolution_notes=alert.resolution_notes,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
        location_name=loc_name,
        camera_name=cam_name,
        camera_code=cam_code,
        employee_name=emp_name,
        employee_code=emp_code,
        zone_name=zone_name,
        acknowledged_by_user_email=ack_email,
        resolved_by_user_email=res_email,
    )

