import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.department import Department
from app.models.location import Location
from app.models.employee import Employee
from app.models.user import User, user_locations
from app.schemas.department import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from app.core.permissions import SystemRole
from app.api.deps import has_location_access

logger = logging.getLogger(__name__)


def list_accessible_departments(
    db: Session,
    user: User,
    location_id: int | None = None,
    is_active: bool | None = None,
) -> list[Department]:
    """
    List departments accessible to the user.
    - If location_id is provided, verify user access first.
    - If location_id is None, super_admin sees all; others only see departments
      in their assigned locations.
    """
    if location_id is not None:
        if not has_location_access(db=db, user=user, location_id=location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorized for location ID {location_id}.",
            )
        query = db.query(Department).filter(Department.location_id == location_id)
    else:
        if user.system_role == SystemRole.SUPER_ADMIN.value:
            query = db.query(Department)
        else:
            accessible_location_ids = [
                row[0]
                for row in db.query(user_locations.c.location_id)
                .filter(user_locations.c.user_id == user.id)
                .all()
            ]
            query = db.query(Department).filter(Department.location_id.in_(accessible_location_ids))

    if is_active is not None:
        query = query.filter(Department.is_active == is_active)

    return query.order_by(Department.location_id.asc(), Department.name.asc()).all()


def get_department_by_id(db: Session, department_id: int) -> Department | None:
    """Retrieve department by primary key."""
    return db.query(Department).filter(Department.id == department_id).first()


def format_department_response(db: Session, department: Department) -> DepartmentResponse:
    """Format Department into DepartmentResponse including employee count."""
    emp_count = (
        db.query(func.count(Employee.id))
        .filter(Employee.department_id == department.id)
        .scalar()
        or 0
    )
    return DepartmentResponse(
        id=department.id,
        location_id=department.location_id,
        name=department.name,
        code=department.code,
        is_active=department.is_active,
        created_at=department.created_at,
        updated_at=department.updated_at,
        employee_count=emp_count,
    )


def create_department(db: Session, data: DepartmentCreate) -> Department:
    """
    Create department within a location.
    Enforces uniqueness of name and code within that specific location.
    """
    # Verify location exists
    location = db.query(Location).filter(Location.id == data.location_id).first()
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID {data.location_id} not found.",
        )

    clean_name = data.name.strip()
    clean_code = data.code.strip() if data.code else None

    # Check unique name within location
    existing_name = (
        db.query(Department)
        .filter(
            Department.location_id == data.location_id,
            func.lower(Department.name) == clean_name.lower(),
        )
        .first()
    )
    if existing_name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Department with name '{clean_name}' already exists in location ID {data.location_id}.",
        )

    # Check unique code within location
    if clean_code:
        existing_code = (
            db.query(Department)
            .filter(
                Department.location_id == data.location_id,
                func.lower(Department.code) == clean_code.lower(),
            )
            .first()
        )
        if existing_code:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Department with code '{clean_code}' already exists in location ID {data.location_id}.",
            )

    department = Department(
        location_id=data.location_id,
        name=clean_name,
        code=clean_code,
        is_active=data.is_active,
    )
    db.add(department)
    db.commit()
    db.refresh(department)
    logger.info("Created department '%s' in location %d (ID %d)", department.name, department.location_id, department.id)
    return department


def update_department(db: Session, department: Department, data: DepartmentUpdate) -> Department:
    """
    Update department fields.
    Enforces uniqueness of name and code within the location.
    """
    if data.name is not None:
        clean_name = data.name.strip()
        if clean_name.lower() != department.name.lower():
            existing = (
                db.query(Department)
                .filter(
                    Department.location_id == department.location_id,
                    func.lower(Department.name) == clean_name.lower(),
                    Department.id != department.id,
                )
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Department with name '{clean_name}' already exists in location ID {department.location_id}.",
                )
        department.name = clean_name

    if data.code is not None:
        clean_code = data.code.strip() if data.code else None
        if clean_code and (department.code is None or clean_code.lower() != department.code.lower()):
            existing = (
                db.query(Department)
                .filter(
                    Department.location_id == department.location_id,
                    func.lower(Department.code) == clean_code.lower(),
                    Department.id != department.id,
                )
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Department with code '{clean_code}' already exists in location ID {department.location_id}.",
                )
        department.code = clean_code

    if data.is_active is not None:
        department.is_active = data.is_active

    db.commit()
    db.refresh(department)
    logger.info("Updated department '%s' (ID %d)", department.name, department.id)
    return department


def deactivate_department(db: Session, department: Department) -> Department:
    """Soft deactivate department."""
    department.is_active = False
    db.commit()
    db.refresh(department)
    logger.info("Deactivated department '%s' (ID %d)", department.name, department.id)
    return department

