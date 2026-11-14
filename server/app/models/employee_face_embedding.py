from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Integer,
    Float,
    ForeignKey,
    CheckConstraint,
    Index,
    text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.user import User


class EmployeeFaceEmbedding(Base):
    __tablename__ = "employee_face_embeddings"
    __table_args__ = (
        CheckConstraint(
            "array_length(embedding, 1) = 512",
            name="ck_employee_face_embedding_dim_512",
        ),
        CheckConstraint(
            "sample_count >= 1",
            name="ck_employee_face_embedding_sample_count",
        ),
        # Partial unique index ensuring at most one active template per employee/model/version.
        # Historical enrollment samples (is_template=False) remain unconstrained.
        Index(
            "uq_active_employee_template",
            "employee_id",
            "model_name",
            "model_version",
            unique=True,
            postgresql_where=text("is_template = true AND is_active = true"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 512-dimensional AuraFace L2-normalized float embedding vector
    embedding: Mapped[list[float]] = mapped_column(
        ARRAY(Float), nullable=False
    )
    is_template: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    model_name: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="auraface_v1_glintr100"
    )
    model_version: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="v1"
    )
    sample_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_image_ref: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    enrolled_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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
    employee: Mapped["Employee"] = relationship(
        back_populates="face_embeddings"
    )
    enrolled_by_user: Mapped["User | None"] = relationship(
        back_populates="enrolled_embeddings"
    )

