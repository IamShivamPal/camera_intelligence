from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.schemas.face_enrollment import (
    FaceEnrollmentCreate,
    FaceEnrollmentResponse,
    FaceEnrollmentDetailResponse,
)
from app.api.deps import (
    require_viewer,
    require_location_admin,
)
from app.services import face_enrollment_service

router = APIRouter(tags=["Face Enrollments"])


@router.post(
    "/employees/{employee_id}/face-enrollments",
    response_model=FaceEnrollmentDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll face template for employee",
    description="Register a 512D AuraFace embedding template or sample. Enforces vector normalization and active template uniqueness.",
)
def enroll_face_template(
    employee_id: int,
    data: FaceEnrollmentCreate,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> FaceEnrollmentDetailResponse:
    embedding = face_enrollment_service.enroll_face_template(
        db=db,
        employee_id=employee_id,
        data=data,
        current_user=current_user,
    )
    return face_enrollment_service.format_enrollment_detail(db=db, embedding=embedding)


@router.get(
    "/employees/{employee_id}/face-enrollments",
    response_model=list[FaceEnrollmentResponse],
    summary="List face enrollment metadata for employee",
    description="Retrieve face enrollment metadata. Never exposes raw embedding vectors or biometric coordinates.",
)
def list_employee_face_enrollments(
    employee_id: int,
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
    is_template: Annotated[bool | None, Query(description="Filter by primary template flag")] = None,
    is_active: Annotated[bool | None, Query(description="Filter by active status")] = None,
    model_name: Annotated[str | None, Query(description="Filter by AI model architecture")] = None,
) -> list[FaceEnrollmentResponse]:
    embeddings = face_enrollment_service.list_employee_face_enrollments(
        db=db,
        employee_id=employee_id,
        user=current_user,
        is_template=is_template,
        is_active=is_active,
        model_name=model_name,
    )
    return [face_enrollment_service.format_enrollment_response(e) for e in embeddings]


@router.get(
    "/face-enrollments/{embedding_id}",
    response_model=FaceEnrollmentDetailResponse,
    summary="Get face enrollment details",
    description="Retrieve face template metadata and employee association details without embedding vectors.",
)
def get_face_enrollment(
    embedding_id: int,
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
) -> FaceEnrollmentDetailResponse:
    embedding = face_enrollment_service.get_face_enrollment_by_id(
        db=db, embedding_id=embedding_id, user=current_user
    )
    return face_enrollment_service.format_enrollment_detail(db=db, embedding=embedding)


@router.delete(
    "/face-enrollments/{embedding_id}",
    response_model=FaceEnrollmentResponse,
    summary="Deactivate face template",
    description="Soft-deactivate a face template (sets is_active=False, is_template=False).",
)
def deactivate_face_enrollment(
    embedding_id: int,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> FaceEnrollmentResponse:
    embedding = face_enrollment_service.deactivate_face_enrollment(
        db=db, embedding_id=embedding_id, current_user=current_user
    )
    return face_enrollment_service.format_enrollment_response(embedding)


@router.post(
    "/face-enrollments/{embedding_id}/set-primary",
    response_model=FaceEnrollmentDetailResponse,
    summary="Set primary active face template",
    description="Designate an existing template as the active primary recognition template for the employee.",
)
def set_primary_face_template(
    embedding_id: int,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> FaceEnrollmentDetailResponse:
    embedding = face_enrollment_service.set_primary_face_template(
        db=db, embedding_id=embedding_id, current_user=current_user
    )
    return face_enrollment_service.format_enrollment_detail(db=db, embedding=embedding)

