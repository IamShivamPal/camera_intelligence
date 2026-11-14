from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    ForeignKey,
    CheckConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.location import Location
    from app.models.role import Role
    from app.models.user import User
    from app.models.employee_face_embedding import EmployeeFaceEmbedding
    from app.models.workstation_zone import WorkstationZone
    from app.models.presence_session import PresenceSession
    from app.models.guest_visit import GuestVisit
    from app.models.detection_event import DetectionEvent
    from app.models.alert import Alert


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        CheckConstraint(
            "enrollment_status IN ('pending', 'enrolled', 'needs_re_enroll', 'revoked')",
            name="ck_employee_enrollment_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str | None] = mapped_column(
        String(150), unique=True, nullable=True, index=True
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    enrollment_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="pending"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
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
    department: Mapped["Department | None"] = relationship(
        back_populates="employees"
    )
    location: Mapped["Location | None"] = relationship(
        back_populates="employees"
    )
    roles: Mapped[list["Role"]] = relationship(
        secondary="employee_roles",
        back_populates="employees",
    )
    user: Mapped["User | None"] = relationship(
        back_populates="employee",
        uselist=False,
    )
    face_embeddings: Mapped[list["EmployeeFaceEmbedding"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    assigned_workstation_zones: Mapped[list["WorkstationZone"]] = relationship(
        foreign_keys="WorkstationZone.assigned_employee_id",
        back_populates="assigned_employee",
    )
    presence_sessions: Mapped[list["PresenceSession"]] = relationship(
        back_populates="employee"
    )
    hosted_guest_visits: Mapped[list["GuestVisit"]] = relationship(
        back_populates="host_employee"
    )
    detection_events: Mapped[list["DetectionEvent"]] = relationship(
        back_populates="employee"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="employee"
    )
