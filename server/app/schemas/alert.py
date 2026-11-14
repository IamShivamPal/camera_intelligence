from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

VALID_ALERT_TYPES = {
    "employee_inactivity",
    "after_hours_intrusion",
    "after_hours_employee",
    "unknown_guest",
    "camera_offline",
}

VALID_SEVERITIES = {
    "low",
    "medium",
    "high",
    "critical",
}

VALID_STATUSES = {
    "open",
    "acknowledged",
    "resolved",
    "false_positive",
}


class AlertCreate(BaseModel):
    location_id: int = Field(..., description="Location ID where alert occurred")
    alert_type: str = Field(..., description="Alert type matching ck_alert_type")
    title: str = Field(..., min_length=1, max_length=200, description="Short human-readable title")
    severity: str = Field("medium", description="Severity: low, medium, high, critical")
    description: str | None = Field(None, max_length=1000, description="Detailed alert description")
    camera_id: int | None = Field(None, description="Optional associated camera ID")
    employee_id: int | None = Field(None, description="Optional associated employee ID")
    workstation_zone_id: int | None = Field(None, description="Optional workstation zone ID")
    detection_event_id: int | None = Field(None, description="Triggering detection event ID")
    presence_session_id: int | None = Field(None, description="Associated presence session ID")
    guest_visit_id: int | None = Field(None, description="Associated guest visit ID")
    triggered_at: datetime | None = Field(None, description="Timestamp alert triggered (defaults to now)")

    @field_validator("alert_type")
    @classmethod
    def validate_alert_type(cls, v: str) -> str:
        clean = v.strip().lower() if isinstance(v, str) else ""
        if clean not in VALID_ALERT_TYPES:
            raise ValueError(
                f"Invalid alert_type '{v}'. Must be one of: {', '.join(sorted(VALID_ALERT_TYPES))}."
            )
        return clean

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        clean = v.strip().lower() if isinstance(v, str) else ""
        if clean not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{v}'. Must be one of: {', '.join(sorted(VALID_SEVERITIES))}."
            )
        return clean


class AlertUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    severity: str | None = None
    resolution_notes: str | None = Field(None, max_length=500)

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str | None) -> str | None:
        if v is None:
            return None
        clean = v.strip().lower() if isinstance(v, str) else ""
        if clean not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{v}'. Must be one of: {', '.join(sorted(VALID_SEVERITIES))}."
            )
        return clean


class AlertResolveRequest(BaseModel):
    resolution_notes: str | None = Field(None, max_length=500, description="Resolution or triage notes")
    is_false_positive: bool = Field(False, description="Whether to mark this alert as a false positive")


class AlertResponse(BaseModel):
    id: int
    location_id: int
    camera_id: int | None
    alert_type: str
    severity: str
    status: str
    title: str
    description: str | None
    employee_id: int | None
    workstation_zone_id: int | None
    presence_session_id: int | None
    guest_visit_id: int | None
    detection_event_id: int | None
    triggered_at: datetime
    acknowledged_by_user_id: int | None
    acknowledged_at: datetime | None
    resolved_by_user_id: int | None
    resolved_at: datetime | None
    resolution_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertDetailResponse(AlertResponse):
    location_name: str | None = None
    camera_name: str | None = None
    camera_code: str | None = None
    employee_name: str | None = None
    employee_code: str | None = None
    zone_name: str | None = None
    acknowledged_by_user_email: str | None = None
    resolved_by_user_email: str | None = None

