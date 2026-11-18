"""
Backend Event Telemetry Client
Dispatches validated detection events to FastAPI POST /api/v1/events with offline queueing.
"""

import logging
import time
from collections import deque
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Any, Callable
import requests

from ai_engine.config import API_EVENTS_ENDPOINT

logger = logging.getLogger(__name__)

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


@dataclass
class DetectionPayload:
    """Structured telemetry event payload matching backend schema DetectionEventCreate."""
    camera_id: int
    event_type: str
    location_id: int
    confidence: float
    occurred_at: str | None = None
    employee_id: int | None = None
    workstation_zone_id: int | None = None
    presence_session_id: int | None = None
    guest_visit_id: int | None = None
    tracker_id: str | None = None
    snapshot_ref: str | None = None
    metadata_json: dict[str, Any] | None = None

    def __post_init__(self):
        if self.event_type not in VALID_EVENT_TYPES:
            raise ValueError(
                f"Invalid event_type '{self.event_type}'. Must be one of: {sorted(VALID_EVENT_TYPES)}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence score must be in [0.0, 1.0], got {self.confidence}")
        if self.occurred_at is None:
            self.occurred_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


class BackendEventClient:
    """
    HTTP client for dispatching AI detection events to backend API.
    Features:
      - Validates payloads against backend constraints before sending.
      - Maintains bounded local queue for resilience during network interruptions.
      - Never includes raw video frames or biometric vectors.
      - Ephemeral tracker IDs are transmitted as telemetry metadata, never employee IDs.
    """

    def __init__(
        self,
        endpoint_url: str = API_EVENTS_ENDPOINT,
        auth_token: str | None = None,
        timeout: float = 3.0,
        max_queue_size: int = 500,
        transport: Callable[[dict[str, Any]], bool] | None = None,
    ):
        self.endpoint_url = endpoint_url
        self.auth_token = auth_token
        self.timeout = timeout
        self.transport = transport
        self._offline_queue: deque[DetectionPayload] = deque(maxlen=max_queue_size)
        self.total_dispatched = 0
        self.total_queued = 0
        self.total_failed = 0

    def dispatch_event(self, payload: DetectionPayload) -> bool:
        """
        Send a single detection event to backend API.
        If network fails, buffers the payload into the offline queue.
        """
        # If custom transport (e.g. mock test transport) is provided
        if self.transport is not None:
            success = self.transport(payload.to_dict())
            if success:
                self.total_dispatched += 1
                return True
            else:
                self._offline_queue.append(payload)
                self.total_queued += 1
                return False

        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        try:
            resp = requests.post(
                self.endpoint_url,
                json=payload.to_dict(),
                headers=headers,
                timeout=self.timeout,
            )
            if resp.status_code in (200, 201):
                self.total_dispatched += 1
                logger.debug(
                    "Dispatched event %s (camera %d, type=%s)",
                    payload.tracker_id,
                    payload.camera_id,
                    payload.event_type,
                )
                return True
            else:
                logger.warning(
                    "Backend rejected event with HTTP %d: %s",
                    resp.status_code,
                    resp.text,
                )
                self._offline_queue.append(payload)
                self.total_queued += 1
                return False
        except Exception as e:
            logger.debug("Network error dispatching event: %s. Enqueuing offline.", e)
            self._offline_queue.append(payload)
            self.total_queued += 1
            self.total_failed += 1
            return False

    def flush_offline_queue(self) -> int:
        """Attempt to re-send buffered events."""
        if not self._offline_queue:
            return 0

        flushed = 0
        while self._offline_queue:
            payload = self._offline_queue[0]
            if self.dispatch_event(payload):
                self._offline_queue.popleft()
                flushed += 1
            else:
                break
        return flushed

    @property
    def queue_size(self) -> int:
        return len(self._offline_queue)
