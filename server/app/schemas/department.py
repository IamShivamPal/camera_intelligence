from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class DepartmentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Department name within location")
    code: str | None = Field(None, max_length=50, description="Unique short code within location")
    is_active: bool = Field(True, description="Active status flag")

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Department name cannot be empty or whitespace.")
        return s

    @field_validator("code")
    @classmethod
    def validate_code_not_blank(cls, v: str | None) -> str | None:
        if v is not None:
            s = v.strip()
            return s if s else None
        return None


class DepartmentCreate(DepartmentBase):
    location_id: int = Field(..., description="ID of location where department resides")


class DepartmentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    code: str | None = Field(None, max_length=50)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, v: str | None) -> str | None:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Department name cannot be empty or whitespace.")
            return s
        return v

    @field_validator("code")
    @classmethod
    def validate_code_not_blank(cls, v: str | None) -> str | None:
        if v is not None:
            s = v.strip()
            return s if s else None
        return None


class DepartmentResponse(BaseModel):
    id: int
    location_id: int
    name: str
    code: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    employee_count: int = 0

    model_config = {"from_attributes": True}

