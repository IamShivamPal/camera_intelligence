import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.employee_face_embedding import EmployeeFaceEmbedding
from app.models.employee import Employee
from app.models.user import User
from app.schemas.face_enrollment import (
    FaceEnrollmentCreate,
    FaceEnrollmentResponse,
    FaceEnrollmentDetailResponse,
)
from app.core.permissions import SystemRole, has_minimum_role
from app.api.deps import has_location_access

logger = logging.getLogger(__name__)


def format_enrollment_response(embedding: EmployeeFaceEmbedding) -> FaceEnrollmentResponse:
    """Format EmployeeFaceEmbedding into safe metadata response (never exposes embedding vectors)."""
    return FaceEnrollmentResponse(
        id=embedding.id,
        employee_id=embedding.employee_id,
        is_template=embedding.is_template,
        model_name=embedding.model_name,
        model_version=embedding.model_version,
        sample_count=embedding.sample_count,
        quality_score=embedding.quality_score,
        source_image_ref=embedding.source_image_ref,
        enrolled_by_user_id=embedding.enrolled_by_user_id,
        is_active=embedding.is_active,
        created_at=embedding.created_at,
        updated_at=embedding.updated_at,
        embedding_dim=512,
    )


def format_enrollment_detail(db: Session, embedding: EmployeeFaceEmbedding) -> FaceEnrollmentDetailResponse:
    """Format EmployeeFaceEmbedding into rich detail response including employee and location context."""
    emp = embedding.employee
    loc_id = emp.location_id if emp else None
    loc_name = emp.location.name if emp and emp.location else None
    dept_name = emp.department.name if emp and emp.department else None
    enroller_name = embedding.enrolled_by_user.full_name if embedding.enrolled_by_user else None

    return FaceEnrollmentDetailResponse(
        id=embedding.id,
        employee_id=embedding.employee_id,
        is_template=embedding.is_template,
        model_name=embedding.model_name,
        model_version=embedding.model_version,
        sample_count=embedding.sample_count,
        quality_score=embedding.quality_score,
        source_image_ref=embedding.source_image_ref,
        enrolled_by_user_id=embedding.enrolled_by_user_id,
        is_active=embedding.is_active,
        created_at=embedding.created_at,
        updated_at=embedding.updated_at,
        embedding_dim=512,
        employee_code=emp.employee_code if emp else None,
        employee_name=emp.full_name if emp else None,
        location_id=loc_id,
        location_name=loc_name,
        department_name=dept_name,
        enrolled_by_user_name=enroller_name,
    )


def enroll_face_template(
    db: Session,
    employee_id: int,
    data: FaceEnrollmentCreate,
    current_user: User,
) -> EmployeeFaceEmbedding:
    """
    Enroll a new 512D AuraFace face template or sample for an employee.
    - Requires location_admin or super_admin.
    - Validates employee exists and user has location access.
    - Enforces partial unique constraint: at most one active template per (employee_id, model_name, model_version).
    - Updates employee enrollment_status to 'enrolled'.
    """
    if not has_minimum_role(current_user.system_role, SystemRole.LOCATION_ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location administrative privileges required to enroll face templates.",
        )

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
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

    clean_model_name = data.model_name.strip()
    clean_model_version = data.model_version.strip()

    # Enforce active template uniqueness
    if data.is_template and data.is_active:
        existing_active = (
            db.query(EmployeeFaceEmbedding)
            .filter(
                EmployeeFaceEmbedding.employee_id == employee_id,
                func.lower(EmployeeFaceEmbedding.model_name) == clean_model_name.lower(),
                func.lower(EmployeeFaceEmbedding.model_version) == clean_model_version.lower(),
                EmployeeFaceEmbedding.is_template == True,
                EmployeeFaceEmbedding.is_active == True,
            )
            .first()
        )
        if existing_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"An active face template already exists for employee ID {employee_id} using "
                    f"model '{clean_model_name}' ({clean_model_version}). Deactivate the existing template "
                    f"or use the /set-primary endpoint to select an active template."
                ),
            )

    embedding_record = EmployeeFaceEmbedding(
        employee_id=employee_id,
        embedding=data.embedding,
        is_template=data.is_template,
        model_name=clean_model_name,
        model_version=clean_model_version,
        sample_count=data.sample_count,
        quality_score=data.quality_score,
        source_image_ref=data.source_image_ref.strip() if data.source_image_ref else None,
        enrolled_by_user_id=current_user.id,
        is_active=data.is_active,
    )
    db.add(embedding_record)

    # Transition employee status to 'enrolled' if active template
    if data.is_template and data.is_active:
        employee.enrollment_status = "enrolled"

    db.commit()
    db.refresh(embedding_record)
    logger.info(
        "Enrolled face template ID %d for employee ID %d (is_template=%s, model=%s)",
        embedding_record.id,
        employee_id,
        embedding_record.is_template,
        embedding_record.model_name,
    )
    return embedding_record


