import logging
from datetime import datetime, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.detection_event import DetectionEvent
from app.models.camera import Camera
from app.models.employee import Employee
from app.models.workstation_zone import WorkstationZone
from app.models.presence_session import PresenceSession
from app.models.guest_visit import GuestVisit
from app.models.alert import Alert
from app.models.user import User, user_locations
from app.schemas.detection_event import (
    DetectionEventCreate,
    DetectionEventResponse,
    DetectionEventDetailResponse,
)
from app.core.permissions import SystemRole, has_minimum_role
from app.api.deps import has_location_access

logger = logging.getLogger(__name__)


def process_presence_on_event(
    db: Session,
    event: DetectionEvent,
    camera: Camera,
) -> PresenceSession | None:
    """
    Evaluate presence session lifecycle for recognized employees:
    1. Facility presence session on entry/exit cameras.
    2. Workstation presence session on workstation zone events.
    Never creates sessions from ambiguous detections or unknown persons.
    """
    if event.employee_id is None:
        return None

    # Case 1: Entry/Exit camera observation
    if camera.camera_role == "entry_exit" and event.event_type == "employee_recognized":
        open_session = (
            db.query(PresenceSession)
            .filter(
                PresenceSession.employee_id == event.employee_id,
                PresenceSession.location_id == event.location_id,
                PresenceSession.session_type == "facility",
                PresenceSession.ended_at.is_(None),
            )
            .first()
        )
        if open_session is None:
            new_session = PresenceSession(
                employee_id=event.employee_id,
                location_id=event.location_id,
                entry_camera_id=event.camera_id,
                session_type="facility",
                status="active",
                started_at=event.occurred_at,
                last_seen_at=event.occurred_at,
                active_seconds=0,
                idle_seconds=0,
                is_after_hours=False,
            )
            db.add(new_session)
            db.flush()
            event.presence_session_id = new_session.id
            return new_session
        else:
            if event.occurred_at > open_session.last_seen_at:
                open_session.last_seen_at = event.occurred_at
            event.presence_session_id = open_session.id
            return open_session

    # Case 2: Workstation zone active/idle events
    if event.workstation_zone_id is not None and event.event_type in (
        "workstation_active",
        "workstation_idle",
    ):
        ws_session = (
            db.query(PresenceSession)
            .filter(
                PresenceSession.employee_id == event.employee_id,
                PresenceSession.workstation_zone_id == event.workstation_zone_id,
                PresenceSession.session_type == "workstation",
                PresenceSession.ended_at.is_(None),
            )
            .first()
        )
        if ws_session is None and event.event_type == "workstation_active":
            new_ws = PresenceSession(
                employee_id=event.employee_id,
                location_id=event.location_id,
                entry_camera_id=event.camera_id,
                workstation_zone_id=event.workstation_zone_id,
                session_type="workstation",
                status="active",
                started_at=event.occurred_at,
                last_seen_at=event.occurred_at,
                active_seconds=0,
                idle_seconds=0,
                is_after_hours=False,
            )
            db.add(new_ws)
            db.flush()
            event.presence_session_id = new_ws.id
            return new_ws
        elif ws_session is not None:
            if event.occurred_at > ws_session.last_seen_at:
                ws_session.last_seen_at = event.occurred_at
            ws_session.status = "active" if event.event_type == "workstation_active" else "idle"
            event.presence_session_id = ws_session.id
            return ws_session

    return None


def process_guest_on_event(
    db: Session,
    event: DetectionEvent,
    camera: Camera,
) -> GuestVisit | None:
    """
    Process guest lifecycle for guest entry and exit events with explicit codes.
    Does not create unverified sessions for generic unknown persons.
    """
    meta = event.metadata_json or {}
    guest_code = meta.get("guest_code")

    if event.event_type == "guest_entry":
        if guest_code:
            code_str = str(guest_code).strip()
            existing = (
                db.query(GuestVisit)
                .filter(GuestVisit.guest_code == code_str)
                .first()
            )
            if existing is None:
                new_visit = GuestVisit(
                    location_id=event.location_id,
                    guest_code=code_str,
                    guest_name=meta.get("guest_name"),
                    entry_camera_id=event.camera_id,
                    host_employee_id=meta.get("host_employee_id"),
                    status="inside",
                    entered_at=event.occurred_at,
                    last_seen_at=event.occurred_at,
                    notes=meta.get("notes"),
                )
                db.add(new_visit)
                db.flush()
                event.guest_visit_id = new_visit.id
                return new_visit
            elif existing.exited_at is None:
                if event.occurred_at > existing.last_seen_at:
                    existing.last_seen_at = event.occurred_at
                event.guest_visit_id = existing.id
                return existing

    elif event.event_type == "guest_exit":
        target_visit: GuestVisit | None = None
        if event.guest_visit_id is not None:
            target_visit = (
                db.query(GuestVisit)
                .filter(GuestVisit.id == event.guest_visit_id)
                .first()
            )
        elif guest_code:
            code_str = str(guest_code).strip()
            target_visit = (
                db.query(GuestVisit)
                .filter(
                    GuestVisit.guest_code == code_str,
                    GuestVisit.exited_at.is_(None),
                )
                .first()
            )

        if target_visit is not None and target_visit.exited_at is None:
            target_visit.status = "exited"
            target_visit.exited_at = event.occurred_at
            if event.occurred_at > target_visit.last_seen_at:
                target_visit.last_seen_at = event.occurred_at
            target_visit.exit_camera_id = event.camera_id
            event.guest_visit_id = target_visit.id
            return target_visit

    return None


