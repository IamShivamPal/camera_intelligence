"""
Independent Camera RTSP Ingestion Worker
Runs as a dedicated background worker per camera stream with auto-reconnect,
FPS downsampling, timeout detection, and failure isolation.
"""

import logging
import threading
import time
from typing import Callable, Any
import cv2
import numpy as np

from ai_engine.stream.camera_config import CameraConfig, CameraStatus, StreamHealth
from ai_engine.stream.frame_buffer import BoundedFrameBuffer, FrameItem

logger = logging.getLogger(__name__)


class RTSPStreamWorker:
    """
    Dedicated worker thread for capturing, decoding, downsampling,
    and buffering video frames from a single RTSP or video source.
    """

    def __init__(
        self,
        config: CameraConfig,
        buffer: BoundedFrameBuffer | None = None,
        capture_factory: Callable[[str], Any] | None = None,
    ):
        self.config = config
        self.buffer = buffer or BoundedFrameBuffer(maxsize=config.queue_size)
        self.capture_factory = capture_factory or (lambda uri: cv2.VideoCapture(uri))
        self.health = StreamHealth(
            camera_id=config.camera_id,
            camera_code=config.camera_code,
            status=CameraStatus.STOPPED,
        )

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._frame_seq = 0
        self._cap: Any | None = None

        # Thread-safe single-frame latest cache for zero-overhead multi-viewer streaming
        self._latest_frame: FrameItem | None = None
        self._latest_frame_lock = threading.Lock()
        self._on_status_change: Callable[[int, CameraStatus, str | None], None] | None = None
        self._prev_status: CameraStatus = CameraStatus.STOPPED

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _set_status(self, new_status: CameraStatus, error_msg: str | None = None):
        """Update status and notify callback if status changed."""
        old_status = self.health.status
        self.health.status = new_status
        if error_msg is not None:
            self.health.last_error = error_msg
        elif new_status == CameraStatus.ONLINE:
            self.health.last_error = None

        if old_status != new_status and self._on_status_change:
            try:
                self._on_status_change(self.config.camera_id, new_status, self.health.last_error)
            except Exception as e:
                logger.debug("Error in status change callback for %s: %s", self.config.camera_code, e)

    def set_status_callback(self, callback: Callable[[int, CameraStatus, str | None], None]):
        """Register callback for camera status changes."""
        self._on_status_change = callback

    def get_latest_frame(self, max_age_seconds: float = 5.0) -> FrameItem | None:
        """
        Thread-safe access to the most recently decoded video frame.
        Reuses existing RTSP worker buffer without popping or stalling AI inference.
        Returns None if camera is offline/stopped or if the frame age exceeds max_age_seconds.
        """
        if self.health.status not in (CameraStatus.ONLINE, CameraStatus.DEGRADED):
            return None
        with self._latest_frame_lock:
            if self._latest_frame is None:
                return None
            age = time.time() - self._latest_frame.timestamp
            if age > max_age_seconds:
                return None
            return self._latest_frame

    def start(self):
        """Start the stream worker thread."""
        if self.is_running:
            logger.warning("Camera %s worker is already running.", self.config.camera_code)
            return

        self._stop_event.clear()
        self.health.started_at = time.time()
        self._set_status(CameraStatus.CONNECTING)
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"RTSPWorker-{self.config.camera_code}",
            daemon=True,
        )
        self._thread.start()
        logger.info("Started camera worker for %s (URI: %s)", self.config.camera_code, self.config.stream_uri)

    def stop(self, timeout: float = 3.0):
        """Signal worker to stop and wait for thread termination."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._release_capture()
        self.buffer.close()
        self._set_status(CameraStatus.STOPPED)
        logger.info("Stopped camera worker for %s", self.config.camera_code)

    def _release_capture(self):
        """Safely release the VideoCapture resource."""
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception as e:
                logger.debug("Error releasing capture for %s: %s", self.config.camera_code, e)
            finally:
                self._cap = None

    def _open_stream(self) -> bool:
        """Attempt to open the camera stream."""
        self._release_capture()
        self._set_status(CameraStatus.CONNECTING)
        try:
            uri = self.config.stream_uri
            # Support integer webcam indices passed as strings
            if isinstance(uri, str) and uri.isdigit():
                uri = int(uri)

            self._cap = self.capture_factory(uri)

            # Set RTSP low-latency buffer properties where supported
            if hasattr(self._cap, "set"):
                try:
                    self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception:
                    pass

            if not self._cap.isOpened():
                self._set_status(CameraStatus.OFFLINE, f"Failed to open video source: {self.config.stream_uri}")
                return False

            self._set_status(CameraStatus.ONLINE)
            logger.info("Successfully connected to camera %s", self.config.camera_code)
            return True
        except Exception as e:
            self._set_status(CameraStatus.ERROR, f"Connection exception: {str(e)}")
            logger.error("Exception opening camera %s: %s", self.config.camera_code, e)
            return False

    def _run_loop(self):
        """Main acquisition and sampling loop."""
        reconnect_attempts = 0
        backoff = self.config.reconnect_interval_seconds
        sample_interval = 1.0 / self.config.sampling_fps
        last_sample_time = 0.0

        # FPS calculation windows
        read_count_window = 0
        sample_count_window = 0
        window_start = time.time()

        while not self._stop_event.is_set():
            # If not connected, attempt connection with backoff
            if self._cap is None or not self._cap.isOpened():
                is_reconnect = (self.health.total_frames_read > 0 or reconnect_attempts > 0)
                if is_reconnect:
                    reconnect_attempts += 1
                    self.health.total_reconnects = reconnect_attempts

                connected = self._open_stream()
                if not connected:
                    if (
                        self.config.max_reconnect_attempts > 0
                        and reconnect_attempts >= self.config.max_reconnect_attempts
                    ):
                        logger.error(
                            "Camera %s reached max reconnect attempts (%d). Exiting worker.",
                            self.config.camera_code,
                            self.config.max_reconnect_attempts,
                        )
                        self.health.status = CameraStatus.ERROR
                        break

                    # Wait before retrying (responsive to stop_event)
                    self._stop_event.wait(timeout=backoff)
                    backoff = min(backoff * 1.5, 30.0)  # Exponential backoff capped at 30s
                    continue
                else:
                    backoff = self.config.reconnect_interval_seconds
                    last_sample_time = 0.0

            # Stream is open — read next frame
            try:
                ret, frame = self._cap.read()
            except Exception as e:
                logger.warning("Read error on camera %s: %s", self.config.camera_code, e)
                ret, frame = False, None

            now = time.time()

            if not ret or frame is None:
                # Frame read failed or stream reached end
                time_since_last = (
                    now - self.health.last_frame_timestamp
                    if self.health.last_frame_timestamp
                    else self.config.read_timeout_seconds + 1
                )
                if time_since_last > self.config.read_timeout_seconds:
                    logger.warning(
                        "Camera %s read timeout (no frame for %.1fs). Reconnecting...",
                        self.config.camera_code,
                        time_since_last,
                    )
                    self._set_status(CameraStatus.DEGRADED, f"Stream timeout after {time_since_last:.1f}s")
                    self._release_capture()
                    self._stop_event.wait(timeout=min(self.config.reconnect_interval_seconds, 1.0))
                else:
                    time.sleep(0.01)
                continue

            # Valid frame received
            self._frame_seq += 1
            self.health.total_frames_read += 1
            self.health.last_frame_timestamp = now
            self._set_status(CameraStatus.ONLINE)
            read_count_window += 1

            # Window-based FPS update (every 1 second)
            if now - window_start >= 1.0:
                elapsed = now - window_start
                self.health.fps_captured = read_count_window / elapsed
                self.health.fps_sampled = sample_count_window / elapsed
                read_count_window = 0
                sample_count_window = 0
                window_start = now

            # Sampling check: only pass to buffer if sampling interval elapsed
            if (now - last_sample_time) >= sample_interval:
                last_sample_time = now
                self.health.total_frames_sampled += 1
                sample_count_window += 1

                frame_item = FrameItem(
                    frame=frame,
                    frame_id=self._frame_seq,
                    timestamp=now,
                    camera_id=self.config.camera_id,
                    camera_code=self.config.camera_code,
                    location_id=self.config.location_id,
                    camera_role=self.config.camera_role,
                )

                # Store latest frame for zero-overhead bridge access
                with self._latest_frame_lock:
                    self._latest_frame = frame_item

                # Push to bounded buffer
                accepted = self.buffer.put(frame_item)
                if not accepted:
                    self.health.total_frames_dropped = self.buffer.dropped_count

        self._release_capture()
        self._set_status(CameraStatus.STOPPED)
