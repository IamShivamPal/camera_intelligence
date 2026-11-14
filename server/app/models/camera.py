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
    from app.models.location import Location
    from app.models.workstation_zone import WorkstationZone
    from app.models.detection_event import DetectionEvent
    from app.models.alert import Alert


class Camera(Base):
    __tablename__ = "cameras"
    __table_args__ = (
        CheckConstraint(
            "camera_role IN ('entry_exit', 'workstation', 'perimeter', 'general')",
            name="ck_camera_role",
        ),
        CheckConstraint(
            "stream_type IN ('rtsp', 'webcam', 'file', 'onvif')",
            name="ck_camera_stream_type",
        ),
        CheckConstraint(
            "connection_status IN ('online', 'offline', 'degraded', 'unknown')",
            name="ck_camera_connection_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    camera_code: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    camera_role: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="general"
    )
    stream_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="rtsp"
    )
    # Reference to securely stored stream credentials/configuration.
    # Plaintext RTSP credentials must never be stored here.
    stream_secret_ref: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    connection_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="unknown"
    )
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
        back_populates="cameras"
    )
    workstation_zones: Mapped[list["WorkstationZone"]] = relationship(
        back_populates="camera"
    )
    detection_events: Mapped[list["DetectionEvent"]] = relationship(
        back_populates="camera"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="camera"
    )
