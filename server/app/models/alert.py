from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import (
    String,
    DateTime,
    BigInteger,
    ForeignKey,
    CheckConstraint,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base

if TYPE_CHECKING:
    from app.models.location import Location
    from app.models.camera import Camera
    from app.models.employee import Employee
    from app.models.workstation_zone import WorkstationZone
    from app.models.presence_session import PresenceSession
    from app.models.guest_visit import GuestVisit
    from app.models.detection_event import DetectionEvent
    from app.models.user import User


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint(
            "alert_type IN ("
            "'employee_inactivity', "
            "'after_hours_intrusion', "
            "'after_hours_employee', "
            "'unknown_guest', "
            "'camera_offline'"
            ")",
            name="ck_alert_type",
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_alert_severity",
        ),
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved', 'false_positive')",
            name="ck_alert_status",
        ),
        Index("ix_alerts_triage", "location_id", "status", "triggered_at"),
        Index("ix_alerts_severity_status", "status", "severity", "triggered_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    camera_id: Mapped[int | None] = mapped_column(
        ForeignKey("cameras.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    alert_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="medium"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="open", index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
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
    detection_event_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("detection_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    acknowledged_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_notes: Mapped[str | None] = mapped_column(
        String(500), nullable=True
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
        back_populates="alerts"
    )
    camera: Mapped["Camera | None"] = relationship(
        back_populates="alerts"
    )
    employee: Mapped["Employee | None"] = relationship(
        back_populates="alerts"
    )
    workstation_zone: Mapped["WorkstationZone | None"] = relationship(
        back_populates="alerts"
    )
    presence_session: Mapped["PresenceSession | None"] = relationship(
        back_populates="alerts"
    )
    guest_visit: Mapped["GuestVisit | None"] = relationship(
        back_populates="alerts"
    )
    detection_event: Mapped["DetectionEvent | None"] = relationship(
        back_populates="alerts"
    )
    acknowledged_by_user: Mapped["User | None"] = relationship(
        foreign_keys=[acknowledged_by_user_id],
        back_populates="acknowledged_alerts",
    )
    resolved_by_user: Mapped["User | None"] = relationship(
        foreign_keys=[resolved_by_user_id],
        back_populates="resolved_alerts",
    )

