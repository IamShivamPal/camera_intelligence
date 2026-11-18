import logging
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.camera import Camera
from app.models.location import Location
from app.models.workstation_zone import WorkstationZone
from app.models.detection_event import DetectionEvent
from app.models.alert import Alert
from app.models.user import User, user_locations
from app.schemas.camera import (
    CameraCreate,
    CameraUpdate,
    CameraResponse,
    CameraDetailResponse,
    WorkstationZoneSummary,
    CameraHeartbeat,
    CameraHeartbeatBatch,
)
from app.core.permissions import SystemRole, has_minimum_role
from app.api.deps import has_location_access

logger = logging.getLogger(__name__)


def list_cameras(
    db: Session,
    user: User,
    page: int = 1,
    size: int = 20,
    location_id: int | None = None,
    camera_role: str | None = None,
    stream_type: str | None = None,
    connection_status: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> tuple[list[Camera], int]:
    """
    List cameras accessible to current user with pagination and filters.
    - Scoping: super_admin has global view; other roles can only see cameras in their assigned locations.
    - Filters: location_id, camera_role, stream_type, connection_status, is_active, and search.
    """
    query = db.query(Camera)

    # 1. Location-based authorization & filter
    if location_id is not None:
        if not has_location_access(db=db, user=user, location_id=location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorized for location ID {location_id}.",
            )
        query = query.filter(Camera.location_id == location_id)
    else:
        if user.system_role != SystemRole.SUPER_ADMIN.value:
            accessible_location_ids = [
                row[0]
                for row in db.query(user_locations.c.location_id)
                .filter(user_locations.c.user_id == user.id)
                .all()
            ]
            query = query.filter(Camera.location_id.in_(accessible_location_ids))

    # 2. Camera role filter
    if camera_role is not None:
        query = query.filter(Camera.camera_role == camera_role)

    # 3. Stream type filter
    if stream_type is not None:
        query = query.filter(Camera.stream_type == stream_type)

    # 4. Connection status filter
    if connection_status is not None:
        query = query.filter(Camera.connection_status == connection_status)

    # 5. Active status filter
    if is_active is not None:
        query = query.filter(Camera.is_active == is_active)

    # 6. Search filter (camera name or code)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Camera.name.ilike(term),
                Camera.camera_code.ilike(term),
            )
        )

    total = query.count()
    offset = (page - 1) * size
    items = (
        query.order_by(Camera.created_at.desc(), Camera.id.desc())
        .offset(offset)
        .limit(size)
        .all()
    )

    return items, total


def get_camera_by_id(db: Session, camera_id: int) -> Camera | None:
    """Retrieve camera by primary key."""
    return db.query(Camera).filter(Camera.id == camera_id).first()


def format_camera_detail(db: Session, camera: Camera) -> CameraDetailResponse:
    """Format Camera into CameraDetailResponse, including safe zone summaries and event counts."""
    event_count = (
        db.query(func.count(DetectionEvent.id))
        .filter(DetectionEvent.camera_id == camera.id)
        .scalar()
        or 0
    )
    alert_count = (
        db.query(func.count(Alert.id))
        .filter(Alert.camera_id == camera.id)
        .scalar()
        or 0
    )

    zone_summaries = [
        WorkstationZoneSummary(
            id=z.id,
            zone_code=z.zone_code,
            name=z.name,
            location_id=z.location_id,
            camera_id=z.camera_id,
            is_active=z.is_active,
        )
        for z in camera.workstation_zones
    ]

    return CameraDetailResponse(
        id=camera.id,
        camera_code=camera.camera_code,
        name=camera.name,
        location_id=camera.location_id,
        camera_role=camera.camera_role,
        stream_type=camera.stream_type,
        stream_secret_ref=camera.stream_secret_ref,
        connection_status=camera.connection_status,
        last_heartbeat_at=camera.last_heartbeat_at,
        is_active=camera.is_active,
        created_at=camera.created_at,
        updated_at=camera.updated_at,
        location_name=camera.location.name if camera.location else None,
        workstation_zones=zone_summaries,
        detection_event_count=event_count,
        alert_count=alert_count,
    )


