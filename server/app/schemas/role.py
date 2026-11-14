from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Unique employee role name")
    description: str | None = Field(None, max_length=200, description="Role description")

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Role name cannot be empty or whitespace.")
        return s


class RoleResponse(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