def list_employee_face_enrollments(
    db: Session,
    employee_id: int,
    user: User,
    is_template: bool | None = None,
    is_active: bool | None = None,
    model_name: str | None = None,
) -> list[EmployeeFaceEmbedding]:
    """List face enrollment metadata for a given employee (never exposes raw vectors)."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found.",
        )

    if employee.location_id is not None:
        if not has_location_access(db=db, user=user, location_id=employee.location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorized for employee location ID {employee.location_id}.",
            )

    query = db.query(EmployeeFaceEmbedding).filter(EmployeeFaceEmbedding.employee_id == employee_id)

    if is_template is not None:
        query = query.filter(EmployeeFaceEmbedding.is_template == is_template)
    if is_active is not None:
        query = query.filter(EmployeeFaceEmbedding.is_active == is_active)
    if model_name is not None and model_name.strip():
        query = query.filter(func.lower(EmployeeFaceEmbedding.model_name) == model_name.strip().lower())

    return (
        query.order_by(
            EmployeeFaceEmbedding.is_template.desc(),
            EmployeeFaceEmbedding.created_at.desc(),
        )
        .all()
    )


def get_face_enrollment_by_id(
    db: Session,
    embedding_id: int,
    user: User,
) -> EmployeeFaceEmbedding:
    """Retrieve single face enrollment metadata."""
    embedding = db.query(EmployeeFaceEmbedding).filter(EmployeeFaceEmbedding.id == embedding_id).first()
    if not embedding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Face enrollment template with ID {embedding_id} not found.",
        )

    if embedding.employee and embedding.employee.location_id is not None:
        if not has_location_access(db=db, user=user, location_id=embedding.employee.location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorized for employee location ID {embedding.employee.location_id}.",
            )

    return embedding


def deactivate_face_enrollment(
    db: Session,
    embedding_id: int,
    current_user: User,
) -> EmployeeFaceEmbedding:
    """
    Deactivate a face template or sample.
    - Requires location_admin or super_admin.
    - Updates employee status to 'needs_re_enroll' if no active templates remain.
    """
    if not has_minimum_role(current_user.system_role, SystemRole.LOCATION_ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location administrative privileges required to deactivate face templates.",
        )

    embedding = db.query(EmployeeFaceEmbedding).filter(EmployeeFaceEmbedding.id == embedding_id).first()
    if not embedding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Face enrollment template with ID {embedding_id} not found.",
        )

    if embedding.employee and embedding.employee.location_id is not None:
        if not has_location_access(db=db, user=current_user, location_id=embedding.employee.location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorized for employee location ID {embedding.employee.location_id}.",
            )

    embedding.is_active = False
    embedding.is_template = False

    # Check remaining active templates for employee
    remaining_count = (
        db.query(func.count(EmployeeFaceEmbedding.id))
        .filter(
            EmployeeFaceEmbedding.employee_id == embedding.employee_id,
            EmployeeFaceEmbedding.is_active == True,
            EmployeeFaceEmbedding.is_template == True,
            EmployeeFaceEmbedding.id != embedding.id,
        )
        .scalar()
        or 0
    )

    if remaining_count == 0 and embedding.employee:
        embedding.employee.enrollment_status = "needs_re_enroll"

    db.commit()
    db.refresh(embedding)
    logger.info("Deactivated face enrollment ID %d for employee ID %d", embedding.id, embedding.employee_id)
    return embedding


def set_primary_face_template(
    db: Session,
    embedding_id: int,
    current_user: User,
) -> EmployeeFaceEmbedding:
    """
    Designate an existing face template as the active primary template.
    - Demotes any existing active template for the same (employee_id, model_name, model_version).
    - Sets target embedding as active template (is_template=True, is_active=True).
    - Updates employee enrollment_status to 'enrolled'.
    """
    if not has_minimum_role(current_user.system_role, SystemRole.LOCATION_ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location administrative privileges required to manage primary templates.",
        )

    embedding = db.query(EmployeeFaceEmbedding).filter(EmployeeFaceEmbedding.id == embedding_id).first()
    if not embedding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Face enrollment template with ID {embedding_id} not found.",
        )

    if embedding.employee and embedding.employee.location_id is not None:
        if not has_location_access(db=db, user=current_user, location_id=embedding.employee.location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorized for employee location ID {embedding.employee.location_id}.",
            )

    # Demote existing active template for same model and version
    db.query(EmployeeFaceEmbedding).filter(
        EmployeeFaceEmbedding.employee_id == embedding.employee_id,
        func.lower(EmployeeFaceEmbedding.model_name) == embedding.model_name.lower(),
        func.lower(EmployeeFaceEmbedding.model_version) == embedding.model_version.lower(),
        EmployeeFaceEmbedding.id != embedding.id,
        EmployeeFaceEmbedding.is_template == True,
        EmployeeFaceEmbedding.is_active == True,
    ).update({"is_template": False}, synchronize_session=False)

    embedding.is_template = True
    embedding.is_active = True

    if embedding.employee:
        embedding.employee.enrollment_status = "enrolled"

    db.commit()
    db.refresh(embedding)
    logger.info("Set face enrollment ID %d as primary template for employee ID %d", embedding.id, embedding.employee_id)
    return embedding