def create_camera(
    db: Session,
    data: CameraCreate,
    current_user: User,
) -> Camera:
    """
    Create a new camera record with full validation:
    - Validates location existence.
    - Validates user authorization to manage cameras in target location.
    - Validates uniqueness of camera_code.
    - Validates safe stream_secret_ref (never logs or accepts raw inline passwords).
    """
    if not has_minimum_role(current_user.system_role, SystemRole.LOCATION_ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location administrative privileges required to create cameras.",
        )

    # 1. Verify location exists
    location = db.query(Location).filter(Location.id == data.location_id).first()
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID {data.location_id} not found.",
        )

    # 2. Check location authorization
    if not has_location_access(db=db, user=current_user, location_id=data.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized to create cameras in location ID {data.location_id}.",
        )

    # 3. Check unique camera_code
    clean_code = data.camera_code.strip()
    existing = (
        db.query(Camera)
        .filter(func.lower(Camera.camera_code) == clean_code.lower())
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Camera code '{clean_code}' is already assigned to another camera.",
        )

    camera = Camera(
        name=data.name.strip(),
        camera_code=clean_code,
        location_id=data.location_id,
        camera_role=data.camera_role,
        stream_type=data.stream_type,
        stream_secret_ref=data.stream_secret_ref,
        connection_status=data.connection_status,
        is_active=data.is_active,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    logger.info(
        "Created camera '%s' (code=%s, location_id=%d, id=%d, has_secret_ref=%s)",
        camera.name,
        camera.camera_code,
        camera.location_id,
        camera.id,
        bool(camera.stream_secret_ref),
    )
    return camera


def update_camera(
    db: Session,
    camera: Camera,
    data: CameraUpdate,
    current_user: User,
) -> Camera:
    """
    Update camera configuration:
    - Enforces location authorization for current and target location.
    - Enforces uniqueness if camera_code is modified.
    - Validates workstation zone consistency if moving camera between locations.
    """
    if not has_minimum_role(current_user.system_role, SystemRole.LOCATION_ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location administrative privileges required to update cameras.",
        )

    # 1. Verify caller access to camera's current location
    if not has_location_access(db=db, user=current_user, location_id=camera.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized to update cameras at location ID {camera.location_id}.",
        )

    # 2. Validate camera_code uniqueness if modified
    if data.camera_code is not None:
        clean_code = data.camera_code.strip()
        if clean_code.lower() != camera.camera_code.lower():
            existing = (
                db.query(Camera)
                .filter(func.lower(Camera.camera_code) == clean_code.lower(), Camera.id != camera.id)
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Camera code '{clean_code}' is already assigned to another camera.",
                )
            camera.camera_code = clean_code

    # 3. Validate location transfer if modified
    if data.location_id is not None and data.location_id != camera.location_id:
        target_loc = db.query(Location).filter(Location.id == data.location_id).first()
        if not target_loc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Location with ID {data.location_id} not found.",
            )
        if not has_location_access(db=db, user=current_user, location_id=data.location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorized for new location ID {data.location_id}.",
            )
        # Check workstation zone consistency
        if len(camera.workstation_zones) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot move camera to a different location while {len(camera.workstation_zones)} "
                    "workstation zone(s) are attached. Reassign or remove zones first."
                ),
            )
        camera.location_id = data.location_id

    if data.name is not None:
        camera.name = data.name.strip()

    if data.camera_role is not None:
        camera.camera_role = data.camera_role

    if data.stream_type is not None:
        camera.stream_type = data.stream_type

    if data.stream_secret_ref is not None:
        camera.stream_secret_ref = data.stream_secret_ref

    if data.connection_status is not None:
        camera.connection_status = data.connection_status

    if data.is_active is not None:
        camera.is_active = data.is_active

    db.commit()
    db.refresh(camera)
    logger.info("Updated camera '%s' (ID %d)", camera.camera_code, camera.id)
    return camera


