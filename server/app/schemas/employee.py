from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator
from app.schemas.role import RoleResponse


class EmployeeBase(BaseModel):
    employee_code: str = Field(..., min_length=1, max_length=50, description="Unique company employee identifier")
    full_name: str = Field(..., min_length=1, max_length=150, description="Employee full name")
    email: EmailStr | None = Field(None, description="Employee corporate or contact email")
    department_id: int | None = Field(None, description="Department ID")
    location_id: int | None = Field(None, description="Location ID")
    enrollment_status: str = Field(
        "pending",
        pattern="^(pending|enrolled|needs_re_enroll|revoked)$",
        description="Face enrollment status",
    )
    is_active: bool = Field(True, description="Active status")

    @field_validator("employee_code", "full_name")
    @classmethod
    def validate_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Value cannot be empty or whitespace.")
        return s


class EmployeeCreate(EmployeeBase):
    role_ids: list[int] = Field(default_factory=list, description="List of role IDs to assign")


class EmployeeUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=150)
    email: EmailStr | None = None
    department_id: int | None = None
    location_id: int | None = None
    enrollment_status: str | None = Field(
        None, pattern="^(pending|enrolled|needs_re_enroll|revoked)$"
    )
    is_active: bool | None = None
    role_ids: list[int] | None = None

    @field_validator("full_name")
    @classmethod
    def validate_not_blank(cls, v: str | None) -> str | None:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Full name cannot be empty or whitespace.")
            return s
        return v


class EmployeeRoleAssign(BaseModel):
    role_id: int = Field(..., description="Role ID to assign to employee")


class EmployeeResponse(BaseModel):
    id: int
    employee_code: str
    full_name: str
    email: str | None
    department_id: int | None
    location_id: int | None
    enrollment_status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    roles: list[RoleResponse] = []

    model_config = {"from_attributes": True}


class EmployeeDetailResponse(EmployeeResponse):
    department_name: str | None = None
    location_name: str | None = None

