from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
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
    from app.models.location import Location
    from app.models.camera import Camera
    from app.models.employee import Employee
    from app.models.detection_event import DetectionEvent
    from app.models.alert import Alert


class GuestVisit(Base):
    __tablename__ = "guest_visits"
    __table_args__ = (
        CheckConstraint(
            "status IN ('inside', 'exited', 'unverified', 'escalated')",
            name="ck_guest_visit_status",
        ),
        Index("ix_guest_visits_open", "location_id", "status", "entered_at"),
        Index(
            "ix_guest_visits_active_presence",
            "location_id",
            postgresql_where=text("exited_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    guest_code: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    guest_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
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
    host_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="inside"
    )
    entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    exited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_after_hours: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    snapshot_ref: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
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
        back_populates="guest_visits"
    )
    entry_camera: Mapped["Camera | None"] = relationship(
        foreign_keys=[entry_camera_id]
    )
    exit_camera: Mapped["Camera | None"] = relationship(
        foreign_keys=[exit_camera_id]
    )
    host_employee: Mapped["Employee | None"] = relationship(
        back_populates="hosted_guest_visits"
    )
    detection_events: Mapped[list["DetectionEvent"]] = relationship(
        back_populates="guest_visit"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="guest_visit"
    )

