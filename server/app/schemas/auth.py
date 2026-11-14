from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Schema for user login credentials."""
    email: EmailStr
    password: str = Field(..., min_length=1, description="Account password")


class UserResponse(BaseModel):
    """Public user profile schema (never exposes password_hash)."""
    id: int
    email: str
    full_name: str
    system_role: str
    is_active: bool
    employee_id: int | None = None
    last_login_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """JWT access token response schema."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token validity duration in seconds")
    expires_at: datetime = Field(..., description="UTC timestamp when token expires")
    user: UserResponse


class LogoutResponse(BaseModel):
    """Response returned upon user logout."""
    status: str = "success"
    message: str = (
        "Successfully logged out. Please remove stored authentication tokens from client storage."
    )

