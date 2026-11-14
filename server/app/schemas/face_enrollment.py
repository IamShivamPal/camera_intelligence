import math
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, field_validator


def validate_embedding_vector(v: Any) -> list[float]:
    """
    Validate 512-dimensional AuraFace embedding:
    - Must be a list of exactly 512 numbers.
    - No NaN, Inf, non-numeric, or boolean values.
    - Must be L2-normalized (norm ~ 1.0 within numerical tolerance [0.95, 1.05]).
    """
    if not isinstance(v, (list, tuple)):
        raise ValueError("Embedding must be a list of float numbers.")

    if len(v) != 512:
        raise ValueError(f"Embedding vector must have exactly 512 dimensions, got {len(v)}.")

    float_vec: list[float] = []
    norm_sq = 0.0

    for idx, val in enumerate(v):
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise ValueError(f"Embedding value at index {idx} must be a numeric float.")
        if math.isnan(val) or math.isinf(val):
            raise ValueError(f"Embedding value at index {idx} cannot be NaN or Infinite.")
        fval = float(val)
        float_vec.append(fval)
        norm_sq += fval * fval

    norm = math.sqrt(norm_sq)
    if not (0.95 <= norm <= 1.05):
        raise ValueError(
            f"Embedding vector must be L2-normalized (expected norm ~1.0, got {norm:.4f})."
        )

    return float_vec


class FaceEnrollmentCreate(BaseModel):
    embedding: list[float] = Field(
        ...,
        description="512-dimensional L2-normalized float embedding vector",
    )
    model_name: str = Field(
        "auraface_v1_glintr100",
        min_length=1,
        max_length=100,
        description="AI model architecture name",
    )
    model_version: str = Field(
        "v1",
        min_length=1,
        max_length=32,
        description="Model checkpoint or version identifier",
    )
    is_template: bool = Field(
        True,
        description="Whether this enrollment serves as the primary recognition template",
    )
    sample_count: int = Field(
        1,
        ge=1,
        description="Number of face images fused into this embedding (>= 1)",
    )
    quality_score: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Face alignment/quality confidence score [0.0, 1.0]",
    )
    source_image_ref: str | None = Field(
        None,
        max_length=255,
        description="Secure reference identifier for source image storage (never raw bytes)",
    )
    is_active: bool = Field(
        True,
        description="Active status flag",
    )

    @field_validator("embedding", mode="before")
    @classmethod
    def validate_embedding(cls, v: Any) -> list[float]:
        return validate_embedding_vector(v)

    @field_validator("model_name", "model_version")
    @classmethod
    def validate_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Value cannot be empty or whitespace.")
        return s


class FaceEnrollmentResponse(BaseModel):
    """
    Public face enrollment metadata response.
    CRITICAL: NEVER exposes raw embedding vectors or biometric coordinates.
    """
    id: int
    employee_id: int
    is_template: bool
    model_name: str
    model_version: str
    sample_count: int
    quality_score: float | None
    source_image_ref: str | None
    enrolled_by_user_id: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    embedding_dim: int = 512

    model_config = {"from_attributes": True}


class FaceEnrollmentDetailResponse(FaceEnrollmentResponse):
    """Extended template metadata with relational context."""
    employee_code: str | None = None
    employee_name: str | None = None
    location_id: int | None = None
    location_name: str | None = None
    department_name: str | None = None
    enrolled_by_user_name: str | None = None