def trigger_automated_alert_on_event(
    db: Session,
    event: DetectionEvent,
    camera: Camera,
) -> Alert | None:
    """
    Trigger operational security alerts for critical anomalies:
    - after_hours_intrusion -> Critical security alert
    - after_hours_employee -> Medium operational alert
    """
    if event.event_type == "after_hours_intrusion":
        alert = Alert(
            location_id=event.location_id,
            camera_id=event.camera_id,
            alert_type="after_hours_intrusion",
            severity="critical",
            status="open",
            title=f"After-Hours Intrusion Detected on Camera {camera.name}",
            description=(
                f"Unauthorized motion/person detected outside scheduled operating hours "
                f"on camera '{camera.name}' ({camera.camera_code})."
            ),
            triggered_at=event.occurred_at,
            detection_event=event,
        )
        db.add(alert)
        db.flush()
        return alert

    if event.event_type == "after_hours_employee":
        alert = Alert(
            location_id=event.location_id,
            camera_id=event.camera_id,
            employee_id=event.employee_id,
            alert_type="after_hours_employee",
            severity="medium",
            status="open",
            title=f"After-Hours Employee Presence on Camera {camera.name}",
            description=(
                f"Employee ID {event.employee_id} observed outside regular scheduled "
                f"shift hours on camera '{camera.name}' ({camera.camera_code})."
            ),
            triggered_at=event.occurred_at,
            detection_event=event,
        )
        db.add(alert)
        db.flush()
        return alert

    return None


def ingest_detection_event(
    db: Session,
    user: User,
    payload: DetectionEventCreate,
) -> DetectionEvent:
    """
    Ingest a detection event from AI Engine or client.
    - Validates camera existence and active status.
    - Enforces location consistency for camera, employee, and workstation zone.
    - Validates user permissions for the camera's location.
    - Triggers presence and guest lifecycle operations safely.
    - Generates automated security alerts where warranted.
    - Preserves historical event records (append-only).
    """
    # 1. Check Role Authorization (operator or higher)
    if not has_minimum_role(user.system_role, SystemRole.OPERATOR.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or higher privileges required to ingest detection events.",
        )

    # 2. Validate Camera
    camera = db.query(Camera).filter(Camera.id == payload.camera_id).first()
    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with ID {payload.camera_id} not found.",
        )
    if not camera.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Camera with ID {payload.camera_id} is inactive.",
        )

    loc_id = camera.location_id

    # 2. Location Scoping & Consistency
    if payload.location_id is not None and payload.location_id != loc_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Location ID {payload.location_id} does not match camera location ID {loc_id}."
            ),
        )

    if not has_location_access(db=db, user=user, location_id=loc_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized for location ID {loc_id}.",
        )

    # 3. Validate Employee (if provided)
    if payload.employee_id is not None:
        employee = db.query(Employee).filter(Employee.id == payload.employee_id).first()
        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {payload.employee_id} not found.",
            )
        if employee.location_id != loc_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Employee ID {payload.employee_id} belongs to location ID {employee.location_id}, "
                    f"which does not match camera location ID {loc_id}."
                ),
            )
        if not employee.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Employee ID {payload.employee_id} is inactive.",
            )

    # 4. Validate Workstation Zone (if provided)
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
        if zone.location_id != loc_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Workstation zone ID {payload.workstation_zone_id} belongs to location ID "
                    f"{zone.location_id}, which does not match camera location ID {loc_id}."
                ),
            )
        if not zone.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Workstation zone ID {payload.workstation_zone_id} is inactive.",
            )

    # 5. Validate Presence Session (if directly provided)
    if payload.presence_session_id is not None:
        session = (
            db.query(PresenceSession)
            .filter(PresenceSession.id == payload.presence_session_id)
            .first()
        )
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Presence session with ID {payload.presence_session_id} not found.",
            )
        if session.location_id != loc_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Presence session ID {payload.presence_session_id} belongs to location ID "
                    f"{session.location_id}, which does not match camera location ID {loc_id}."
                ),
            )

    # 6. Validate Guest Visit (if directly provided)
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
        if visit.location_id != loc_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Guest visit ID {payload.guest_visit_id} belongs to location ID "
                    f"{visit.location_id}, which does not match camera location ID {loc_id}."
                ),
            )

    event_time = payload.occurred_at or datetime.now(timezone.utc)

    # 7. Create DetectionEvent record
    event = DetectionEvent(
        location_id=loc_id,
        camera_id=camera.id,
        event_type=payload.event_type,
        occurred_at=event_time,
        employee_id=payload.employee_id,
        workstation_zone_id=payload.workstation_zone_id,
        presence_session_id=payload.presence_session_id,
        guest_visit_id=payload.guest_visit_id,
        confidence=payload.confidence,
        tracker_id=payload.tracker_id,
        snapshot_ref=payload.snapshot_ref,
        metadata_json=payload.metadata_json,
    )
    db.add(event)
    db.flush()

    # 8. Lifecycle Transitions
    try:
        process_presence_on_event(db=db, event=event, camera=camera)
        process_guest_on_event(db=db, event=event, camera=camera)
        trigger_automated_alert_on_event(db=db, event=event, camera=camera)

        db.commit()
        db.refresh(event)
        logger.info(
            "Ingested detection event ID %d (type=%s, camera=%d, loc=%d)",
            event.id,
            event.event_type,
            event.camera_id,
            event.location_id,
        )
        return event
    except Exception as e:
        db.rollback()
        logger.error("Failed to ingest detection event: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to record detection event: {str(e)}",
        )


