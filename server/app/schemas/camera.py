import re
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class CameraRole(str, Enum):
    ENTRY_EXIT = "entry_exit"
    WORKSTATION = "workstation"
    PERIMETER = "perimeter"
    GENERAL = "general"


class StreamType(str, Enum):
    RTSP = "rtsp"
    WEBCAM = "webcam"
    FILE = "file"
    ONVIF = "onvif"


class ConnectionStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class WorkstationZoneSummary(BaseModel):
    id: int
    zone_code: str
    name: str
    location_id: int
    camera_id: int
    is_active: bool

    model_config = {"from_attributes": True}


class CameraBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150, description="Display name for the camera")
    camera_code: str = Field(..., min_length=1, max_length=100, description="Unique camera identifier")
    location_id: int = Field(..., description="ID of location where camera is deployed")
    camera_role: str = Field(
        "general",
        pattern="^(entry_exit|workstation|perimeter|general)$",
        description="Functional camera role",
    )
    stream_type: str = Field(
        "rtsp",
        pattern="^(rtsp|webcam|file|onvif)$",
        description="Stream ingestion protocol",
    )
    stream_secret_ref: str | None = Field(
        None,
        max_length=255,
        description="Secret manager key or reference pointer (never store plaintext credentials)",
    )
    connection_status: str = Field(
        "unknown",
        pattern="^(online|offline|degraded|unknown)$",
        description="Health / connectivity status",
    )
    is_active: bool = Field(True, description="Active status")

    @field_validator("name", "camera_code")
    @classmethod
    def validate_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Value cannot be empty or whitespace.")
        return s

    @field_validator("stream_secret_ref")
    @classmethod
    def validate_no_raw_credentials(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        # Reject raw inline credentials like rtsp://user:pass@host or ://...:...@
        if re.search(r"://[^/]+:[^/]+@", s) or ("@" in s and ":" in s.split("@")[0]):
            raise ValueError(
                "Plaintext credentials or inline authentication (user:password@) are strictly prohibited in stream_secret_ref. Use a reference key or vault path instead."
            )
        return s if s else None


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    camera_code: str | None = Field(None, min_length=1, max_length=100)
    location_id: int | None = None
    camera_role: str | None = Field(None, pattern="^(entry_exit|workstation|perimeter|general)$")
    stream_type: str | None = Field(None, pattern="^(rtsp|webcam|file|onvif)$")
    stream_secret_ref: str | None = Field(None, max_length=255)
    connection_status: str | None = Field(None, pattern="^(online|offline|degraded|unknown)$")
    is_active: bool | None = None

    @field_validator("name", "camera_code")
    @classmethod
    def validate_not_blank(cls, v: str | None) -> str | None:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Value cannot be empty or whitespace.")
            return s
        return v

    @field_validator("stream_secret_ref")
    @classmethod
    def validate_no_raw_credentials(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if re.search(r"://[^/]+:[^/]+@", s) or ("@" in s and ":" in s.split("@")[0]):
            raise ValueError(
                "Plaintext credentials or inline authentication (user:password@) are strictly prohibited in stream_secret_ref. Use a reference key or vault path instead."
            )
        return s if s else None


class CameraResponse(BaseModel):
    id: int
    camera_code: str
    name: str
    location_id: int
    camera_role: str
    stream_type: str
    stream_secret_ref: str | None
    connection_status: str
    last_heartbeat_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CameraDetailResponse(CameraResponse):
    location_name: str | None = None
    workstation_zones: list[WorkstationZoneSummary] = []
    detection_event_count: int = 0
    alert_count: int = 0

