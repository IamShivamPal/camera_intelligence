import logging
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.workstation_zone import WorkstationZone
from app.models.location import Location
from app.models.camera import Camera
from app.models.employee import Employee
from app.models.department import Department
from app.models.user import User, user_locations
from app.schemas.workstation_zone import (
    WorkstationZoneCreate,
    WorkstationZoneUpdate,
    WorkstationZoneResponse,
    WorkstationZoneDetailResponse,
)
from app.core.permissions import SystemRole, has_minimum_role
from app.api.deps import has_location_access

logger = logging.getLogger(__name__)


def list_zones(
    db: Session,
    user: User,
    page: int = 1,
    size: int = 20,
    location_id: int | None = None,
    camera_id: int | None = None,
    assigned_employee_id: int | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> tuple[list[WorkstationZone], int]:
    """
    List workstation zones accessible to the user with pagination and filters.
    - Scoping: super_admin has global view; other roles can only see zones in assigned locations.
    - Filters: location_id, camera_id, assigned_employee_id, is_active, and search.
    """
    query = db.query(WorkstationZone)

    # 1. Location-based authorization & filter
    if location_id is not None:
        if not has_location_access(db=db, user=user, location_id=location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorized for location ID {location_id}.",
            )
        query = query.filter(WorkstationZone.location_id == location_id)
    else:
        if user.system_role != SystemRole.SUPER_ADMIN.value:
            accessible_location_ids = [
                row[0]
                for row in db.query(user_locations.c.location_id)
                .filter(user_locations.c.user_id == user.id)
                .all()
            ]
            query = query.filter(WorkstationZone.location_id.in_(accessible_location_ids))

    # 2. Camera filter
    if camera_id is not None:
        query = query.filter(WorkstationZone.camera_id == camera_id)

    # 3. Assigned employee filter
    if assigned_employee_id is not None:
        query = query.filter(WorkstationZone.assigned_employee_id == assigned_employee_id)

    # 4. Active status filter
    if is_active is not None:
        query = query.filter(WorkstationZone.is_active == is_active)

    # 5. Search filter (zone name or code)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                WorkstationZone.name.ilike(term),
                WorkstationZone.zone_code.ilike(term),
            )
        )

    total = query.count()
    offset = (page - 1) * size
    items = (
        query.order_by(WorkstationZone.created_at.desc(), WorkstationZone.id.desc())
        .offset(offset)
        .limit(size)
        .all()
    )

    return items, total


def get_zone_by_id(db: Session, zone_id: int) -> WorkstationZone | None:
    """Retrieve workstation zone by primary key."""
    return db.query(WorkstationZone).filter(WorkstationZone.id == zone_id).first()


def format_zone_detail(db: Session, zone: WorkstationZone) -> WorkstationZoneDetailResponse:
    """Format WorkstationZone into WorkstationZoneDetailResponse with relational context."""
    return WorkstationZoneDetailResponse(
        id=zone.id,
        zone_code=zone.zone_code,
        name=zone.name,
        location_id=zone.location_id,
        camera_id=zone.camera_id,
        polygon_points=zone.polygon_points,
        assigned_employee_id=zone.assigned_employee_id,
        department_id=zone.department_id,
        inactivity_threshold_seconds=zone.inactivity_threshold_seconds,
        is_active=zone.is_active,
        created_at=zone.created_at,
        updated_at=zone.updated_at,
        location_name=zone.location.name if zone.location else None,
        camera_name=zone.camera.name if zone.camera else None,
        camera_code=zone.camera.camera_code if zone.camera else None,
        assigned_employee_name=zone.assigned_employee.full_name if zone.assigned_employee else None,
        department_name=zone.department.name if zone.department else None,
    )


