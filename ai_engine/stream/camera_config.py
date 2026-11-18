"""
Camera Configuration, Status, and Telemetry Models
"""

import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Any


class CameraStatus(str, Enum):
    """Lifecycle status of a camera stream."""
    STOPPED = "stopped"
    CONNECTING = "connecting"
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    ERROR = "error"


@dataclass
class CameraConfig:
    """Configuration for a single camera stream."""
    camera_id: int
    camera_code: str
    name: str
    stream_uri: str
    location_id: int
    camera_role: str = "general"  # 'entry_exit', 'workstation', 'perimeter', 'general'
    sampling_fps: float = 5.0
    queue_size: int = 15
    reconnect_interval_seconds: float = 3.0
    max_reconnect_attempts: int = 0  # 0 = infinite retry
    read_timeout_seconds: float = 5.0
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.sampling_fps <= 0:
            raise ValueError("sampling_fps must be positive")
        if self.queue_size <= 0:
            raise ValueError("queue_size must be positive")
        if self.read_timeout_seconds <= 0:
            raise ValueError("read_timeout_seconds must be positive")


@dataclass
class StreamHealth:
    """Operational telemetry and health metrics for a camera stream."""
    camera_id: int
    camera_code: str
    status: CameraStatus = CameraStatus.STOPPED
    fps_captured: float = 0.0
    fps_sampled: float = 0.0
    total_frames_read: int = 0
    total_frames_sampled: int = 0
    total_frames_dropped: int = 0
    total_reconnects: int = 0
    last_frame_timestamp: float | None = None
    last_error: str | None = None
    started_at: float | None = None

    @property
    def uptime_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        return max(0.0, time.time() - self.started_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "camera_code": self.camera_code,
            "status": self.status.value,
            "fps_captured": round(self.fps_captured, 2),
            "fps_sampled": round(self.fps_sampled, 2),
            "total_frames_read": self.total_frames_read,
            "total_frames_sampled": self.total_frames_sampled,
            "total_frames_dropped": self.total_frames_dropped,
            "total_reconnects": self.total_reconnects,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "last_frame_age_seconds": (
                round(time.time() - self.last_frame_timestamp, 2)
                if self.last_frame_timestamp
                else None
            ),
            "last_error": self.last_error,
        }
