import math
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, field_validator


def validate_polygon_coordinates(v: Any) -> list[list[float]]:
    """
    Validate polygon points coordinates:
    - Must be a list of at least 3 distinct vertices.
    - Each vertex must be [x, y] with finite numeric values.
    - Stored as normalized coordinates in range [0.0, 1.0].
    """
    if not isinstance(v, (list, tuple)):
        raise ValueError("Polygon points must be a list of coordinate pairs [[x, y], ...].")

    if len(v) < 3:
        raise ValueError("Polygon must contain at least 3 distinct vertices.")

    validated: list[list[float]] = []
    unique_points: set[tuple[float, float]] = set()

    for idx, pt in enumerate(v):
        if not isinstance(pt, (list, tuple)) or len(pt) != 2:
            raise ValueError(f"Vertex at index {idx} must be a 2-element coordinate [x, y].")

        x, y = pt[0], pt[1]

        # Check for numeric type (excluding bool)
        if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise ValueError(f"Vertex at index {idx} coordinates must be finite numbers.")

        # Check for NaN and Inf
        if math.isnan(x) or math.isinf(x) or math.isnan(y) or math.isinf(y):
            raise ValueError(f"Vertex at index {idx} coordinates cannot be NaN or Infinite.")

        # Range check: normalized coordinates [0.0, 1.0]
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise ValueError(
                f"Vertex at index {idx} ({x}, {y}) is out of normalized range [0.0, 1.0]."
            )

        fx, fy = float(x), float(y)
        validated.append([fx, fy])
        unique_points.add((round(fx, 6), round(fy, 6)))

    if len(unique_points) < 3:
        raise ValueError("Polygon must contain at least 3 distinct vertices.")

    return validated


class WorkstationZoneBase(BaseModel):
    zone_code: str = Field(..., min_length=1, max_length=100, description="Unique workstation zone identifier")
    name: str = Field(..., min_length=1, max_length=150, description="Human-readable zone name")
    location_id: int = Field(..., description="ID of location where zone is located")
    camera_id: int = Field(..., description="ID of camera monitoring this zone")
    polygon_points: list[list[float]] = Field(
        ...,
        description="Normalized polygon vertices [[x, y], ...] in range [0.0, 1.0]",
    )
    assigned_employee_id: int | None = Field(None, description="Optional assigned employee ID")
    department_id: int | None = Field(None, description="Optional department ID")
    inactivity_threshold_seconds: int = Field(
        900,
        gt=0,
        description="Threshold in seconds before inactivity alert triggers (default: 900s / 15m)",
    )
    is_active: bool = Field(True, description="Zone active state")

    @field_validator("zone_code", "name")
    @classmethod
    def validate_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Value cannot be empty or whitespace.")
        return s

    @field_validator("polygon_points", mode="before")
    @classmethod
    def validate_polygon(cls, v: Any) -> list[list[float]]:
        return validate_polygon_coordinates(v)


class WorkstationZoneCreate(WorkstationZoneBase):
    pass


class WorkstationZoneUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    zone_code: str | None = Field(None, min_length=1, max_length=100)
    camera_id: int | None = None
    polygon_points: list[list[float]] | None = None
    assigned_employee_id: int | None = None
    department_id: int | None = None
    inactivity_threshold_seconds: int | None = Field(None, gt=0)
    is_active: bool | None = None

    @field_validator("name", "zone_code")
    @classmethod
    def validate_not_blank(cls, v: str | None) -> str | None:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Value cannot be empty or whitespace.")
            return s
        return v

    @field_validator("polygon_points", mode="before")
    @classmethod
    def validate_polygon(cls, v: Any) -> list[list[float]] | None:
        if v is not None:
            return validate_polygon_coordinates(v)
        return None


class ZoneEmployeeAssign(BaseModel):
    employee_id: int = Field(..., description="ID of employee to assign to this zone")


class WorkstationZoneResponse(BaseModel):
    id: int
    zone_code: str
    name: str
    location_id: int
    camera_id: int
    polygon_points: list[list[float]]
    assigned_employee_id: int | None
    department_id: int | None
    inactivity_threshold_seconds: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkstationZoneDetailResponse(WorkstationZoneResponse):
    location_name: str | None = None
    camera_name: str | None = None
    camera_code: str | None = None
    assigned_employee_name: str | None = None
    department_name: str | None = None
