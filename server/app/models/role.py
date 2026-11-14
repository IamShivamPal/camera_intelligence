from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, Table, Column, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


employee_roles = Table(
    "employee_roles",
    Base.metadata,
    Column(
        "employee_id",
        ForeignKey("employees.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "assigned_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    employees: Mapped[list["Employee"]] = relationship(
        secondary=employee_roles,
        back_populates="roles",
    )
