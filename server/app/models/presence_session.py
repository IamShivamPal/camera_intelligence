from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Integer,
    BigInteger,
    ForeignKey,
    CheckConstraint,
    Index,
    text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.location import Location
    from app.models.camera import Camera
    from app.models.workstation_zone import WorkstationZone
    from app.models.detection_event import DetectionEvent
    from app.models.alert import Alert


class PresenceSession(Base):
    __tablename__ = "presence_sessions"
    __table_args__ = (
        CheckConstraint(
            "session_type IN ('facility', 'workstation')",
            name="ck_presence_session_type",
        ),
        CheckConstraint(
            "status IN ('active', 'idle', 'closed')",
            name="ck_presence_session_status",
        ),
        CheckConstraint(
            "active_seconds >= 0",
            name="ck_presence_session_active_seconds",
        ),
        CheckConstraint(
            "idle_seconds >= 0",
            name="ck_presence_session_idle_seconds",
        ),
        # Partial unique index: at most one open facility session per employee per location
        Index(
            "uq_open_facility_session_per_employee",
            "employee_id",
            "location_id",
            unique=True,
            postgresql_where=text("session_type = 'facility' AND ended_at IS NULL"),
        ),
        # Partial unique index: at most one open workstation session per employee per zone
        Index(
            "uq_open_workstation_session_per_employee",
            "employee_id",
            "workstation_zone_id",
            unique=True,
            postgresql_where=text("session_type = 'workstation' AND ended_at IS NULL"),
        ),
        Index("ix_presence_sessions_query", "location_id", "status", "started_at"),
        Index("ix_presence_sessions_employee_timeline", "employee_id", "started_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    entry_camera_id: Mapped[int | None] = mapped_column(
        ForeignKey("cameras.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    exit_camera_id: Mapped[int | None] = mapped_column(
        ForeignKey("cameras.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workstation_zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("workstation_zones.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    session_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="facility"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="active"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    active_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    idle_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    is_after_hours: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
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
    employee: Mapped["Employee"] = relationship(
        back_populates="presence_sessions"
    )
    location: Mapped["Location"] = relationship(
        back_populates="presence_sessions"
    )
    entry_camera: Mapped["Camera | None"] = relationship(
        foreign_keys=[entry_camera_id]
    )
    exit_camera: Mapped["Camera | None"] = relationship(
        foreign_keys=[exit_camera_id]
    )
    workstation_zone: Mapped["WorkstationZone | None"] = relationship(
        back_populates="presence_sessions"
    )
    detection_events: Mapped[list["DetectionEvent"]] = relationship(
        back_populates="presence_session"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="presence_session"
    )

