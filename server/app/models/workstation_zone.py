from datetime import datetime
from typing import TYPE_CHECKING, Any
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Integer,
    ForeignKey,
    CheckConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base

if TYPE_CHECKING:
    from app.models.location import Location
    from app.models.camera import Camera
    from app.models.employee import Employee
    from app.models.department import Department
    from app.models.presence_session import PresenceSession
    from app.models.detection_event import DetectionEvent
    from app.models.alert import Alert


class WorkstationZone(Base):
    __tablename__ = "workstation_zones"
    __table_args__ = (
        CheckConstraint(
            "inactivity_threshold_seconds > 0",
            name="ck_workstation_zone_inactivity_threshold",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("cameras.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    zone_code: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    # Stored as normalized polygon coordinates [[x, y], ...] in range [0.0, 1.0]
    polygon_points: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    assigned_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    inactivity_threshold_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="900"
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
    location: Mapped["Location"] = relationship(
        back_populates="workstation_zones"
    )
    camera: Mapped["Camera"] = relationship(
        back_populates="workstation_zones"
    )
    assigned_employee: Mapped["Employee | None"] = relationship(
        foreign_keys=[assigned_employee_id],
        back_populates="assigned_workstation_zones",
    )
    department: Mapped["Department | None"] = relationship(
        back_populates="workstation_zones"
    )
    presence_sessions: Mapped[list["PresenceSession"]] = relationship(
        back_populates="workstation_zone"
    )
    detection_events: Mapped[list["DetectionEvent"]] = relationship(
        back_populates="workstation_zone"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="workstation_zone"
    )