def deactivate_camera(
    db: Session,
    camera: Camera,
    current_user: User,
) -> Camera:
    """Soft-deactivate a camera (is_active = False)."""
    if not has_minimum_role(current_user.system_role, SystemRole.LOCATION_ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location administrative privileges required to deactivate cameras.",
        )

    if not has_location_access(db=db, user=current_user, location_id=camera.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized to deactivate cameras at location ID {camera.location_id}.",
        )

    camera.is_active = False
    db.commit()
    db.refresh(camera)
    logger.info("Deactivated camera '%s' (ID %d)", camera.camera_code, camera.id)
    return camera


def associate_workstation_zone(
    db: Session,
    camera: Camera,
    zone_id: int,
    current_user: User,
) -> WorkstationZone:
    """
    Associate an existing workstation zone with this camera.
    Enforces location consistency: camera and workstation zone MUST belong to the same location.
    """
    if not has_minimum_role(current_user.system_role, SystemRole.LOCATION_ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location administrative privileges required to associate workstation zones.",
        )

    if not has_location_access(db=db, user=current_user, location_id=camera.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized for camera location ID {camera.location_id}.",
        )

    zone = db.query(WorkstationZone).filter(WorkstationZone.id == zone_id).first()
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workstation zone with ID {zone_id} not found.",
        )

    # Location consistency validation
    if zone.location_id != camera.location_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Workstation zone location ID ({zone.location_id}) does not match "
                f"camera location ID ({camera.location_id}). Both must reside in the same location."
            ),
        )

    zone.camera_id = camera.id
    db.commit()
    db.refresh(zone)
    db.refresh(camera)
    logger.info(
        "Associated workstation zone '%s' (ID %d) to camera '%s' (ID %d)",
        zone.zone_code,
        zone.id,
        camera.camera_code,
        camera.id,
    )
    return zone


def record_camera_heartbeat(
    db: Session,
    camera_id: int,
    heartbeat_data: CameraHeartbeat,
) -> Camera:
    """Update camera connection status and last_heartbeat_at timestamp."""
    camera = get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with ID {camera_id} not found.",
        )
    camera.connection_status = heartbeat_data.connection_status
    camera.last_heartbeat_at = func.now()
    db.commit()
    db.refresh(camera)

    if camera.connection_status in ("offline", "unknown"):
        try:
            from app.services.event_service import reconcile_stale_presence_sessions
            reconcile_stale_presence_sessions(db, camera_id=camera.id, offline_camera_grace_seconds=60.0)
        except Exception as e:
            logger.debug("Error during camera heartbeat session reconciliation: %s", e)

    return camera


def record_batch_heartbeats(
    db: Session,
    batch_data: CameraHeartbeatBatch,
) -> int:
    """Batch update multiple cameras' connection status and last_heartbeat_at timestamp."""
    updated_count = 0
    now_expr = func.now()
    offline_cam_ids = []
    for item in batch_data.items:
        cam = db.query(Camera).filter(Camera.id == item.camera_id).first()
        if cam:
            cam.connection_status = item.connection_status
            cam.last_heartbeat_at = now_expr
            updated_count += 1
            if item.connection_status in ("offline", "unknown"):
                offline_cam_ids.append(cam.id)
    if updated_count > 0:
        db.commit()
        if offline_cam_ids:
            try:
                from app.services.event_service import reconcile_stale_presence_sessions
                for cid in offline_cam_ids:
                    reconcile_stale_presence_sessions(db, camera_id=cid, offline_camera_grace_seconds=60.0)
            except Exception as e:
                logger.debug("Error during batch heartbeat session reconciliation: %s", e)
    return updated_count

