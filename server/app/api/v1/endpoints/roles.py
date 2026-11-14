from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.schemas.role import RoleCreate, RoleResponse
from app.api.deps import require_viewer, require_location_admin
from app.services import role_service

router = APIRouter()


@router.get(
    "",
    response_model=list[RoleResponse],
    summary="List employee roles",
    description="Retrieve all configured employee job roles.",
)
def list_roles(
    _: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
) -> list[RoleResponse]:
    roles = role_service.list_roles(db=db)
    return [RoleResponse.model_validate(r) for r in roles]


@router.post(
    "",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create employee role",
    description="Create a new employee job role. Requires location_admin or super_admin authority.",
)
def create_role(
    data: RoleCreate,
    _: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> RoleResponse:
    role = role_service.create_role(db=db, data=data)
    return RoleResponse.model_validate(role)


@router.get(
    "/{role_id}",
    response_model=RoleResponse,
    summary="Get role details",
    description="Retrieve role details by ID.",
)
def get_role(
    role_id: int,
    _: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
) -> RoleResponse:
    role = role_service.get_role_by_id(db=db, role_id=role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} not found.",
        )
    return RoleResponse.model_validate(role)

