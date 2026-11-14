import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.location import Location
from app.models.department import Department
from app.models.employee import Employee
from app.models.camera import Camera
from app.models.user import User, user_locations
from app.schemas.location import LocationCreate, LocationUpdate, LocationDetailResponse, LocationResponse
from app.core.permissions import SystemRole

logger = logging.getLogger(__name__)


def list_accessible_locations(
    db: Session,
    user: User,
    is_active: bool | None = None,
) -> list[Location]:
    """
    List locations accessible to the current user.
    - super_admin sees all locations.
    - Other users only see locations explicitly assigned in user_locations.
    """
    if user.system_role == SystemRole.SUPER_ADMIN.value:
        query = db.query(Location)
    else:
        query = (
            db.query(Location)
            .join(user_locations, Location.id == user_locations.c.location_id)
            .filter(user_locations.c.user_id == user.id)
        )

    if is_active is not None:
        query = query.filter(Location.is_active == is_active)

    return query.order_by(Location.name.asc()).all()


def get_location_by_id(db: Session, location_id: int) -> Location | None:
    """Retrieve location by primary key."""
    return db.query(Location).filter(Location.id == location_id).first()


def get_location_detail_response(db: Session, location: Location) -> LocationDetailResponse:
    """Build a detailed location response including entity counts."""
    dept_count = db.query(func.count(Department.id)).filter(Department.location_id == location.id).scalar() or 0
    emp_count = db.query(func.count(Employee.id)).filter(Employee.location_id == location.id).scalar() or 0
    cam_count = db.query(func.count(Camera.id)).filter(Camera.location_id == location.id).scalar() or 0

    return LocationDetailResponse(
        id=location.id,
        name=location.name,
        address=location.address,
        timezone=location.timezone,
        is_active=location.is_active,
        created_at=location.created_at,
        updated_at=location.updated_at,
        department_count=dept_count,
        employee_count=emp_count,
        camera_count=cam_count,
    )


def create_location(db: Session, data: LocationCreate) -> Location:
    """Create a new location. Enforces unique location name."""
    clean_name = data.name.strip()
    existing = db.query(Location).filter(func.lower(Location.name) == clean_name.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A location with name '{clean_name}' already exists.",
        )

    location = Location(
        name=clean_name,
        address=data.address.strip() if data.address else None,
        timezone=data.timezone.strip() if data.timezone else "UTC",
        is_active=data.is_active,
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    logger.info("Created location '%s' (ID %d)", location.name, location.id)
    return location


def update_location(db: Session, location: Location, data: LocationUpdate) -> Location:
    """Update location fields. Enforces unique name if modified."""
    if data.name is not None:
        clean_name = data.name.strip()
        if clean_name.lower() != location.name.lower():
            existing = (
                db.query(Location)
                .filter(func.lower(Location.name) == clean_name.lower(), Location.id != location.id)
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A location with name '{clean_name}' already exists.",
                )
        location.name = clean_name

    if data.address is not None:
        location.address = data.address.strip() if data.address else None

    if data.timezone is not None:
        location.timezone = data.timezone.strip()

    if data.is_active is not None:
        location.is_active = data.is_active

    db.commit()
    db.refresh(location)
    logger.info("Updated location '%s' (ID %d)", location.name, location.id)
    return location


def deactivate_location(db: Session, location: Location) -> Location:
    """Soft deactivate location."""
    location.is_active = False
    db.commit()
    db.refresh(location)
    logger.info("Deactivated location '%s' (ID %d)", location.name, location.id)
    return location

