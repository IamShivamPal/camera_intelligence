import logging
import math
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.employee import Employee
from app.models.department import Department
from app.models.location import Location
from app.models.role import Role
from app.models.user import User, user_locations
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeResponse,
    EmployeeDetailResponse,
)
from app.schemas.role import RoleResponse
from app.core.permissions import SystemRole
from app.api.deps import has_location_access

logger = logging.getLogger(__name__)


def list_employees(
    db: Session,
    user: User,
    page: int = 1,
    size: int = 20,
    location_id: int | None = None,
    department_id: int | None = None,
    is_active: bool | None = None,
    enrollment_status: str | None = None,
    search: str | None = None,
) -> tuple[list[Employee], int]:
    """
    List employees with authorization scoping, pagination, and multi-field filtering.
    - Scoping: super_admin has global view; other roles can only see employees in their assigned locations.
    - Search: searches full_name, employee_code, and email.
    """
    query = db.query(Employee)

    # 1. Location-based authorization & filter
    if location_id is not None:
        if not has_location_access(db=db, user=user, location_id=location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorized for location ID {location_id}.",
            )
        query = query.filter(Employee.location_id == location_id)
    else:
        if user.system_role != SystemRole.SUPER_ADMIN.value:
            accessible_location_ids = [
                row[0]
                for row in db.query(user_locations.c.location_id)
                .filter(user_locations.c.user_id == user.id)
                .all()
            ]
            query = query.filter(Employee.location_id.in_(accessible_location_ids))

    # 2. Department filter
    if department_id is not None:
        query = query.filter(Employee.department_id == department_id)

    # 3. Active status filter
    if is_active is not None:
        query = query.filter(Employee.is_active == is_active)

    # 4. Enrollment status filter
    if enrollment_status is not None:
        query = query.filter(Employee.enrollment_status == enrollment_status)

    # 5. Text search filter
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Employee.full_name.ilike(term),
                Employee.employee_code.ilike(term),
                Employee.email.ilike(term),
            )
        )

    total = query.count()
    offset = (page - 1) * size
    items = (
        query.order_by(Employee.created_at.desc(), Employee.id.desc())
        .offset(offset)
        .limit(size)
        .all()
    )

    return items, total


def get_employee_by_id(db: Session, employee_id: int) -> Employee | None:
    """Retrieve employee by primary key."""
    return db.query(Employee).filter(Employee.id == employee_id).first()


def format_employee_detail(employee: Employee) -> EmployeeDetailResponse:
    """Format Employee into EmployeeDetailResponse, safely omitting sensitive data."""
    roles = [
        RoleResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in employee.roles
    ]
    return EmployeeDetailResponse(
        id=employee.id,
        employee_code=employee.employee_code,
        full_name=employee.full_name,
        email=employee.email,
        department_id=employee.department_id,
        location_id=employee.location_id,
        enrollment_status=employee.enrollment_status,
        is_active=employee.is_active,
        created_at=employee.created_at,
        updated_at=employee.updated_at,
        roles=roles,
        department_name=employee.department.name if employee.department else None,
        location_name=employee.location.name if employee.location else None,
    )


def create_employee(
    db: Session,
    data: EmployeeCreate,
    current_user: User,
) -> Employee:
    """
    Create a new employee with full validation:
    - Validates uniqueness of employee_code and email.
    - Validates department and location consistency (department.location_id == location_id).
    - If department_id is supplied without location_id, inherits department's location.
    - Validates user's authorization to manage the target location.
    - Validates and assigns role references.
    """
    clean_code = data.employee_code.strip()
    clean_email = str(data.email).strip().lower() if data.email else None

    # Check unique employee_code
    existing_code = (
        db.query(Employee)
        .filter(func.lower(Employee.employee_code) == clean_code.lower())
        .first()
    )
    if existing_code:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Employee code '{clean_code}' is already assigned to another employee.",
        )

    # Check unique email
    if clean_email:
        existing_email = (
            db.query(Employee)
            .filter(func.lower(Employee.email) == clean_email)
            .first()
        )
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email '{clean_email}' is already in use by another employee.",
            )

    # Resolve and validate department & location consistency
    target_location_id = data.location_id
    if data.department_id is not None:
        department = (
            db.query(Department).filter(Department.id == data.department_id).first()
        )
        if not department:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department with ID {data.department_id} does not exist.",
            )
        if target_location_id is not None and target_location_id != department.location_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Department location ID {department.location_id} does not match "
                    f"specified employee location ID {target_location_id}."
                ),
            )
        target_location_id = department.location_id
    elif target_location_id is not None:
        location = (
            db.query(Location).filter(Location.id == target_location_id).first()
        )
        if not location:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Location with ID {target_location_id} does not exist.",
            )

    # Verify user authorization for target location
    if target_location_id is not None:
        if not has_location_access(db=db, user=current_user, location_id=target_location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorized to create employees in location ID {target_location_id}.",
            )

    # Validate roles
    assigned_roles = []
    if data.role_ids:
        roles = db.query(Role).filter(Role.id.in_(data.role_ids)).all()
        if len(roles) != len(set(data.role_ids)):
            found_ids = {r.id for r in roles}
            missing_ids = set(data.role_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"The following role IDs do not exist: {sorted(missing_ids)}.",
            )
        assigned_roles = roles

    employee = Employee(
        employee_code=clean_code,
        full_name=data.full_name.strip(),
        email=clean_email,
        department_id=data.department_id,
        location_id=target_location_id,
        enrollment_status=data.enrollment_status,
        is_active=data.is_active,
    )
    employee.roles = assigned_roles

    db.add(employee)
    db.commit()
    db.refresh(employee)
    logger.info("Created employee '%s' (%s, ID %d)", employee.full_name, employee.employee_code, employee.id)
    return employee


