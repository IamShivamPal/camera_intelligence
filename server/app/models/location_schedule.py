from datetime import datetime, time
from typing import TYPE_CHECKING
from sqlalchemy import (
    Boolean,
    DateTime,
    Time,
    SmallInteger,
    Integer,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base

if TYPE_CHECKING:
    from app.models.location import Location


class LocationSchedule(Base):
    __tablename__ = "location_schedules"
    __table_args__ = (
        UniqueConstraint("location_id", "day_of_week", name="uq_location_schedule_day"),
        CheckConstraint(
            "day_of_week >= 0 AND day_of_week <= 6",
            name="ck_location_schedule_day_of_week",
        ),
        CheckConstraint(
            "after_hours_grace_minutes >= 0",
            name="ck_location_schedule_grace_minutes",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_working_day: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    open_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    close_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    after_hours_grace_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="15"
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
    location: Mapped["Location"] = relationship(back_populates="schedules")

