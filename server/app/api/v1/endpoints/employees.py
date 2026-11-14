import math
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeResponse,
    EmployeeDetailResponse,
    EmployeeRoleAssign,
)
from app.schemas.common import PaginatedResponse
from app.api.deps import (
    require_viewer,
    require_location_admin,
    has_location_access,
)
from app.services import employee_service

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[EmployeeResponse],
    summary="List employees with pagination and filters",
    description="Retrieve paginated employees within accessible locations. Supports filtering by location, department, active status, enrollment status, and text search.",
)
def list_employees(
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    location_id: Annotated[int | None, Query(description="Filter by location ID")] = None,
    department_id: Annotated[int | None, Query(description="Filter by department ID")] = None,
    is_active: Annotated[bool | None, Query(description="Filter by active status")] = None,
    enrollment_status: Annotated[str | None, Query(description="Filter by enrollment status")] = None,
    search: Annotated[str | None, Query(description="Search by full name, code, or email")] = None,
) -> PaginatedResponse[EmployeeResponse]:
    items, total = employee_service.list_employees(
        db=db,
        user=current_user,
        page=page,
        size=size,
        location_id=location_id,
        department_id=department_id,
        is_active=is_active,
        enrollment_status=enrollment_status,
        search=search,
    )

    pages = math.ceil(total / size) if total > 0 else 0

    return PaginatedResponse[EmployeeResponse](
        items=[EmployeeResponse.model_validate(e) for e in items],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.post(
    "",
    response_model=EmployeeDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create employee",
    description="Register a new employee. Validates uniqueness of employee code and email, department/location consistency, and location authorization.",
)
def create_employee(
    data: EmployeeCreate,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> EmployeeDetailResponse:
    employee = employee_service.create_employee(
        db=db, data=data, current_user=current_user
    )
    return employee_service.format_employee_detail(employee)


@router.get(
    "/{employee_id}",
    response_model=EmployeeDetailResponse,
    summary="Get employee details",
    description="Retrieve full employee details. Safe output: never exposes credentials or biometric vectors.",
)
def get_employee(
    employee_id: int,
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
) -> EmployeeDetailResponse:
    employee = employee_service.get_employee_by_id(db=db, employee_id=employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )

    if employee.location_id is not None:
        if not has_location_access(db=db, user=current_user, location_id=employee.location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorized for employee location ID {employee.location_id}.",
            )

    return employee_service.format_employee_detail(employee)


@router.patch(
    "/{employee_id}",
    response_model=EmployeeDetailResponse,
    summary="Update employee",
    description="Update employee profile, department, location, roles, or status.",
)
def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> EmployeeDetailResponse:
    employee = employee_service.get_employee_by_id(db=db, employee_id=employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )

    if employee.location_id is not None:
        if not has_location_access(db=db, user=current_user, location_id=employee.location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorized to update employee at location ID {employee.location_id}.",
            )

    updated = employee_service.update_employee(
        db=db, employee=employee, data=data, current_user=current_user
    )
    return employee_service.format_employee_detail(updated)


@router.delete(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Deactivate employee",
    description="Soft-deactivate an employee record (sets is_active=False).",
)
def deactivate_employee(
    employee_id: int,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> EmployeeResponse:
    employee = employee_service.get_employee_by_id(db=db, employee_id=employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )

    if employee.location_id is not None:
        if not has_location_access(db=db, user=current_user, location_id=employee.location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorized to deactivate employee at location ID {employee.location_id}.",
            )

    deactivated = employee_service.deactivate_employee(db=db, employee=employee)
    return EmployeeResponse.model_validate(deactivated)


@router.post(
    "/{employee_id}/roles",
    response_model=EmployeeDetailResponse,
    summary="Assign role to employee",
    description="Assign an employee job role using request body.",
)
def assign_role(
    employee_id: int,
    data: EmployeeRoleAssign,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> EmployeeDetailResponse:
    employee = employee_service.get_employee_by_id(db=db, employee_id=employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )

    if employee.location_id is not None:
        if not has_location_access(db=db, user=current_user, location_id=employee.location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorized for employee location ID {employee.location_id}.",
            )

    updated = employee_service.assign_role_to_employee(
        db=db, employee=employee, role_id=data.role_id
    )
    return employee_service.format_employee_detail(updated)


@router.post(
    "/{employee_id}/roles/{role_id}",
    response_model=EmployeeDetailResponse,
    summary="Assign role to employee (path parameter)",
    description="Assign an employee job role using URL path parameter.",
)
def assign_role_by_path(
    employee_id: int,
    role_id: int,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> EmployeeDetailResponse:
    return assign_role(
        employee_id=employee_id,
        data=EmployeeRoleAssign(role_id=role_id),
        current_user=current_user,
        db=db,
    )


@router.delete(
    "/{employee_id}/roles/{role_id}",
    response_model=EmployeeDetailResponse,
    summary="Remove role from employee",
    description="Remove an assigned job role from an employee.",
)
def remove_role(
    employee_id: int,
    role_id: int,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> EmployeeDetailResponse:
    employee = employee_service.get_employee_by_id(db=db, employee_id=employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )

    if employee.location_id is not None:
        if not has_location_access(db=db, user=current_user, location_id=employee.location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorized for employee location ID {employee.location_id}.",
            )

    updated = employee_service.remove_role_from_employee(
        db=db, employee=employee, role_id=role_id
    )
    return employee_service.format_employee_detail(updated)

