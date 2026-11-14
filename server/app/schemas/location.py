from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class LocationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150, description="Unique location or branch name")
    address: str | None = Field(None, max_length=300, description="Physical address")
    timezone: str = Field("UTC", max_length=64, description="IANA timezone name, e.g. 'America/New_York'")
    is_active: bool = Field(True, description="Active status flag")

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Location name cannot be empty or whitespace.")
        return s


class LocationCreate(LocationBase):
    pass


class LocationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    address: str | None = Field(None, max_length=300)
    timezone: str | None = Field(None, max_length=64)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, v: str | None) -> str | None:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Location name cannot be empty or whitespace.")
            return s
        return v


class LocationResponse(BaseModel):
    id: int
    name: str
    address: str | None
    timezone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LocationDetailResponse(LocationResponse):
    department_count: int = 0
    employee_count: int = 0
    camera_count: int = 0

