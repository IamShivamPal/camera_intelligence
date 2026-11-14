from datetime import datetime
from typing import TYPE_CHECKING, Any
from sqlalchemy import (
    String,
    DateTime,
    Float,
    BigInteger,
    ForeignKey,
    CheckConstraint,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base

if TYPE_CHECKING:
    from app.models.location import Location
    from app.models.camera import Camera
    from app.models.employee import Employee
    from app.models.workstation_zone import WorkstationZone
    from app.models.presence_session import PresenceSession
    from app.models.guest_visit import GuestVisit
    from app.models.alert import Alert


class DetectionEvent(Base):
    __tablename__ = "detection_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'employee_recognized', "
            "'unknown_person', "
            "'workstation_active', "
            "'workstation_idle', "
            "'after_hours_employee', "
            "'after_hours_intrusion', "
            "'guest_entry', "
            "'guest_exit'"
            ")",
            name="ck_detection_event_type",
        ),
        Index("ix_detection_events_loc_time", "location_id", "occurred_at"),
        Index("ix_detection_events_cam_time", "camera_id", "occurred_at"),
        Index("ix_detection_events_emp_time", "employee_id", "occurred_at"),
    )

    # Immutable append-only detection record
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
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
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workstation_zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("workstation_zones.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    presence_session_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("presence_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    guest_visit_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("guest_visits.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Ephemeral tracking identifier per stream (e.g. ByteTrack ID);
    # MUST NEVER be used as a permanent employee identity.
    tracker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    snapshot_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    location: Mapped["Location"] = relationship(
        back_populates="detection_events"
    )
    camera: Mapped["Camera"] = relationship(
        back_populates="detection_events"
    )
    employee: Mapped["Employee | None"] = relationship(
        back_populates="detection_events"
    )
    workstation_zone: Mapped["WorkstationZone | None"] = relationship(
        back_populates="detection_events"
    )
    presence_session: Mapped["PresenceSession | None"] = relationship(
        back_populates="detection_events"
    )
    guest_visit: Mapped["GuestVisit | None"] = relationship(
        back_populates="detection_events"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="detection_event"
    )

