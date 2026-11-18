"""
Camera Stream Manager: Multi-camera Lifecycle, Health Monitoring, and Failure Isolation
"""

import logging
import threading
import time
from typing import Callable, Any

from ai_engine.stream.camera_config import CameraConfig, CameraStatus, StreamHealth
from ai_engine.stream.frame_buffer import BoundedFrameBuffer, FrameItem
from ai_engine.stream.rtsp_worker import RTSPStreamWorker

logger = logging.getLogger(__name__)


class CameraStreamManager:
    """
    Central manager for multi-camera video streams.
    - Isolates failures: one camera dropping does not affect others.
    - Provides thread-safe frame access across all cameras.
    - Collects unified health telemetry.
    """

    def __init__(
        self,
        default_queue_size: int = 15,
        capture_factory: Callable[[str], Any] | None = None,
    ):
        self.default_queue_size = default_queue_size
        self.capture_factory = capture_factory
        self._workers: dict[int, RTSPStreamWorker] = {}
        self._lock = threading.Lock()
        self._merged_buffer = BoundedFrameBuffer(maxsize=default_queue_size * 2)
        self._status_callbacks: list[Callable[[int, CameraStatus, str | None], None]] = []

    def _dispatch_status_change(self, camera_id: int, status: CameraStatus, error_msg: str | None):
        with self._lock:
            callbacks = list(self._status_callbacks)
        for cb in callbacks:
            try:
                cb(camera_id, status, error_msg)
            except Exception as e:
                logger.debug("Error in camera status callback: %s", e)

    def add_status_callback(self, callback: Callable[[int, CameraStatus, str | None], None]):
        """Register an additional callback for camera status change events."""
        with self._lock:
            if callback not in self._status_callbacks:
                self._status_callbacks.append(callback)
            for worker in self._workers.values():
                worker.set_status_callback(self._dispatch_status_change)

    def set_status_callback(self, callback: Callable[[int, CameraStatus, str | None], None]):
        """Register a callback for camera status change events across all workers."""
        with self._lock:
            self._status_callbacks = [callback]
            for worker in self._workers.values():
                worker.set_status_callback(self._dispatch_status_change)

    def add_camera(self, config: CameraConfig) -> bool:
        """Register a new camera configuration and instantiate its worker."""
        with self._lock:
            if config.camera_id in self._workers:
                logger.warning("Camera ID %d already registered.", config.camera_id)
                return False

            # Dedicated buffer for this camera
            cam_buffer = BoundedFrameBuffer(maxsize=config.queue_size)
            worker = RTSPStreamWorker(
                config=config,
                buffer=cam_buffer,
                capture_factory=self.capture_factory,
            )
            if self._status_callbacks:
                worker.set_status_callback(self._dispatch_status_change)
            self._workers[config.camera_id] = worker
            logger.info("Registered camera %s (ID: %d)", config.camera_code, config.camera_id)
            return True

    def remove_camera(self, camera_id: int) -> bool:
        """Stop and remove a camera worker from the registry."""
        with self._lock:
            worker = self._workers.pop(camera_id, None)

        if worker:
            worker.stop()
            logger.info("Removed camera ID %d", camera_id)
            return True
        return False

    def start_camera(self, camera_id: int) -> bool:
        """Start streaming for a specific camera."""
        with self._lock:
            worker = self._workers.get(camera_id)
        if worker:
            worker.start()
            return True
        return False

    def stop_camera(self, camera_id: int) -> bool:
        """Stop streaming for a specific camera."""
        with self._lock:
            worker = self._workers.get(camera_id)
        if worker:
            worker.stop()
            return True
        return False

    def start_all(self):
        """Start all registered camera workers."""
        with self._lock:
            workers = list(self._workers.values())
        for worker in workers:
            if worker.config.is_active:
                worker.start()

    def stop_all(self, timeout: float = 3.0):
        """Gracefully stop and clean up all camera workers."""
        with self._lock:
            workers = list(self._workers.values())
        for worker in workers:
            worker.stop(timeout=timeout)
        self._merged_buffer.close()
        logger.info("All camera stream workers stopped.")

    def get_frame(self, camera_id: int, timeout: float = 0.5) -> FrameItem | None:
        """Retrieve the next sampled frame from a specific camera."""
        with self._lock:
            worker = self._workers.get(camera_id)
        if worker:
            return worker.buffer.get(timeout=timeout)
        return None

    def get_latest_frame(self, camera_id: int, max_age_seconds: float = 5.0) -> FrameItem | None:
        """
        Thread-safe access to the most recently decoded frame from a specific camera.
        Reuses the existing RTSP worker buffer without popping or stalling AI inference.
        Returns None if camera is offline, stopped, or if the frame exceeds max_age_seconds.
        """
        with self._lock:
            worker = self._workers.get(camera_id)
        if worker:
            return worker.get_latest_frame(max_age_seconds=max_age_seconds)
        return None

    def get_any_frame(self, timeout: float = 0.5) -> FrameItem | None:
        """
        Poll round-robin across active camera buffers to retrieve the next available frame.
        Non-blocking per camera with short total deadline.
        """
        with self._lock:
            camera_ids = list(self._workers.keys())

        if not camera_ids:
            time.sleep(min(timeout, 0.05))
            return None

        deadline = time.time() + timeout
        while time.time() < deadline:
            for cid in camera_ids:
                with self._lock:
                    worker = self._workers.get(cid)
                if worker and not worker.buffer.is_empty():
                    item = worker.buffer.get(timeout=0.01)
                    if item is not None:
                        return item
            time.sleep(0.01)

        return None

    def get_camera_health(self, camera_id: int) -> StreamHealth | None:
        """Get live health metrics for a specific camera."""
        with self._lock:
            worker = self._workers.get(camera_id)
        return worker.health if worker else None

    def get_all_health(self) -> dict[int, StreamHealth]:
        """Get live health metrics for all cameras."""
        with self._lock:
            return {cid: worker.health for cid, worker in self._workers.items()}

    def get_all_health_dicts(self) -> list[dict[str, Any]]:
        """Get serializable health dictionaries for all cameras."""
        with self._lock:
            return [worker.health.to_dict() for worker in self._workers.values()]

    @property
    def camera_count(self) -> int:
        with self._lock:
            return len(self._workers)

    @property
    def online_count(self) -> int:
        with self._lock:
            return sum(
                1 for w in self._workers.values() if w.health.status == CameraStatus.ONLINE
            )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_all()