def update_employee(
    db: Session,
    employee: Employee,
    data: EmployeeUpdate,
    current_user: User,
) -> Employee:
    """
    Update employee attributes:
    - Enforces uniqueness if employee_code or email is modified.
    - Validates department and location consistency.
    - Enforces location authorization if moving employee across locations.
    - Updates role assignments if provided.
    """
    # 1. Check unique employee email if modified
    if data.email is not None:
        clean_email = str(data.email).strip().lower()
        if employee.email is None or clean_email != employee.email.lower():
            existing = (
                db.query(Employee)
                .filter(func.lower(Employee.email) == clean_email, Employee.id != employee.id)
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Email '{clean_email}' is already in use by another employee.",
                )
        employee.email = clean_email

    # 2. Resolve department & location consistency
    target_location_id = data.location_id if data.location_id is not None else employee.location_id
    target_department_id = data.department_id if data.department_id is not None else employee.department_id

    if data.department_id is not None:
        department = db.query(Department).filter(Department.id == data.department_id).first()
        if not department:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department with ID {data.department_id} does not exist.",
            )
        if target_location_id is not None and department.location_id != target_location_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Department location ID {department.location_id} does not match "
                    f"target employee location ID {target_location_id}."
                ),
            )
        target_location_id = department.location_id
        employee.department_id = data.department_id

    if data.location_id is not None:
        location = db.query(Location).filter(Location.id == data.location_id).first()
        if not location:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Location with ID {data.location_id} does not exist.",
            )
        # If employee already has a department, check consistency
        if employee.department_id is not None:
            dept = db.query(Department).filter(Department.id == employee.department_id).first()
            if dept and dept.location_id != data.location_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Current department location ID {dept.location_id} does not match "
                        f"new location ID {data.location_id}. Update department accordingly."
                    ),
                )
        target_location_id = data.location_id

    # If location is changing, verify caller has access to the destination location
    if target_location_id != employee.location_id and target_location_id is not None:
        if not has_location_access(db=db, user=current_user, location_id=target_location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorized for new location ID {target_location_id}.",
            )
        employee.location_id = target_location_id

    if data.full_name is not None:
        employee.full_name = data.full_name.strip()

    if data.enrollment_status is not None:
        employee.enrollment_status = data.enrollment_status

    if data.is_active is not None:
        employee.is_active = data.is_active

    if data.role_ids is not None:
        roles = db.query(Role).filter(Role.id.in_(data.role_ids)).all()
        if len(roles) != len(set(data.role_ids)):
            found_ids = {r.id for r in roles}
            missing_ids = set(data.role_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"The following role IDs do not exist: {sorted(missing_ids)}.",
            )
        employee.roles = roles

    db.commit()
    db.refresh(employee)
    logger.info("Updated employee '%s' (%s, ID %d)", employee.full_name, employee.employee_code, employee.id)
    return employee


def deactivate_employee(db: Session, employee: Employee) -> Employee:
    """Soft deactivate employee."""
    employee.is_active = False
    db.commit()
    db.refresh(employee)
    logger.info("Deactivated employee '%s' (%s, ID %d)", employee.full_name, employee.employee_code, employee.id)
    return employee


def assign_role_to_employee(db: Session, employee: Employee, role_id: int) -> Employee:
    """Assign an employee role to the employee."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} not found.",
        )
    if role not in employee.roles:
        employee.roles.append(role)
        db.commit()
        db.refresh(employee)
        logger.info("Assigned role '%s' to employee ID %d", role.name, employee.id)
    return employee


def remove_role_from_employee(db: Session, employee: Employee, role_id: int) -> Employee:
    """Remove an employee role from the employee."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} not found.",
        )
    if role not in employee.roles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} ('{role.name}') is not assigned to employee ID {employee.id}.",
        )
    employee.roles.remove(role)
    db.commit()
    db.refresh(employee)
    logger.info("Removed role '%s' from employee ID %d", role.name, employee.id)
    return employee

