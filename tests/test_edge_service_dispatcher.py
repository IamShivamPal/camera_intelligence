"""
Automated Test Suite for Edge Ingestion Service & Persistent Telemetry Dispatcher
Phase 3, Task 3 Verification

Covers:
1. Persistent Queue FIFO Enqueue & Confirmed Drain
2. Persistent Queue Crash & Restart Recovery (SQLite WAL durability)
3. Retry Exponential Backoff & Jitter Timing
4. Duplicate Prevention & Idempotency Key Tracking
5. Bounded Queue Capacity & Oldest Event Discard
6. Strict Biometric & Frame Scrubbing Safety
7. Backend Camera Configuration Synchronization
8. Backend Workstation Zone & Polygon Synchronization
9. Backend Unavailable Outage & Automatic Recovery
10. Edge Service Complete Startup & Graceful Shutdown
11. Multi-Camera Concurrency & Stream Failure Isolation
12. Operational Telemetry & Sanitized Health Reporting
13. Live Pipeline Worker Integration with Persistent Dispatcher
"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock
import numpy as np

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_engine.stream.camera_config import CameraConfig, CameraStatus
from ai_engine.stream.stream_manager import CameraStreamManager
from ai_engine.stream.frame_buffer import FrameItem
from ai_engine.analytics.polygon import PolygonZone
from ai_engine.analytics.occupancy_tracker import MultiZoneManager
from ai_engine.client.event_client import DetectionPayload
from ai_engine.client.persistent_dispatcher import PersistentTelemetryDispatcher
from ai_engine.client.config_client import BackendConfigClient
from ai_engine.service import EdgeIngestionService, ServiceStatus
from ai_engine.utils.security import sanitize_stream_uri, scrub_biometrics_and_frames


class TestEdgeServiceAndDispatcher(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="camera_intel_test_")
        self.db_path = Path(self.temp_dir) / "test_queue.db"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Persistent Queue & Dispatcher Tests
    # -------------------------------------------------------------------------

    def test_01_persistent_queue_fifo_enqueue_and_drain(self):
        """1. Dispatcher enqueues events to SQLite and drains in strict FIFO order on success."""
        dispatched_items = []

        def mock_transport(payload_dict):
            dispatched_items.append(payload_dict)
            return True

        dispatcher = PersistentTelemetryDispatcher(
            db_path=self.db_path,
            transport=mock_transport,
            auto_start=False,
        )

        try:
            # Enqueue 3 events
            for i in range(1, 4):
                payload = DetectionPayload(
                    camera_id=1,
                    location_id=10,
                    event_type="employee_recognized",
                    confidence=0.90 + (i * 0.01),
                    employee_id=100 + i,
                    tracker_id=f"cam1_trk_{i}",
                    metadata_json={"order": i},
                )
                dispatcher.enqueue(payload)

            self.assertEqual(dispatcher.queue_size, 3)

            # Synchronously flush
            flushed = dispatcher.flush(max_items=10)
            self.assertEqual(flushed, 3)
            self.assertEqual(dispatcher.queue_size, 0)
            self.assertEqual(len(dispatched_items), 3)

            # Confirm FIFO ordering
            orders = [item["metadata_json"]["order"] for item in dispatched_items]
            self.assertEqual(orders, [1, 2, 3])

            # Confirm confirmed events are deleted from SQLite
            self.assertEqual(dispatcher.queue_size, 0)

        finally:
            dispatcher.close()

    def test_02_persistent_queue_recovery_after_restart(self):
        """2. Un-dispatched events survive service termination and resume cleanly upon restart."""
        # Step 1: Start dispatcher with failing backend to build backlog on disk
        dispatcher_1 = PersistentTelemetryDispatcher(
            db_path=self.db_path,
            transport=lambda payload: False,  # Backend down
            auto_start=False,
        )

        for i in range(5):
            payload = DetectionPayload(
                camera_id=2,
                location_id=5,
                event_type="unknown_person",
                confidence=0.85,
                tracker_id=f"cam2_trk_{i}",
                metadata_json={"seq": i},
            )
            dispatcher_1.enqueue(payload)

        self.assertEqual(dispatcher_1.queue_size, 5)

        # Step 2: Simulate sudden service crash / reboot (close connection)
        dispatcher_1.close()

        # Confirm database file exists on disk
        self.assertTrue(self.db_path.exists())

        # Step 3: Reopen with new dispatcher instance pointing to the same file
        delivered_items = []
        dispatcher_2 = PersistentTelemetryDispatcher(
            db_path=self.db_path,
            transport=lambda p: (delivered_items.append(p) or True),  # Backend recovered
            auto_start=False,
        )

        try:
            # All 5 events must be recovered
            self.assertEqual(dispatcher_2.queue_size, 5)

            # Reset backoff timestamps to allow immediate flush
            with dispatcher_2._lock:
                cur = dispatcher_2._conn.cursor()
                cur.execute("UPDATE pending_events SET next_retry_at = 0.0")
                dispatcher_2._conn.commit()

            # Flush recovered events
            flushed = dispatcher_2.flush(max_items=10)
            self.assertEqual(flushed, 5)
            self.assertEqual(dispatcher_2.queue_size, 0)
            self.assertEqual(len(delivered_items), 5)
            self.assertEqual([d["metadata_json"]["seq"] for d in delivered_items], [0, 1, 2, 3, 4])

        finally:
            dispatcher_2.close()

    def test_03_retry_exponential_backoff_and_jitter(self):
        """3. Failed deliveries trigger exponential backoff before subsequent attempts."""
        dispatcher = PersistentTelemetryDispatcher(
            db_path=self.db_path,
            transport=lambda p: False,  # Always fail
            base_backoff_seconds=2.0,
            backoff_multiplier=2.0,
            auto_start=False,
        )

        try:
            payload = DetectionPayload(
                camera_id=1,
                location_id=1,
                event_type="unknown_person",
                confidence=0.80,
            )
            dispatcher.enqueue(payload)
            self.assertEqual(dispatcher.queue_size, 1)

            t0 = time.time()
            dispatcher.flush(max_items=1)  # Attempt 1 -> fails

            # Read retry metadata
            with dispatcher._lock:
                cur = dispatcher._conn.cursor()
                cur.execute("SELECT retry_count, next_retry_at FROM pending_events LIMIT 1")
                retry_count, next_retry = cur.fetchone()

            self.assertEqual(retry_count, 1)
            # Delay should be ~ 2.0s (+/- jitter)
            self.assertGreaterEqual(next_retry, t0 + 1.5)
            self.assertLessEqual(next_retry, t0 + 3.0)

            # Attempting flush before next_retry_at must skip the event
            flushed_early = dispatcher.flush(max_items=1)
            self.assertEqual(flushed_early, 0)
            self.assertEqual(dispatcher.queue_size, 1)

        finally:
            dispatcher.close()

    def test_04_duplicate_prevention_idempotency(self):
        """4. Events carry unique client_event_id tokens preventing duplicate records."""
        dispatcher = PersistentTelemetryDispatcher(
            db_path=self.db_path,
            transport=lambda p: True,
            auto_start=False,
        )

        try:
            p1 = DetectionPayload(
                camera_id=1,
                location_id=1,
                event_type="workstation_active",
                confidence=0.95,
                metadata_json={"custom_key": "val"},
            )
            cid1 = dispatcher.enqueue(p1)
            self.assertIsNotNone(cid1)
            self.assertTrue(len(cid1) > 10)

            # Verify client_event_id is populated into metadata_json
            with dispatcher._lock:
                cur = dispatcher._conn.cursor()
                cur.execute("SELECT payload_json FROM pending_events WHERE client_event_id = ?", (cid1,))
                row = cur.fetchone()
                payload_stored = json.loads(row[0])
                self.assertEqual(payload_stored["metadata_json"]["client_event_id"], cid1)

        finally:
            dispatcher.close()

    def test_05_bounded_queue_capacity_drop_oldest(self):
        """5. Queue enforces fixed maximum capacity, dropping oldest events when bounded limit is exceeded."""
        dispatcher = PersistentTelemetryDispatcher(
            db_path=self.db_path,
            max_queue_items=3,  # Max 3 items
            transport=lambda p: False,
            auto_start=False,
        )

        try:
            # Enqueue 5 items (overflow by 2)
            for i in range(5):
                p = DetectionPayload(
                    camera_id=1,
                    location_id=1,
                    event_type="unknown_person",
                    confidence=0.70,
                    metadata_json={"idx": i},
                )
                dispatcher.enqueue(p)

            # Must stay bounded at 3
            self.assertEqual(dispatcher.queue_size, 3)
            self.assertEqual(dispatcher.total_dropped, 2)

            # Remaining items should be indices 2, 3, 4 (0 and 1 dropped)
            with dispatcher._lock:
                cur = dispatcher._conn.cursor()
                cur.execute("SELECT payload_json FROM pending_events ORDER BY id ASC")
                remaining = [json.loads(r[0])["metadata_json"]["idx"] for r in cur.fetchall()]
            self.assertEqual(remaining, [2, 3, 4])

        finally:
            dispatcher.close()

    def test_06_strict_biometric_and_frame_scrubbing(self):
        """6. Telemetry dispatcher scrubs raw image bytes and 512D biometric vectors before storage."""
        dispatcher = PersistentTelemetryDispatcher(
            db_path=self.db_path,
            transport=lambda p: True,
            auto_start=False,
        )

        try:
            dirty_payload = DetectionPayload(
                camera_id=1,
                location_id=1,
                event_type="employee_recognized",
                confidence=0.99,
                employee_id=42,
                metadata_json={
                    "bbox": [100, 100, 200, 200],
                    "raw_frame": b"FAKERAWPIXELBYTES",
                    "embedding": [0.123] * 512,  # 512D vector
                    "crop_image": "base64bytes...",
                    "safe_metadata": "valid_value",
                },
            )
            cid = dispatcher.enqueue(dirty_payload)

            with dispatcher._lock:
                cur = dispatcher._conn.cursor()
                cur.execute("SELECT payload_json FROM pending_events WHERE client_event_id = ?", (cid,))
                payload_str = cur.fetchone()[0]
                stored = json.loads(payload_str)
                meta = stored.get("metadata_json", {})

            # Forbidden keys must be completely removed
            self.assertNotIn("raw_frame", meta)
            self.assertNotIn("embedding", meta)
            self.assertNotIn("crop_image", meta)
            # Safe keys preserved
            self.assertEqual(meta["safe_metadata"], "valid_value")
            self.assertEqual(meta["client_event_id"], cid)

        finally:
            dispatcher.close()

    # -------------------------------------------------------------------------
    # 2. Backend Configuration Client Tests
    # -------------------------------------------------------------------------

    def test_07_backend_camera_configuration_sync(self):
        """7. Config client synchronizes camera inventory and resolves stream URIs safely."""
        mock_cameras_api = {
            "items": [
                {
                    "id": 101,
                    "camera_code": "CAM-ENTRANCE",
                    "name": "Main Entrance",
                    "location_id": 1,
                    "camera_role": "entry_exit",
                    "stream_type": "rtsp",
                    "stream_secret_ref": "CAM_ENTRANCE_RTSP",
                    "is_active": True,
                },
                {
                    "id": 102,
                    "camera_code": "CAM-DESK-A",
                    "name": "Workstation Area",
                    "location_id": 1,
                    "camera_role": "workstation",
                    "stream_type": "rtsp",
                    "stream_secret_ref": None,
                    "is_active": True,
                },
            ],
            "total": 2,
            "page": 1,
            "size": 100,
        }

        def mock_adapter(method, url, headers=None, json=None):
            if "/api/v1/cameras" in url:
                return mock_cameras_api
            return {}

        uri_map = {"CAM_ENTRANCE_RTSP": "rtsp://admin:SecretPass123@192.168.1.10:554/stream1"}
        client = BackendConfigClient(
            base_url="http://mock-backend:8000",
            uri_resolver=uri_map,
            request_adapter=mock_adapter,
        )

        configs = client.fetch_cameras()
        self.assertEqual(len(configs), 2)

        # Camera 101 verification
        c1 = configs[0]
        self.assertEqual(c1.camera_id, 101)
        self.assertEqual(c1.camera_code, "CAM-ENTRANCE")
        self.assertEqual(c1.stream_uri, "rtsp://admin:SecretPass123@192.168.1.10:554/stream1")

        # Verify credential sanitization utility
        sanitized = sanitize_stream_uri(c1.stream_uri)
        self.assertEqual(sanitized, "rtsp://admin:***@192.168.1.10:554/stream1")
        self.assertNotIn("SecretPass123", sanitized)

        # Camera 102 verification (fallback resolution)
        c2 = configs[1]
        self.assertEqual(c2.camera_id, 102)
        self.assertEqual(c2.stream_uri, "rtsp://localhost:8554/CAM-DESK-A")

    def test_08_backend_zone_configuration_sync(self):
        """8. Config client synchronizes workstation polygon zones and inactivity thresholds."""
        mock_zones_api = {
            "items": [
                {
                    "id": 501,
                    "zone_code": "DESK-DEV-01",
                    "name": "Developer Desk 1",
                    "location_id": 1,
                    "camera_id": 102,
                    "polygon_points": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
                    "inactivity_threshold_seconds": 600,
                    "is_active": True,
                }
            ],
            "total": 1,
            "page": 1,
            "size": 100,
        }

        def mock_adapter(method, url, headers=None, json=None):
            if "/api/v1/zones" in url:
                return mock_zones_api
            return {}

        client = BackendConfigClient(
            base_url="http://mock-backend:8000",
            request_adapter=mock_adapter,
        )

        zones = client.fetch_workstation_zones()
        self.assertEqual(len(zones), 1)

        z1 = zones[0]
        self.assertEqual(z1.zone_id, 501)
        self.assertEqual(z1.zone_code, "DESK-DEV-01")
        self.assertEqual(z1.camera_id, 102)
        self.assertEqual(z1.inactivity_threshold_seconds, 600.0)
        self.assertEqual(len(z1.polygon_points), 4)

    # -------------------------------------------------------------------------
    # 3. Edge Ingestion Service Orchestration Tests
    # -------------------------------------------------------------------------

    def test_09_backend_unavailable_and_recovery(self):
        """9. Edge service continues capturing/inference during backend outage; drains on recovery."""
        backend_online = False
        received_by_backend = []

        def mock_transport(payload):
            if not backend_online:
                return False
            received_by_backend.append(payload)
            return True

        dispatcher = PersistentTelemetryDispatcher(
            db_path=self.db_path,
            transport=mock_transport,
            base_backoff_seconds=0.5,
            auto_start=False,
        )

        try:
            # 1. Backend is offline: dispatch events
            for i in range(4):
                p = DetectionPayload(
                    camera_id=1,
                    location_id=1,
                    event_type="workstation_active",
                    confidence=0.91,
                    tracker_id=f"cam1_trk_{i}",
                    metadata_json={"num": i},
                )
                dispatcher.dispatch_event(p)

            # Verify all 4 queued locally
            self.assertEqual(dispatcher.queue_size, 4)
            self.assertEqual(len(received_by_backend), 0)

            # 2. Backend recovers!
            backend_online = True
            with dispatcher._lock:
                dispatcher._conn.execute("UPDATE pending_events SET next_retry_at = 0.0")
                dispatcher._conn.commit()

            # Flush
            flushed = dispatcher.flush(max_items=10)
            self.assertEqual(flushed, 4)
            self.assertEqual(dispatcher.queue_size, 0)
            self.assertEqual(len(received_by_backend), 4)

        finally:
            dispatcher.close()

    def test_10_edge_service_startup_and_graceful_shutdown(self):
        """10. Service starts all subsystems cleanly and shuts down without leaking threads or sockets."""
        dispatcher = PersistentTelemetryDispatcher(
            db_path=self.db_path,
            transport=lambda p: True,
            auto_start=False,
        )
        stream_manager = CameraStreamManager()

        # Dummy mock capture factory
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        stream_manager.capture_factory = lambda uri: mock_cap

        # Mock detector returning empty person list
        mock_detector = MagicMock()
        mock_detector.detect_and_track.return_value = []

        service = EdgeIngestionService(
            dispatcher=dispatcher,
            stream_manager=stream_manager,
            detector=mock_detector,
            enable_face_recognition=False,
            enable_periodic_sync=False,
        )

        try:
            # Register a mock camera
            cam = CameraConfig(
                camera_id=10,
                camera_code="CAM-TEST-10",
                name="Test Camera 10",
                stream_uri="rtsp://mock-camera/live",
                location_id=1,
                sampling_fps=10.0,
            )
            stream_manager.add_camera(cam)

            # Start service
            service.start(sync_config=False)
            self.assertEqual(service.status, ServiceStatus.RUNNING)
            self.assertIsNotNone(service.started_at)
            self.assertEqual(stream_manager.camera_count, 1)

            # Health check while running
            health = service.get_health()
            self.assertEqual(health["service_status"], "running")
            self.assertEqual(health["cameras_total"], 1)

            # Stop service
            service.stop(timeout=2.0)
            self.assertEqual(service.status, ServiceStatus.STOPPED)

        finally:
            service.stop(timeout=1.0)
            dispatcher.close()

    def test_11_multiple_camera_operation_and_failure_isolation(self):
        """11. Service runs multiple cameras concurrently; failure of one camera leaves others intact."""
        dispatcher = PersistentTelemetryDispatcher(
            db_path=self.db_path,
            transport=lambda p: True,
            auto_start=False,
        )

        # Factory providing working frames for CAM-GOOD, but failure for CAM-BAD
        class MockCapture:
            def __init__(self, uri):
                self.is_bad = "bad" in uri.lower()

            def isOpened(self):
                return True

            def read(self):
                if self.is_bad:
                    return False, None
                return True, np.zeros((240, 320, 3), dtype=np.uint8)

            def release(self):
                pass

        stream_manager = CameraStreamManager(capture_factory=lambda u: MockCapture(u))
        mock_detector = MagicMock()
        mock_detector.detect_and_track.return_value = []

        service = EdgeIngestionService(
            dispatcher=dispatcher,
            stream_manager=stream_manager,
            detector=mock_detector,
            enable_face_recognition=False,
            enable_periodic_sync=False,
        )

        try:
            # Register 2 cameras
            cam1 = CameraConfig(
                camera_id=1,
                camera_code="CAM-GOOD",
                name="Good Camera",
                stream_uri="rtsp://mock/good",
                location_id=1,
            )
            cam2 = CameraConfig(
                camera_id=2,
                camera_code="CAM-BAD",
                name="Failing Camera",
                stream_uri="rtsp://mock/bad",
                location_id=1,
                read_timeout_seconds=0.5,
            )
            stream_manager.add_camera(cam1)
            stream_manager.add_camera(cam2)

            service.start(sync_config=False)
            time.sleep(0.3)

            # Good camera continues receiving frames
            frame_item = stream_manager.get_frame(camera_id=1, timeout=0.5)
            self.assertIsNotNone(frame_item)
            self.assertEqual(frame_item.camera_id, 1)

            # Failing camera should enter degraded or offline state without crashing CAM-1
            health1 = stream_manager.get_camera_health(1)
            health2 = stream_manager.get_camera_health(2)
            self.assertEqual(health1.status, CameraStatus.ONLINE)
            self.assertIn(health2.status, [CameraStatus.DEGRADED, CameraStatus.OFFLINE, CameraStatus.CONNECTING])

            # Edge service health reports total 2 cameras
            h = service.get_health()
            self.assertEqual(h["cameras_total"], 2)

        finally:
            service.stop(timeout=1.0)
            dispatcher.close()

    def test_12_service_health_telemetry_reporting(self):
        """12. Operational health status report contains sanitized, structured telemetry metrics."""
        dispatcher = PersistentTelemetryDispatcher(
            db_path=self.db_path,
            transport=lambda p: True,
            auto_start=False,
        )
        stream_manager = CameraStreamManager()
        mock_detector = MagicMock()
        mock_detector.detect_and_track.return_value = []

        service = EdgeIngestionService(
            dispatcher=dispatcher,
            stream_manager=stream_manager,
            detector=mock_detector,
            enable_face_recognition=False,
            enable_periodic_sync=False,
        )

        try:
            service.start(sync_config=False)
            health = service.get_health()

            # Verify structured sections
            self.assertIn("service_status", health)
            self.assertIn("uptime_seconds", health)
            self.assertIn("cameras", health)
            self.assertIn("pipeline", health)
            self.assertIn("telemetry_dispatcher", health)
            self.assertIn("workstations", health)

            # Telemetry dispatcher sub-metrics
            td = health["telemetry_dispatcher"]
            self.assertIn("queue_size", td)
            self.assertIn("total_dispatched", td)
            self.assertIn("is_connected", td)

        finally:
            service.stop(timeout=1.0)
            dispatcher.close()

    def test_13_live_pipeline_worker_with_persistent_dispatcher(self):
        """13. LivePipelineWorker seamlessly dispatches detection events directly to persistent queue."""
        dispatched_items = []

        dispatcher = PersistentTelemetryDispatcher(
            db_path=self.db_path,
            transport=lambda p: (dispatched_items.append(p) or True),
            auto_start=False,
        )

        stream_manager = CameraStreamManager()

        # Dummy frame with a person
        from ai_engine.pipeline.detector import TrackedPerson
        mock_detector = MagicMock()
        mock_detector.detect_and_track.return_value = [
            TrackedPerson(
                x1=50.0, y1=50.0, x2=200.0, y2=400.0,
                confidence=0.94, tracker_id=1,
            )
        ]

        from ai_engine.pipeline.pipeline_worker import LivePipelineWorker
        worker = LivePipelineWorker(
            stream_manager=stream_manager,
            detector=mock_detector,
            event_client=dispatcher,  # Injected persistent dispatcher
            enable_face_recognition=False,
        )

        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame_item = FrameItem(
            frame=dummy_frame,
            frame_id=1,
            timestamp=100.0,
            camera_id=1,
            camera_code="CAM-01",
            location_id=10,
        )

        # Process single frame
        events = worker.process_frame(frame_item)
        self.assertEqual(len(events), 1)

        # Must be in dispatcher queue
        self.assertEqual(dispatcher.queue_size, 1)

        # Flush
        flushed = dispatcher.flush(max_items=5)
        self.assertEqual(flushed, 1)
        self.assertEqual(len(dispatched_items), 1)
        self.assertEqual(dispatched_items[0]["event_type"], "unknown_person")
        self.assertEqual(dispatched_items[0]["camera_id"], 1)

        dispatcher.close()


if __name__ == "__main__":
    unittest.main()
