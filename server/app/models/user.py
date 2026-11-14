from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Table,
    Column,
    ForeignKey,
    CheckConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.location import Location
    from app.models.employee_face_embedding import EmployeeFaceEmbedding
    from app.models.alert import Alert


user_locations = Table(
    "user_locations",
    Base.metadata,
    Column(
        "user_id",
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "location_id",
        ForeignKey("locations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "assigned_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "system_role IN ('super_admin', 'location_admin', 'operator', 'viewer')",
            name="ck_user_system_role",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(
        String(150), unique=True, nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    system_role: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="viewer"
    )
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
    employee: Mapped["Employee | None"] = relationship(
        back_populates="user"
    )
    locations: Mapped[list["Location"]] = relationship(
        secondary=user_locations,
        back_populates="users",
    )
    enrolled_embeddings: Mapped[list["EmployeeFaceEmbedding"]] = relationship(
        back_populates="enrolled_by_user"
    )
    acknowledged_alerts: Mapped[list["Alert"]] = relationship(
        foreign_keys="Alert.acknowledged_by_user_id",
        back_populates="acknowledged_by_user",
    )
    resolved_alerts: Mapped[list["Alert"]] = relationship(
        foreign_keys="Alert.resolved_by_user_id",
        back_populates="resolved_by_user",
    )

