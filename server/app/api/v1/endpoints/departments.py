from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.schemas.department import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
)
from app.api.deps import (
    require_viewer,
    require_location_admin,
    has_location_access,
)
from app.services import department_service

router = APIRouter()


@router.get(
    "",
    response_model=list[DepartmentResponse],
    summary="List accessible departments",
    description="Retrieve departments within accessible locations. Optional filtering by location_id and is_active.",
)
def list_departments(
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
    location_id: Annotated[int | None, Query(description="Filter by location ID")] = None,
    is_active: Annotated[bool | None, Query(description="Filter by active status")] = None,
) -> list[DepartmentResponse]:
    departments = department_service.list_accessible_departments(
        db=db, user=current_user, location_id=location_id, is_active=is_active
    )
    return [
        department_service.format_department_response(db=db, department=dept)
        for dept in departments
    ]


@router.post(
    "",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create department within a location",
    description="Create a new department. Requires location_admin authority for the target location.",
)
def create_department(
    data: DepartmentCreate,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> DepartmentResponse:
    if not has_location_access(db=db, user=current_user, location_id=data.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized to create departments in location ID {data.location_id}.",
        )

    department = department_service.create_department(db=db, data=data)
    return department_service.format_department_response(db=db, department=department)


@router.get(
    "/{department_id}",
    response_model=DepartmentResponse,
    summary="Get department details",
    description="Retrieve department details. Caller must have access to the department's location.",
)
def get_department(
    department_id: int,
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
) -> DepartmentResponse:
    department = department_service.get_department_by_id(db=db, department_id=department_id)
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {department_id} not found.",
        )

    if not has_location_access(db=db, user=current_user, location_id=department.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized for department ID {department_id}.",
        )

    return department_service.format_department_response(db=db, department=department)


@router.patch(
    "/{department_id}",
    response_model=DepartmentResponse,
    summary="Update department",
    description="Update department details. Requires location_admin authority for the department's location.",
)
def update_department(
    department_id: int,
    data: DepartmentUpdate,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> DepartmentResponse:
    department = department_service.get_department_by_id(db=db, department_id=department_id)
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {department_id} not found.",
        )

    if not has_location_access(db=db, user=current_user, location_id=department.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized to update department ID {department_id}.",
        )

    updated = department_service.update_department(db=db, department=department, data=data)
    return department_service.format_department_response(db=db, department=updated)


@router.delete(
    "/{department_id}",
    response_model=DepartmentResponse,
    summary="Deactivate department",
    description="Soft-deactivate department. Requires location_admin authority for the department's location.",
)
def deactivate_department(
    department_id: int,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> DepartmentResponse:
    department = department_service.get_department_by_id(db=db, department_id=department_id)
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {department_id} not found.",
        )

    if not has_location_access(db=db, user=current_user, location_id=department.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized to deactivate department ID {department_id}.",
        )

    deactivated = department_service.deactivate_department(db=db, department=department)
    return department_service.format_department_response(db=db, department=deactivated)

