"""
Camera Health & Heartbeat Dispatcher
Synchronizes camera connection states and telemetry metrics from Edge Ingestion Service
to the FastAPI backend (PostgreSQL database).
"""

import logging
import threading
import time
from typing import Any
import requests

from ai_engine.stream.camera_config import CameraStatus, StreamHealth
from ai_engine.config import DEFAULT_BACKEND_URL

logger = logging.getLogger(__name__)


class CameraHeartbeatClient:
    """
    HTTP client for dispatching camera connectivity state and telemetry metrics.
    Features:
      - Immediate notification on state transitions (e.g., OFFLINE -> ONLINE).
      - Throttled periodic heartbeats for active streams (default: 10 seconds).
      - Never spams the database on every frame.
      - Graceful error handling if backend is temporarily unreachable.
    """

    def __init__(
        self,
        backend_url: str = DEFAULT_BACKEND_URL,
        auth_token: str | None = None,
        heartbeat_interval_seconds: float = 10.0,
        timeout: float = 3.0,
    ):
        self.backend_url = backend_url.rstrip("/")
        self.auth_token = auth_token
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.timeout = timeout

        # Tracking state
        self._last_reported_status: dict[int, str] = {}
        self._last_reported_time: dict[int, float] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._stream_manager: Any = None

    def set_auth_token(self, token: str):
        with self._lock:
            self.auth_token = token

    def on_status_change(self, camera_id: int, status: CameraStatus, error_msg: str | None = None):
        """Immediately dispatch a status update when connection state transitions."""
        threading.Thread(
            target=self._send_single_heartbeat,
            args=(camera_id, status.value, error_msg),
            daemon=True,
            name=f"StatusChange-{camera_id}",
        ).start()

    def _get_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def _send_single_heartbeat(
        self,
        camera_id: int,
        status_str: str,
        error_msg: str | None = None,
        fps_captured: float | None = None,
        total_reconnects: int | None = None,
    ) -> bool:
        """Post a single camera heartbeat to FastAPI backend."""
        with self._lock:
            # Map edge status to backend allowed connection_status
            normalized_status = status_str.lower()
            if normalized_status == "connecting":
                normalized_status = "offline"

            self._last_reported_status[camera_id] = normalized_status
            self._last_reported_time[camera_id] = time.time()

        payload = {
            "connection_status": normalized_status,
            "last_error": error_msg,
            "fps_captured": fps_captured,
            "total_reconnects": total_reconnects,
        }

        url = f"{self.backend_url}/api/v1/cameras/{camera_id}/heartbeat"
        try:
            r = requests.post(url, json=payload, headers=self._get_headers(), timeout=self.timeout)
            if r.status_code == 200:
                logger.debug("Dispatched heartbeat for camera %d: status=%s", camera_id, normalized_status)
                return True
            else:
                logger.debug("Heartbeat returned status %d for camera %d: %s", r.status_code, camera_id, r.text)
                return False
        except Exception as e:
            logger.debug("Failed to dispatch heartbeat to %s for camera %d: %s", url, camera_id, e)
            return False

    def send_batch_heartbeat(self, health_list: list[StreamHealth]) -> bool:
        """Post batch heartbeat for multiple cameras in one HTTP call."""
        if not health_list:
            return True

        items = []
        now = time.time()

        for h in health_list:
            status_val = h.status.value.lower()
            if status_val == "connecting":
                status_val = "offline"

            with self._lock:
                last_time = self._last_reported_time.get(h.camera_id, 0.0)
                last_stat = self._last_reported_status.get(h.camera_id)

                # Skip if reported recently and status unchanged
                if last_stat == status_val and (now - last_time) < self.heartbeat_interval_seconds:
                    continue

                self._last_reported_status[h.camera_id] = status_val
                self._last_reported_time[h.camera_id] = now

            items.append({
                "camera_id": h.camera_id,
                "connection_status": status_val,
                "last_error": h.last_error,
                "fps_captured": round(h.fps_captured, 2),
                "fps_sampled": round(h.fps_sampled, 2),
                "total_reconnects": h.total_reconnects,
            })

        if not items:
            return True

        url = f"{self.backend_url}/api/v1/cameras/heartbeat/batch"
        try:
            r = requests.post(url, json={"items": items}, headers=self._get_headers(), timeout=self.timeout)
            if r.status_code == 200:
                logger.info("Batch heartbeat updated %d cameras.", len(items))
                return True
            else:
                logger.debug("Batch heartbeat returned status %d: %s", r.status_code, r.text)
                return False
        except Exception as e:
            logger.debug("Failed to send batch heartbeat to %s: %s", url, e)
            return False

    def start_periodic_worker(self, stream_manager: Any):
        """Start background thread periodically collecting and reporting health."""
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._stream_manager = stream_manager
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._loop,
            name="CameraHeartbeatWorker",
            daemon=True,
        )
        self._worker_thread.start()
        logger.info("Camera heartbeat worker started.")

    def stop(self, timeout: float = 2.0):
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
        logger.info("Camera heartbeat worker stopped.")

    def _loop(self):
        while not self._stop_event.is_set():
            time.sleep(min(self.heartbeat_interval_seconds, 2.0))
            if self._stop_event.is_set():
                break

            if self._stream_manager:
                health_dict = self._stream_manager.get_all_health()
                if health_dict:
                    self.send_batch_heartbeat(list(health_dict.values()))
