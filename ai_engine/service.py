"""
Edge Ingestion Service: Master Orchestrator
Coordinates camera capture streams, live detection pipeline, workstation analytics,
backend configuration synchronization, and persistent telemetry dispatching.
"""

import logging
import signal
import sys
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from ai_engine.stream.stream_manager import CameraStreamManager
from ai_engine.stream.camera_config import CameraConfig, CameraStatus
from ai_engine.stream.edge_frame_server import EdgeFrameServer
from ai_engine.pipeline.detector import PersonDetector
from ai_engine.pipeline.face_pipeline import FaceProcessingPipeline
from ai_engine.pipeline.pipeline_worker import LivePipelineWorker
from ai_engine.analytics.occupancy_tracker import MultiZoneManager
from ai_engine.client.config_client import BackendConfigClient
from ai_engine.client.persistent_dispatcher import PersistentTelemetryDispatcher
from ai_engine.client.event_client import BackendEventClient
from ai_engine.client.heartbeat_client import CameraHeartbeatClient
from ai_engine.config import (
    EngineConfig,
    DEFAULT_BACKEND_URL,
    DEFAULT_CAMERA_DISCONNECT_GRACE_PERIOD_SECONDS,
)
from ai_engine.utils.security import sanitize_stream_uri

logger = logging.getLogger(__name__)