def list_detection_events(
    db: Session,
    user: User,
    page: int = 1,
    size: int = 50,
    location_id: int | None = None,
    camera_id: int | None = None,
    employee_id: int | None = None,
    event_type: str | None = None,
    workstation_zone_id: int | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    tracker_id: str | None = None,
) -> tuple[list[DetectionEvent], int]:
    """
    List detection events with pagination and filters.
    Enforces location scoping: non-super_admin users can only view events for assigned locations.
    """
    query = db.query(DetectionEvent)

    # 1. Location Scoping
    if location_id is not None:
        if not has_location_access(db=db, user=user, location_id=location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorized for location ID {location_id}.",
            )
        query = query.filter(DetectionEvent.location_id == location_id)
    else:
        if user.system_role != SystemRole.SUPER_ADMIN.value:
            accessible_loc_ids = [
                r[0]
                for r in db.query(user_locations.c.location_id)
                .filter(user_locations.c.user_id == user.id)
                .all()
            ]
            query = query.filter(DetectionEvent.location_id.in_(accessible_loc_ids))

    # 2. Filters
    if camera_id is not None:
        query = query.filter(DetectionEvent.camera_id == camera_id)
    if employee_id is not None:
        query = query.filter(DetectionEvent.employee_id == employee_id)
    if event_type is not None:
        query = query.filter(DetectionEvent.event_type == event_type)
    if workstation_zone_id is not None:
        query = query.filter(DetectionEvent.workstation_zone_id == workstation_zone_id)
    if tracker_id is not None:
        query = query.filter(DetectionEvent.tracker_id == tracker_id)
    if from_time is not None:
        query = query.filter(DetectionEvent.occurred_at >= from_time)
    if to_time is not None:
        query = query.filter(DetectionEvent.occurred_at <= to_time)

    total = query.count()
    offset = (page - 1) * size
    events = (
        query.order_by(DetectionEvent.occurred_at.desc(), DetectionEvent.id.desc())
        .offset(offset)
        .limit(size)
        .all()
    )
    return events, total


def get_detection_event_by_id(
    db: Session,
    user: User,
    event_id: int,
) -> DetectionEvent:
    """Retrieve detection event by ID, enforcing location authorization."""
    event = db.query(DetectionEvent).filter(DetectionEvent.id == event_id).first()
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection event with ID {event_id} not found.",
        )

    if not has_location_access(db=db, user=user, location_id=event.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized for location ID {event.location_id}.",
        )

    return event


def format_detection_event_detail(event: DetectionEvent) -> DetectionEventDetailResponse:
    """Format full detection event response with joined relationship fields."""
    loc_name = event.location.name if event.location else None
    cam_name = event.camera.name if event.camera else None
    cam_code = event.camera.camera_code if event.camera else None
    emp_name = event.employee.full_name if event.employee else None
    emp_code = event.employee.employee_code if event.employee else None
    zone_name = event.workstation_zone.zone_name if event.workstation_zone else None
    alert_ids = [a.id for a in event.alerts] if event.alerts else []

    return DetectionEventDetailResponse(
        id=event.id,
        location_id=event.location_id,
        camera_id=event.camera_id,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        employee_id=event.employee_id,
        workstation_zone_id=event.workstation_zone_id,
        presence_session_id=event.presence_session_id,
        guest_visit_id=event.guest_visit_id,
        confidence=event.confidence,
        tracker_id=event.tracker_id,
        snapshot_ref=event.snapshot_ref,
        metadata_json=event.metadata_json,
        created_at=event.created_at,
        location_name=loc_name,
        camera_name=cam_name,
        camera_code=cam_code,
        employee_name=emp_name,
        employee_code=emp_code,
        zone_name=zone_name,
        alert_ids=alert_ids,
    )
