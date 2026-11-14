from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base

if TYPE_CHECKING:
    from app.models.location import Location
    from app.models.employee import Employee
    from app.models.workstation_zone import WorkstationZone


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("location_id", "name", name="uq_department_location_name"),
        UniqueConstraint("location_id", "code", name="uq_department_location_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
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
    location: Mapped["Location"] = relationship(back_populates="departments")
    employees: Mapped[list["Employee"]] = relationship(back_populates="department")
    workstation_zones: Mapped[list["WorkstationZone"]] = relationship(
        back_populates="department"
    )

