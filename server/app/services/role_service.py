import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.role import Role
from app.schemas.role import RoleCreate

logger = logging.getLogger(__name__)


def list_roles(db: Session) -> list[Role]:
    """List all available employee roles."""
    return db.query(Role).order_by(Role.name.asc()).all()


def get_role_by_id(db: Session, role_id: int) -> Role | None:
    """Retrieve role by primary key."""
    return db.query(Role).filter(Role.id == role_id).first()


def create_role(db: Session, data: RoleCreate) -> Role:
    """Create a new role. Enforces unique role name."""
    clean_name = data.name.strip()
    existing = db.query(Role).filter(func.lower(Role.name) == clean_name.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role with name '{clean_name}' already exists.",
        )

    role = Role(
        name=clean_name,
        description=data.description.strip() if data.description else None,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    logger.info("Created role '%s' (ID %d)", role.name, role.id)
    return role

