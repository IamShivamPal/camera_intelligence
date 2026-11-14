import math
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator

VALID_EVENT_TYPES = {
    "employee_recognized",
    "unknown_person",
    "workstation_active",
    "workstation_idle",
    "after_hours_employee",
    "after_hours_intrusion",
    "guest_entry",
    "guest_exit",
}


def validate_confidence_score(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError("Confidence must be a numeric float.")
    if math.isnan(v) or math.isinf(v):
        raise ValueError("Confidence cannot be NaN or Infinite.")
    fval = float(v)
    if not (0.0 <= fval <= 1.0):
        raise ValueError(f"Confidence score must be between 0.0 and 1.0, got {fval}.")
    return fval


class DetectionEventCreate(BaseModel):
    camera_id: int = Field(..., description="ID of camera that captured the event")
    event_type: str = Field(..., description="Event type matching ck_detection_event_type")
    location_id: int | None = Field(
        None,
        description="Optional location ID; if provided, must match camera's location",
    )
    occurred_at: datetime | None = Field(
        None,
        description="Event timestamp in ISO format (defaults to current time)",
    )
    employee_id: int | None = Field(
        None,
        description="ID of identified employee, if recognized",
    )
    workstation_zone_id: int | None = Field(
        None,
        description="ID of workstation zone, if event is zone-related",
    )
    presence_session_id: int | None = Field(
        None,
        description="Optional presence session ID to link directly",
    )
    guest_visit_id: int | None = Field(
        None,
        description="Optional guest visit ID to link directly",
    )
    confidence: float | None = Field(
        None,
        description="Detection confidence score between 0.0 and 1.0",
    )
    tracker_id: str | None = Field(
        None,
        max_length=64,
        description="Ephemeral stream tracking ID (e.g. ByteTrack). Never used as identity.",
    )
    snapshot_ref: str | None = Field(
        None,
        max_length=255,
        description="Storage reference path for visual snapshot (never raw bytes)",
    )
    metadata_json: dict[str, Any] | None = Field(
        None,
        description="Structured telemetry metadata (bounding boxes, pose, attributes)",
    )

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        clean = v.strip().lower() if isinstance(v, str) else ""
        if clean not in VALID_EVENT_TYPES:
            raise ValueError(
                f"Invalid event_type '{v}'. Must be one of: {', '.join(sorted(VALID_EVENT_TYPES))}."
            )
        return clean

    @field_validator("confidence", mode="before")
    @classmethod
    def check_confidence(cls, v: Any) -> float | None:
        return validate_confidence_score(v)


class DetectionEventResponse(BaseModel):
    id: int
    location_id: int
    camera_id: int
    event_type: str
    occurred_at: datetime
    employee_id: int | None
    workstation_zone_id: int | None
    presence_session_id: int | None
    guest_visit_id: int | None
    confidence: float | None
    tracker_id: str | None
    snapshot_ref: str | None
    metadata_json: dict[str, Any] | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DetectionEventDetailResponse(DetectionEventResponse):
    location_name: str | None = None
    camera_name: str | None = None
    camera_code: str | None = None
    employee_name: str | None = None
    employee_code: str | None = None
    zone_name: str | None = None
    alert_ids: list[int] = Field(default_factory=list)