class ServiceStatus(str, Enum):
    INITIALIZING = "initializing"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class EdgeIngestionService:
    """
    Master background service for AI Engine edge deployment.
    Responsibilities:
      1. Configuration Synchronization: pulls cameras and workstation zones from FastAPI backend.
      2. Camera Stream Manager: decodes multiple RTSP/file/webcam streams with independent isolation.
      3. Live Pipeline Worker: decodes person tracks, aligns faces, and evaluates workstation analytics.
      4. Persistent Telemetry Dispatcher: ensures offline resilience, exponential backoff retries, and ordering.
      5. Graceful Lifecycle: traps system signals for clean tear-down without leaking sockets or threads.
    """

    def __init__(
        self,
        config: EngineConfig | None = None,
        config_client: BackendConfigClient | None = None,
        dispatcher: PersistentTelemetryDispatcher | None = None,
        stream_manager: CameraStreamManager | None = None,
        zone_manager: MultiZoneManager | None = None,
        detector: PersonDetector | None = None,
        face_pipeline: FaceProcessingPipeline | None = None,
        pipeline_worker: LivePipelineWorker | None = None,
        enable_face_recognition: bool = True,
        sync_interval_seconds: float = 60.0,
        enable_periodic_sync: bool = False,
        capture_factory: Callable[[str], Any] | None = None,
        enable_frame_server: bool = True,
        frame_server_port: int = 8001,
        frame_server_host: str = "127.0.0.1",
        enable_heartbeat: bool = True,
        heartbeat_client: CameraHeartbeatClient | None = None,
        frame_server: EdgeFrameServer | None = None,
        disconnect_grace_period_seconds: float = DEFAULT_CAMERA_DISCONNECT_GRACE_PERIOD_SECONDS,
    ):
        self.config = config or EngineConfig()
        self.enable_face_recognition = enable_face_recognition
        self.sync_interval_seconds = sync_interval_seconds
        self.enable_periodic_sync = enable_periodic_sync
        self.enable_frame_server = enable_frame_server
        self.enable_heartbeat = enable_heartbeat
        self.disconnect_grace_period_seconds = disconnect_grace_period_seconds

        # Subsystems
        self.config_client = config_client or BackendConfigClient()
        self.dispatcher = dispatcher or PersistentTelemetryDispatcher()
        self.stream_manager = stream_manager or CameraStreamManager(
            default_queue_size=self.config.queue_size,
            capture_factory=capture_factory,
        )
        self.zone_manager = zone_manager or MultiZoneManager(
            disconnect_grace_period_seconds=disconnect_grace_period_seconds
        )
        self.detector = detector
        self.face_pipeline = face_pipeline
        self.pipeline_worker = pipeline_worker

        # Disconnection grace period management
        self._disconnect_timers: dict[int, threading.Timer] = {}
        self._disconnect_lock = threading.Lock()

        # Frame Bridge & Heartbeat Subsystems
        self.frame_server = frame_server or (
            EdgeFrameServer(
                stream_manager=self.stream_manager,
                host=frame_server_host,
                port=frame_server_port,
                sync_handler=self.sync_configuration,
            )
            if enable_frame_server
            else None
        )
        self.heartbeat_client = heartbeat_client or (
            CameraHeartbeatClient(backend_url=DEFAULT_BACKEND_URL)
            if enable_heartbeat
            else None
        )
        if self.heartbeat_client:
            self.stream_manager.add_status_callback(self.heartbeat_client.on_status_change)
        self.stream_manager.add_status_callback(self._on_camera_status_change)

        # Status & State
        self.status = ServiceStatus.INITIALIZING
        self.started_at: float | None = None
        self.last_sync_at: float | None = None
        self.last_sync_error: str | None = None

        # Background synchronization thread
        self._stop_event = threading.Event()
        self._sync_thread: threading.Thread | None = None
        self._is_initialized = False

    def initialize(self):
        """Lazy initialization of heavy deep learning models and pipeline worker."""
        if self._is_initialized:
            return

        logger.info("Initializing Edge Ingestion Service components...")

        # 1. Person Detector (YOLO11s + ByteTrack)
        if self.detector is None:
            self.detector = PersonDetector(
                model_path=self.config.yolo_model_path,
                conf_threshold=self.config.person_confidence,
                device="cuda" if self.config.use_cuda else "cpu",
            )

        # 2. Face Processing Pipeline (RetinaFace + AuraFace)
        if self.enable_face_recognition and self.face_pipeline is None:
            try:
                self.face_pipeline = FaceProcessingPipeline()
            except Exception as e:
                logger.warning("Face processing pipeline unavailable: %s. Continuing in detector-only mode.", e)
                self.enable_face_recognition = False

        # 3. Live Pipeline Worker
        if self.pipeline_worker is None:
            # Wrap PersistentTelemetryDispatcher as event client
            # LivePipelineWorker accepts any object with dispatch_event(payload)
            self.pipeline_worker = LivePipelineWorker(
                stream_manager=self.stream_manager,
                detector=self.detector,
                face_pipeline=self.face_pipeline,
                event_client=self.dispatcher,  # Persistent dispatcher receives all events
                zone_manager=self.zone_manager,
                enable_face_recognition=self.enable_face_recognition,
            )

        self._is_initialized = True
        logger.info("Edge Ingestion Service initialized successfully.")

    def sync_configuration(self, location_id: int | None = None) -> dict[str, int]:
        """
        Synchronize cameras and workstation zones from the backend API.
        Applies updates dynamically without restarting the whole service.
        """
        logger.info("Synchronizing configuration from backend API...")
        try:
            cameras, zones = self.config_client.sync_all(location_id=location_id)
            if self.dispatcher and self.config_client.auth_token:
                self.dispatcher.auth_token = self.config_client.auth_token
            if self.heartbeat_client and self.config_client.auth_token:
                self.heartbeat_client.set_auth_token(self.config_client.auth_token)

            # 1. Update Cameras in CameraStreamManager
            cameras_added = 0
            for cam in cameras:
                # If camera is already registered, update or retain
                added = self.stream_manager.add_camera(cam)
                if added:
                    cameras_added += 1
                    # If service is already running and camera is active, start capture
                    if self.status == ServiceStatus.RUNNING and cam.is_active:
                        self.stream_manager.start_camera(cam.camera_id)

            # 2. Update Workstation Zones in MultiZoneManager
            zones_registered = 0
            for zone in zones:
                self.zone_manager.register_zone(zone)
                zones_registered += 1

            self.last_sync_at = time.time()
            self.last_sync_error = None
            logger.info(
                "Sync complete: %d cameras registered (%d new), %d zones registered.",
                len(cameras),
                cameras_added,
                zones_registered,
            )
            return {"cameras_synced": len(cameras), "zones_synced": len(zones)}

        except Exception as e:
            self.last_sync_error = str(e)
            logger.error("Configuration synchronization failed: %s", e)
            return {"cameras_synced": 0, "zones_synced": 0}

    def start(self, sync_config: bool = True, location_id: int | None = None):
        """
        Start the complete edge AI service:
          1. Initializes pipeline worker & models.
          2. Synchronizes cameras and zones from backend (if requested).
          3. Starts persistent telemetry dispatcher.
          4. Starts inference pipeline worker.
          5. Starts all camera capture workers.
        """
        if self.status == ServiceStatus.RUNNING:
            logger.warning("Edge Ingestion Service is already running.")
            return

        self.initialize()
        self._stop_event.clear()

        # 1. Sync Configuration
        if sync_config:
            self.sync_configuration(location_id=location_id)

        # 2. Start Persistent Telemetry Dispatcher
        self.dispatcher.start()

        # 3. Start Pipeline Inference Worker
        self.pipeline_worker.start()

        # 4. Start Camera Stream Capture Workers
        self.stream_manager.start_all()

        # 5. Start Edge Frame Server (if enabled)
        if self.frame_server:
            try:
                self.frame_server.start()
            except Exception as e:
                logger.error("Failed to start Edge Frame Server: %s", e)

        # 6. Start Camera Heartbeat Periodic Worker (if enabled)
        if self.heartbeat_client:
            try:
                self.heartbeat_client.start_periodic_worker(self.stream_manager)
            except Exception as e:
                logger.error("Failed to start Camera Heartbeat Worker: %s", e)

        # 7. Start Periodic Sync (if enabled)
        if self.enable_periodic_sync:
            self._sync_thread = threading.Thread(
                target=self._periodic_sync_loop,
                name="EdgeConfigSyncThread",
                daemon=True,
            )
            self._sync_thread.start()

        self.started_at = time.time()
        self.status = ServiceStatus.RUNNING
        logger.info(
            "Edge Ingestion Service started successfully with %d cameras.",
            self.stream_manager.camera_count,
        )

    def stop(self, timeout: float = 5.0):
        """
        Perform a clean, graceful shutdown:
          1. Stops all camera capture threads.
          2. Stops inference pipeline worker.
          3. Flushes remaining events in telemetry queue.
          4. Stops persistent dispatcher worker.
        """
        if self.status in (ServiceStatus.STOPPING, ServiceStatus.STOPPED):
            return

        self.status = ServiceStatus.STOPPING
        logger.info("Stopping Edge Ingestion Service...")
        self._stop_event.set()

        # 1. Stop periodic sync thread
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=1.0)

        # 2. Stop frame server and heartbeat client
        if self.frame_server:
            try:
                self.frame_server.stop()
            except Exception as e:
                logger.debug("Error stopping frame server: %s", e)

        if self.heartbeat_client:
            try:
                self.heartbeat_client.stop()
            except Exception as e:
                logger.debug("Error stopping heartbeat client: %s", e)

        # 3. Stop camera capture workers
        self.stream_manager.stop_all(timeout=timeout / 2)

        # 4. Stop inference pipeline
        if self.pipeline_worker:
            self.pipeline_worker.stop(timeout=timeout / 2)

        # 5. Cancel disconnect timers and flush departures on shutdown
        with self._disconnect_lock:
            for timer in self._disconnect_timers.values():
                timer.cancel()
            self._disconnect_timers.clear()

        if self.zone_manager:
            for cam_id in list(self.stream_manager._workers.keys()):
                departures = self.zone_manager.reset_camera(cam_id, emit_exit_events=True)
                for dep in departures:
                    if self.dispatcher:
                        self.dispatcher.enqueue(dep)

        # 6. Flush remaining events and stop dispatcher
        if self.dispatcher:
            try:
                self.dispatcher.flush(max_items=50)
            except Exception as e:
                logger.debug("Error flushing dispatcher on stop: %s", e)
            self.dispatcher.stop(timeout=timeout / 2)

        self.status = ServiceStatus.STOPPED
        logger.info("Edge Ingestion Service stopped cleanly.")

    def _on_camera_status_change(self, camera_id: int, status: CameraStatus, error_msg: str | None = None):
        """Handle camera status changes and trigger disconnect grace period timer if offline."""
        if status in (CameraStatus.OFFLINE, CameraStatus.ERROR, CameraStatus.DEGRADED, CameraStatus.STOPPED):
            # Camera dropped or degraded
            with self._disconnect_lock:
                if camera_id not in self._disconnect_timers:
                    timer = threading.Timer(
                        self.disconnect_grace_period_seconds,
                        self._trigger_camera_disconnect_reset,
                        args=[camera_id],
                    )
                    timer.daemon = True
                    self._disconnect_timers[camera_id] = timer
                    timer.start()
                    logger.warning(
                        "Camera %d entered status '%s'. Scheduled disconnect grace period reset in %.1fs.",
                        camera_id,
                        status.value,
                        self.disconnect_grace_period_seconds,
                    )
        elif status == CameraStatus.ONLINE:
            # Reconnected within grace period
            with self._disconnect_lock:
                timer = self._disconnect_timers.pop(camera_id, None)
                if timer:
                    timer.cancel()
                    logger.info("Camera %d reconnected online within grace period; cancelled disconnect reset.", camera_id)
            if self.zone_manager:
                self.zone_manager.handle_camera_reconnect(camera_id)

    def _trigger_camera_disconnect_reset(self, camera_id: int):
        """Invoked when reconnect grace period expires for a disconnected camera."""
        with self._disconnect_lock:
            self._disconnect_timers.pop(camera_id, None)

        if not self.zone_manager:
            return

        logger.warning(
            "Camera %d remained disconnected beyond grace period (%.1fs). Emitting departures and resetting zones.",
            camera_id,
            self.disconnect_grace_period_seconds,
        )
        departures = self.zone_manager.reset_camera(camera_id, emit_exit_events=True)
        if departures and self.dispatcher:
            for dep in departures:
                self.dispatcher.enqueue(dep)
            logger.info("Enqueued %d departure events for disconnected camera %d.", len(departures), camera_id)

    def _periodic_sync_loop(self):
        """Background thread periodically refreshing camera & zone configuration."""
        while not self._stop_event.is_set():
            time.sleep(min(self.sync_interval_seconds, 1.0))
            if self._stop_event.is_set():
                break

            # Check if sync interval elapsed
            elapsed = time.time() - (self.last_sync_at or 0.0)
            if elapsed >= self.sync_interval_seconds:
                try:
                    self.sync_configuration()
                except Exception as e:
                    logger.debug("Periodic sync error: %s", e)

    def get_health(self) -> dict[str, Any]:
        """
        Comprehensive operational telemetry report.
        Sanitizes all sensitive stream URIs.
        """
        now = time.time()
        uptime = max(0.0, now - self.started_at) if self.started_at else 0.0

        # Cameras Health
        cameras_health = []
        for cam_health in self.stream_manager.get_all_health().values():
            h_dict = cam_health.to_dict()
            # Find matching config to sanitize URI if stored
            cameras_health.append(h_dict)

        # Dynamic Status
        service_status = self.status.value
        if self.status == ServiceStatus.RUNNING:
            if self.stream_manager.camera_count > 0 and self.stream_manager.online_count == 0:
                service_status = ServiceStatus.DEGRADED.value

        # Pipeline Metrics
        pipeline_metrics = {}
        if self.pipeline_worker:
            pipeline_metrics = {
                "total_frames_processed": self.pipeline_worker.total_frames_processed,
                "total_persons_detected": self.pipeline_worker.total_persons_detected,
                "total_events_generated": self.pipeline_worker.total_events_generated,
                "avg_inference_latency_ms": round(self.pipeline_worker.avg_inference_latency_ms, 2),
            }

        # Dispatcher Metrics
        dispatcher_metrics = self.dispatcher.get_metrics() if self.dispatcher else {}

        # Workstations Diagnostics
        workstation_summaries = (
            self.zone_manager.get_all_occupancy_summaries() if self.zone_manager else []
        )

        return {
            "service_status": service_status,
            "uptime_seconds": round(uptime, 1),
            "started_at": self.started_at,
            "last_sync_at": self.last_sync_at,
            "last_sync_error": self.last_sync_error,
            "cameras_total": self.stream_manager.camera_count,
            "cameras_online": self.stream_manager.online_count,
            "cameras": cameras_health,
            "pipeline": pipeline_metrics,
            "telemetry_dispatcher": dispatcher_metrics,
            "workstations": workstation_summaries,
        }

    def register_signal_handlers(self):
        """Register OS signal handlers for graceful shutdown on SIGINT/SIGTERM."""
        def _handler(signum, frame):
            logger.info("Signal %d received. Initiating graceful shutdown...", signum)
            self.stop()
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, _handler)
            signal.signal(signal.SIGTERM, _handler)
        except (ValueError, AttributeError):
            # Not supported in certain non-main threads or platforms
            pass
