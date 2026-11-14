from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.camera import Camera
    from app.models.location_schedule import LocationSchedule
    from app.models.workstation_zone import WorkstationZone
    from app.models.employee import Employee
    from app.models.user import User
    from app.models.presence_session import PresenceSession
    from app.models.guest_visit import GuestVisit
    from app.models.detection_event import DetectionEvent
    from app.models.alert import Alert


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="UTC"
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
    departments: Mapped[list["Department"]] = relationship(
        back_populates="location"
    )
    cameras: Mapped[list["Camera"]] = relationship(
        back_populates="location"
    )
    schedules: Mapped[list["LocationSchedule"]] = relationship(
        back_populates="location",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    workstation_zones: Mapped[list["WorkstationZone"]] = relationship(
        back_populates="location"
    )
    employees: Mapped[list["Employee"]] = relationship(
        back_populates="location"
    )
    users: Mapped[list["User"]] = relationship(
        secondary="user_locations",
        back_populates="locations",
    )
    presence_sessions: Mapped[list["PresenceSession"]] = relationship(
        back_populates="location"
    )
    guest_visits: Mapped[list["GuestVisit"]] = relationship(
        back_populates="location"
    )
    detection_events: Mapped[list["DetectionEvent"]] = relationship(
        back_populates="location"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="location"
    )