def create_zone(
    db: Session,
    data: WorkstationZoneCreate,
    current_user: User,
) -> WorkstationZone:
    """
    Create a new workstation zone with full validation:
    - Enforces location administrative authority.
    - Validates location existence and user authorization.
    - Validates camera existence and camera/zone location consistency.
    - Validates assigned employee and employee/zone location consistency.
    - Validates department and department/zone location consistency.
    - Enforces unique zone_code.
    - Validates positive inactivity threshold.
    """
    if not has_minimum_role(current_user.system_role, SystemRole.LOCATION_ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location administrative privileges required to create workstation zones.",
        )

    # 1. Location existence & authorization
    location = db.query(Location).filter(Location.id == data.location_id).first()
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID {data.location_id} not found.",
        )

    if not has_location_access(db=db, user=current_user, location_id=data.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized to create zones in location ID {data.location_id}.",
        )

    # 2. Camera existence & location consistency
    camera = db.query(Camera).filter(Camera.id == data.camera_id).first()
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with ID {data.camera_id} not found.",
        )
    if camera.location_id != data.location_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Camera location ID ({camera.location_id}) does not match zone location ID ({data.location_id}).",
        )

    # 3. Assigned employee existence & location consistency
    if data.assigned_employee_id is not None:
        emp = db.query(Employee).filter(Employee.id == data.assigned_employee_id).first()
        if not emp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {data.assigned_employee_id} not found.",
            )
        if emp.location_id != data.location_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Assigned employee location ID ({emp.location_id}) does not match zone location ID ({data.location_id}).",
            )

    # 4. Department existence & location consistency
    if data.department_id is not None:
        dept = db.query(Department).filter(Department.id == data.department_id).first()
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with ID {data.department_id} not found.",
            )
        if dept.location_id != data.location_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department location ID ({dept.location_id}) does not match zone location ID ({data.location_id}).",
            )

    # 5. Unique zone_code
    clean_code = data.zone_code.strip()
    existing = (
        db.query(WorkstationZone)
        .filter(func.lower(WorkstationZone.zone_code) == clean_code.lower())
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workstation zone code '{clean_code}' is already assigned to another zone.",
        )

    # 6. Inactivity threshold check
    if data.inactivity_threshold_seconds <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="inactivity_threshold_seconds must be positive.",
        )

    zone = WorkstationZone(
        zone_code=clean_code,
        name=data.name.strip(),
        location_id=data.location_id,
        camera_id=data.camera_id,
        polygon_points=data.polygon_points,
        assigned_employee_id=data.assigned_employee_id,
        department_id=data.department_id,
        inactivity_threshold_seconds=data.inactivity_threshold_seconds,
        is_active=data.is_active,
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    logger.info("Created workstation zone '%s' (ID %d, location_id=%d)", zone.zone_code, zone.id, zone.location_id)
    return zone


def update_zone(
    db: Session,
    zone: WorkstationZone,
    data: WorkstationZoneUpdate,
    current_user: User,
) -> WorkstationZone:
    """
    Update workstation zone attributes:
    - Enforces location administrative authority.
    - Validates unique zone_code if modified.
    - Enforces camera and employee location consistency.
    """
    if not has_minimum_role(current_user.system_role, SystemRole.LOCATION_ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location administrative privileges required to update workstation zones.",
        )

    if not has_location_access(db=db, user=current_user, location_id=zone.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized to update zones at location ID {zone.location_id}.",
        )

    # 1. Unique zone_code if changed
    if data.zone_code is not None:
        clean_code = data.zone_code.strip()
        if clean_code.lower() != zone.zone_code.lower():
            existing = (
                db.query(WorkstationZone)
                .filter(func.lower(WorkstationZone.zone_code) == clean_code.lower(), WorkstationZone.id != zone.id)
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Workstation zone code '{clean_code}' is already assigned to another zone.",
                )
            zone.zone_code = clean_code

    # 2. Camera location consistency
    if data.camera_id is not None:
        cam = db.query(Camera).filter(Camera.id == data.camera_id).first()
        if not cam:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Camera with ID {data.camera_id} not found.",
            )
        if cam.location_id != zone.location_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Camera location ID ({cam.location_id}) does not match zone location ID ({zone.location_id}).",
            )
        zone.camera_id = data.camera_id

    # 3. Employee location consistency
    if data.assigned_employee_id is not None:
        emp = db.query(Employee).filter(Employee.id == data.assigned_employee_id).first()
        if not emp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {data.assigned_employee_id} not found.",
            )
        if emp.location_id != zone.location_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Assigned employee location ID ({emp.location_id}) does not match zone location ID ({zone.location_id}).",
            )
        zone.assigned_employee_id = data.assigned_employee_id

    # 4. Department location consistency
    if data.department_id is not None:
        dept = db.query(Department).filter(Department.id == data.department_id).first()
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with ID {data.department_id} not found.",
            )
        if dept.location_id != zone.location_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department location ID ({dept.location_id}) does not match zone location ID ({zone.location_id}).",
            )
        zone.department_id = data.department_id

    if data.polygon_points is not None:
        zone.polygon_points = data.polygon_points

    if data.inactivity_threshold_seconds is not None:
        if data.inactivity_threshold_seconds <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="inactivity_threshold_seconds must be positive.",
            )
        zone.inactivity_threshold_seconds = data.inactivity_threshold_seconds

    if data.name is not None:
        zone.name = data.name.strip()

    if data.is_active is not None:
        zone.is_active = data.is_active

    db.commit()
    db.refresh(zone)
    logger.info("Updated workstation zone '%s' (ID %d)", zone.zone_code, zone.id)
    return zone


def deactivate_zone(
    db: Session,
    zone: WorkstationZone,
    current_user: User,
) -> WorkstationZone:
    """Soft-deactivate workstation zone (is_active = False)."""
    if not has_minimum_role(current_user.system_role, SystemRole.LOCATION_ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location administrative privileges required to deactivate workstation zones.",
        )

    if not has_location_access(db=db, user=current_user, location_id=zone.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized to deactivate zones at location ID {zone.location_id}.",
        )

    zone.is_active = False
    db.commit()
    db.refresh(zone)
    logger.info("Deactivated workstation zone '%s' (ID %d)", zone.zone_code, zone.id)
    return zone


def assign_employee_to_zone(
    db: Session,
    zone: WorkstationZone,
    employee_id: int,
    current_user: User,
) -> WorkstationZone:
    """
    Assign an employee to a workstation zone.
    Enforces location consistency: employee must belong to the same location as the zone.
    """
    if not has_minimum_role(current_user.system_role, SystemRole.LOCATION_ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location administrative privileges required to assign employees.",
        )

    if not has_location_access(db=db, user=current_user, location_id=zone.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized for zone location ID {zone.location_id}.",
        )

    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )

    if emp.location_id != zone.location_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Assigned employee location ID ({emp.location_id}) does not match "
                f"zone location ID ({zone.location_id}). Both must reside in the same location."
            ),
        )

    zone.assigned_employee_id = emp.id
    db.commit()
    db.refresh(zone)
    logger.info("Assigned employee ID %d to workstation zone ID %d", emp.id, zone.id)
    return zone


def remove_employee_from_zone(
    db: Session,
    zone: WorkstationZone,
    current_user: User,
) -> WorkstationZone:
    """Remove employee assignment from a workstation zone."""
    if not has_minimum_role(current_user.system_role, SystemRole.LOCATION_ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location administrative privileges required to unassign employees.",
        )

    if not has_location_access(db=db, user=current_user, location_id=zone.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized for zone location ID {zone.location_id}.",
        )

    zone.assigned_employee_id = None
    db.commit()
    db.refresh(zone)
    logger.info("Removed employee assignment from workstation zone ID %d", zone.id)
    return zone

