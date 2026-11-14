from datetime import datetime, time
from typing import Any
from pydantic import BaseModel, Field, field_validator


DAY_NAME_TO_INT: dict[str, int] = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

INT_TO_DAY_NAME: dict[int, str] = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}


def parse_day_of_week(v: Any) -> int:
    """Parse day_of_week from integer (0-6) or day name string."""
    if isinstance(v, int):
        if not (0 <= v <= 6):
            raise ValueError(f"day_of_week must be between 0 (Monday) and 6 (Sunday), got {v}.")
        return v
    if isinstance(v, str):
        clean = v.strip().lower()
        if clean.isdigit():
            val = int(clean)
            if not (0 <= val <= 6):
                raise ValueError(f"day_of_week must be between 0 and 6, got {val}.")
            return val
        if clean in DAY_NAME_TO_INT:
            return DAY_NAME_TO_INT[clean]
        raise ValueError(
            f"Invalid day_of_week '{v}'. Expected 0-6 or day name (e.g. 'Monday', 'Friday')."
        )
    raise ValueError("day_of_week must be an integer (0-6) or string day name.")


class LocationScheduleBase(BaseModel):
    day_of_week: int = Field(
        ...,
        description="Day of week: 0=Monday, 1=Tuesday, ..., 6=Sunday",
    )
    is_working_day: bool = Field(True, description="Whether location is operational on this day")
    open_time: time | None = Field(None, description="Opening time (HH:MM:SS)")
    close_time: time | None = Field(None, description="Closing time (HH:MM:SS)")
    after_hours_grace_minutes: int = Field(
        15,
        ge=0,
        description="Grace period in minutes before raising after-hours alerts (>= 0)",
    )

    @field_validator("day_of_week", mode="before")
    @classmethod
    def validate_day(cls, v: Any) -> int:
        return parse_day_of_week(v)

    @field_validator("close_time")
    @classmethod
    def validate_times(cls, v: time | None, info) -> time | None:
        open_t = info.data.get("open_time")
        if open_t is not None and v is not None:
            if open_t == v:
                raise ValueError("open_time and close_time cannot be identical.")
        return v


class LocationScheduleCreate(LocationScheduleBase):
    pass


class LocationScheduleUpdate(BaseModel):
    is_working_day: bool | None = None
    open_time: time | None = None
    close_time: time | None = None
    after_hours_grace_minutes: int | None = Field(None, ge=0)

    @field_validator("close_time")
    @classmethod
    def validate_times(cls, v: time | None, info) -> time | None:
        open_t = info.data.get("open_time")
        if open_t is not None and v is not None:
            if open_t == v:
                raise ValueError("open_time and close_time cannot be identical.")
        return v


class LocationScheduleResponse(BaseModel):
    id: int
    location_id: int
    day_of_week: int
    day_name: str
    is_working_day: bool
    open_time: time | None
    close_time: time | None
    after_hours_grace_minutes: int
    is_overnight: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LocationScheduleListResponse(BaseModel):
    location_id: int
    location_name: str
    timezone: str
    schedules: list[LocationScheduleResponse]

