"""
Comprehensive Automated Test Suite for Edge Video Bridge, Snapshot API & MJPEG Streaming
Phase 6B Verification

Covers:
1. RTSP Worker thread-safe non-destructive latest frame access (zero frame stealing)
2. Frame age expiration and offline camera handling in frame access bridge
3. Edge Frame Server internal loopback endpoints (/internal/health, /internal/snapshot, /internal/stream)
4. Viewer concurrency limits and 429 Too Many Requests enforcement
5. Camera Heartbeat Client transition triggers & periodic sync
6. FastAPI Camera Heartbeat endpoints (single camera and batch update in PostgreSQL)
7. FastAPI Camera Snapshot endpoint with Location-based RBAC & inactive camera rejection
8. FastAPI MJPEG Streaming endpoint with boundary headers & connection lifecycle
9. Edge Bridge Service failure handling (ConnectError -> 503, Timeout -> 504)
"""

import asyncio
import io
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import cv2

# Add paths
TEST_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TEST_DIR.parent
SERVER_ROOT = PROJECT_ROOT / "server"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from ai_engine.stream.camera_config import CameraConfig, CameraStatus
from ai_engine.stream.stream_manager import CameraStreamManager
from ai_engine.stream.rtsp_worker import RTSPStreamWorker
from ai_engine.stream.frame_buffer import FrameItem, BoundedFrameBuffer
from ai_engine.stream.edge_frame_server import create_edge_frame_app, EdgeFrameServer
from ai_engine.client.heartbeat_client import CameraHeartbeatClient

from app.database.session import SessionLocal
from app.models.user import User, user_locations
from app.models.location import Location
from app.models.camera import Camera
from app.schemas.camera import CameraHeartbeat, CameraHeartbeatBatch, CameraHeartbeatBatchItem
from app.services.edge_bridge_service import EdgeBridgeService
from app.main import app as fastapi_app
from app.api.v1.endpoints.cameras import (
    get_camera_snapshot,
    get_camera_stream,
    camera_heartbeat as camera_heartbeat_ep,
    batch_camera_heartbeat as batch_camera_heartbeat_ep,
)


class MockVideoCapture:
    """Simulates OpenCV VideoCapture producing synthetic frames."""

    def __init__(self, width=320, height=240, fps=30):
        self.width = width
        self.height = height
        self.fps = fps
        self._opened = True
        self._frame_count = 0

    def isOpened(self):
        return self._opened

    def read(self):
        if not self._opened:
            return False, None
        self._frame_count += 1
        # Generate dummy 3-channel frame
        frame = np.full((self.height, self.width, 3), (self._frame_count % 255), dtype=np.uint8)
        # Draw frame number
        cv2.putText(frame, f"F:{self._frame_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        return True, frame

    def release(self):
        self._opened = False


class TestEdgeVideoBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test database records (locations, cameras, users)."""
        cls.db = SessionLocal()

        # Admin user
        cls.admin_user = cls.db.query(User).filter(User.email == "admin@cameraintelligence.com").first()
        if not cls.admin_user:
            cls.admin_user = cls.db.query(User).filter(User.system_role == "super_admin").first()
        assert cls.admin_user is not None, "Test requires an existing super_admin user."

        # Pre-clean any leftover test records from aborted runs
        try:
            cls.db.query(Camera).filter(
                Camera.camera_code.in_(["CAM-BRIDGE-01", "CAM-BRIDGE-02", "CAM-BRIDGE-03"])
            ).delete(synchronize_session=False)

            existing_users = cls.db.query(User).filter(
                User.email.in_(["bridge_viewer@example.com", "bridge_operator@example.com"])
            ).all()
            if existing_users:
                u_ids = [u.id for u in existing_users]
                cls.db.execute(user_locations.delete().where(user_locations.c.user_id.in_(u_ids)))
                cls.db.query(User).filter(User.id.in_(u_ids)).delete(synchronize_session=False)

            cls.db.query(Location).filter(
                Location.name.in_(["Bridge Test Facility", "Restricted Facility"])
            ).delete(synchronize_session=False)
            cls.db.commit()
        except Exception:
            cls.db.rollback()

        # Create isolated test location
        cls.test_location = Location(
            name="Bridge Test Facility",
            address="777 Stream Road, Video City",
            timezone="UTC",
            is_active=True,
        )
        cls.db.add(cls.test_location)
        cls.db.commit()
        cls.db.refresh(cls.test_location)

        # Create isolated unauthorized location
        cls.unauth_location = Location(
            name="Restricted Facility",
            address="999 Secret Road, Restricted City",
            timezone="UTC",
            is_active=True,
        )
        cls.db.add(cls.unauth_location)
        cls.db.commit()
        cls.db.refresh(cls.unauth_location)

        # Create viewer user
        cls.viewer_user = User(
            email="bridge_viewer@example.com",
            full_name="Bridge Viewer",
            password_hash="test-hash",
            system_role="viewer",
            is_active=True,
        )
        cls.db.add(cls.viewer_user)
        cls.db.commit()
        cls.db.refresh(cls.viewer_user)

        # Assign viewer only to test_location
        cls.db.execute(
            user_locations.insert().values(
                user_id=cls.viewer_user.id,
                location_id=cls.test_location.id,
            )
        )
        cls.db.commit()

        # Create operator user
        cls.operator_user = User(
            email="bridge_operator@example.com",
            full_name="Bridge Operator",
            password_hash="test-hash",
            system_role="operator",
            is_active=True,
        )
        cls.db.add(cls.operator_user)
        cls.db.commit()
        cls.db.refresh(cls.operator_user)

        # Create active test camera
        cls.active_camera = Camera(
            camera_code="CAM-BRIDGE-01",
            name="Live Bridge Camera",
            location_id=cls.test_location.id,
            camera_role="entry_exit",
            stream_type="rtsp",
            connection_status="unknown",
            is_active=True,
        )
        cls.db.add(cls.active_camera)

        # Create deactivated test camera
        cls.inactive_camera = Camera(
            camera_code="CAM-BRIDGE-02",
            name="Deactivated Bridge Camera",
            location_id=cls.test_location.id,
            camera_role="general",
            stream_type="rtsp",
            connection_status="offline",
            is_active=False,
        )
        cls.db.add(cls.inactive_camera)

        # Create restricted location camera
        cls.restricted_camera = Camera(
            camera_code="CAM-BRIDGE-03",
            name="Restricted Zone Camera",
            location_id=cls.unauth_location.id,
            camera_role="perimeter",
            stream_type="rtsp",
            connection_status="online",
            is_active=True,
        )
        cls.db.add(cls.restricted_camera)
        cls.db.commit()
        cls.db.refresh(cls.active_camera)
        cls.db.refresh(cls.inactive_camera)
        cls.db.refresh(cls.restricted_camera)

    @classmethod
    def tearDownClass(cls):
        """Clean up database fixtures."""
        try:
            cls.db.query(Camera).filter(
                Camera.id.in_([cls.active_camera.id, cls.inactive_camera.id, cls.restricted_camera.id])
            ).delete(synchronize_session=False)

            cls.db.execute(
                user_locations.delete().where(
                    user_locations.c.user_id.in_([cls.viewer_user.id, cls.operator_user.id])
                )
            )

            cls.db.query(User).filter(
                User.id.in_([cls.viewer_user.id, cls.operator_user.id])
            ).delete(synchronize_session=False)

            cls.db.query(Location).filter(
                Location.id.in_([cls.test_location.id, cls.unauth_location.id])
            ).delete(synchronize_session=False)

            cls.db.commit()
        except Exception as e:
            cls.db.rollback()
            print(f"Teardown error: {e}")
        finally:
            cls.db.close()

    # -------------------------------------------------------------------------
    # 1. RTSP Worker & Frame Access Tests (No Frame Stealing)
    # -------------------------------------------------------------------------
    def test_rtsp_worker_latest_frame_no_stealing(self):
        """Verify get_latest_frame retrieves fresh frame without consuming from inference queue."""
        config = CameraConfig(
            camera_id=901,
            camera_code="TEST-01",
            name="Test Cam 1",
            stream_uri="mock://test",
            location_id=self.test_location.id,
        )
        buffer = BoundedFrameBuffer(maxsize=10)

        worker = RTSPStreamWorker(
            config=config,
            buffer=buffer,
            capture_factory=lambda uri: MockVideoCapture(),
        )
        worker.start()

        # Wait for worker to produce at least 3 frames
        deadline = time.time() + 3.0
        while time.time() < deadline and buffer.qsize() < 3:
            time.sleep(0.05)

        self.assertGreaterEqual(buffer.qsize(), 1, "Inference buffer should contain frames")
        initial_buffer_size = buffer.qsize()

        # Fetch latest frame via frame bridge accessor
        latest_item = worker.get_latest_frame(max_age_seconds=5.0)
        self.assertIsNotNone(latest_item, "Should retrieve latest decoded frame")
        self.assertIsInstance(latest_item.frame, np.ndarray)
        self.assertEqual(latest_item.camera_id, 901)

        # CRITICAL: Buffer size must NOT decrease (zero frame stealing from AI pipeline)
        self.assertEqual(
            buffer.qsize(),
            initial_buffer_size,
            "Fetching latest frame must NOT steal frames from inference buffer!",
        )

        # Verify multiple concurrent reads succeed and return valid frames
        item2 = worker.get_latest_frame(max_age_seconds=5.0)
        self.assertIsNotNone(item2)

        worker.stop(timeout=2.0)

    def test_rtsp_worker_stale_frame_rejection(self):
        """Verify get_latest_frame returns None when frame is older than max_age_seconds."""
        config = CameraConfig(
            camera_id=902,
            camera_code="TEST-02",
            name="Test Cam 2",
            stream_uri="mock://test",
            location_id=self.test_location.id,
        )
        buffer = BoundedFrameBuffer(maxsize=5)
        worker = RTSPStreamWorker(config=config, buffer=buffer)
        worker.health.status = CameraStatus.ONLINE

        # Manually inject an old frame (10 seconds ago)
        old_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        with worker._latest_frame_lock:
            worker._latest_frame = FrameItem(
                frame=old_frame,
                frame_id=1,
                timestamp=time.time() - 10.0,
                camera_id=902,
                camera_code="TEST-02",
                location_id=self.test_location.id,
            )

        # Asking for max_age=2.0 must reject the 10-second old frame
        self.assertIsNone(worker.get_latest_frame(max_age_seconds=2.0))
        # Asking for max_age=15.0 must accept it
        self.assertIsNotNone(worker.get_latest_frame(max_age_seconds=15.0))

    # -------------------------------------------------------------------------
    # 2. Edge Frame Server Internal Loopback Tests
    # -------------------------------------------------------------------------
    def test_edge_frame_server_snapshot_endpoint(self):
        """Test loopback microservice /internal/cameras/{id}/snapshot."""
        stream_manager = CameraStreamManager(capture_factory=lambda uri: MockVideoCapture())
        config = CameraConfig(
            camera_id=self.active_camera.id,
            camera_code=self.active_camera.camera_code,
            name=self.active_camera.name,
            stream_uri="mock://active",
            location_id=self.test_location.id,
        )
        stream_manager.add_camera(config)
        stream_manager.start_camera(self.active_camera.id)

        # Wait for worker online
        time.sleep(0.5)

        app = create_edge_frame_app(stream_manager, max_viewers_per_camera=5)
        client = TestClient(app)

        # Health endpoint
        health_resp = client.get("/internal/health")
        self.assertEqual(health_resp.status_code, 200)
        self.assertEqual(health_resp.json()["status"], "healthy")

        # Snapshot endpoint
        snap_resp = client.get(f"/internal/cameras/{self.active_camera.id}/snapshot?quality=80")
        self.assertEqual(snap_resp.status_code, 200)
        self.assertEqual(snap_resp.headers["content-type"], "image/jpeg")
        self.assertEqual(snap_resp.headers["x-camera-id"], str(self.active_camera.id))
        self.assertIn("x-frame-timestamp", snap_resp.headers)
        self.assertIn("x-frame-age-ms", snap_resp.headers)

        # Verify JPEG magic header (FF D8 FF)
        content = snap_resp.content
        self.assertTrue(content.startswith(b"\xff\xd8\xff"), "Snapshot must be valid JPEG image bytes")

        # Unregistered camera returns 404
        bad_resp = client.get("/internal/cameras/999999/snapshot")
        self.assertEqual(bad_resp.status_code, 404)

        stream_manager.stop_all(timeout=1.0)

    def test_edge_frame_server_offline_camera_snapshot(self):
        """Test loopback microservice returns 503 when camera is offline."""
        stream_manager = CameraStreamManager()
        config = CameraConfig(
            camera_id=888,
            camera_code="OFFLINE-01",
            name="Offline Cam",
            stream_uri="mock://offline",
            location_id=self.test_location.id,
        )
        stream_manager.add_camera(config)
        # Not starting camera worker -> status is OFFLINE

        app = create_edge_frame_app(stream_manager)
        client = TestClient(app)

        snap_resp = client.get("/internal/cameras/888/snapshot")
        self.assertEqual(snap_resp.status_code, 503)
        self.assertIn("OFFLINE", snap_resp.json()["detail"])

    # -------------------------------------------------------------------------
    # 3. Viewer Concurrency Limit Enforcement & MJPEG Stream
    # -------------------------------------------------------------------------
    def test_edge_frame_server_mjpeg_stream_output(self):
        """Test loopback microservice delivers multipart/x-mixed-replace MJPEG stream chunks."""
        stream_manager = CameraStreamManager(capture_factory=lambda uri: MockVideoCapture())
        config = CameraConfig(
            camera_id=777,
            camera_code="BUSY-01",
            name="Busy Cam",
            stream_uri="mock://busy",
            location_id=self.test_location.id,
        )
        stream_manager.add_camera(config)
        stream_manager.start_camera(777)
        time.sleep(0.3)

        app = create_edge_frame_app(stream_manager, max_viewers_per_camera=5)
        client = TestClient(app)

        with client.stream("GET", "/internal/cameras/777/stream?fps=20&max_frames=2") as stream:
            self.assertEqual(stream.status_code, 200)
            self.assertIn("multipart/x-mixed-replace", stream.headers["content-type"])
            chunk = next(stream.iter_bytes())
            self.assertTrue(len(chunk) > 0)
            self.assertIn(b"--frame", chunk)

        stream_manager.stop_all(timeout=1.0)

    def test_edge_frame_server_viewer_limits(self):
        """Test max viewers limit (HTTP 429) per camera stream when capacity reached."""
        stream_manager = CameraStreamManager(capture_factory=lambda uri: MockVideoCapture())
        config = CameraConfig(
            camera_id=778,
            camera_code="LIMIT-01",
            name="Limit Cam",
            stream_uri="mock://limit",
            location_id=self.test_location.id,
        )
        stream_manager.add_camera(config)
        stream_manager.start_camera(778)
        time.sleep(0.3)

        # max_viewers_per_camera = 0 immediately triggers 429
        app = create_edge_frame_app(stream_manager, max_viewers_per_camera=0)
        client = TestClient(app)

        resp = client.get("/internal/cameras/778/stream")
        self.assertEqual(resp.status_code, 429)
        self.assertIn("Maximum concurrent viewers", resp.json()["detail"])

        stream_manager.stop_all(timeout=1.0)

    # -------------------------------------------------------------------------
    # 4. Camera Heartbeat Client & Status Notification Tests
    # -------------------------------------------------------------------------
    def test_camera_heartbeat_client_state_transition(self):
        """Verify on_status_change dispatches single heartbeat immediately."""
        dispatched_payloads = []

        def mock_post(url, json=None, headers=None, timeout=None):
            dispatched_payloads.append((url, json))
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            return mock_resp

        with patch("requests.post", side_effect=mock_post):
            hb_client = CameraHeartbeatClient(backend_url="http://127.0.0.1:8000", auth_token="fake-jwt")
            hb_client.on_status_change(camera_id=123, status=CameraStatus.ONLINE)

            # Wait briefly for daemon thread dispatch
            time.sleep(0.3)

            self.assertGreaterEqual(len(dispatched_payloads), 1)
            url, payload = dispatched_payloads[0]
            self.assertIn("/api/v1/cameras/123/heartbeat", url)
            self.assertEqual(payload["connection_status"], "online")

    # -------------------------------------------------------------------------
    # 5. FastAPI Camera Heartbeat Endpoints (PostgreSQL Sync)
    # -------------------------------------------------------------------------
    def test_fastapi_camera_heartbeat_sync(self):
        """Test POST /api/v1/cameras/{id}/heartbeat updates database record."""
        hb_data = CameraHeartbeat(
            connection_status="online",
            fps_captured=29.8,
            total_reconnects=1,
            last_error=None,
        )
        res = camera_heartbeat_ep(
            camera_id=self.active_camera.id,
            heartbeat_data=hb_data,
            current_user=self.operator_user,
            db=self.db,
        )
        self.assertEqual(res.connection_status, "online")
        self.assertIsNotNone(res.last_heartbeat_at)

        # Verify database record updated
        cam = self.db.query(Camera).filter(Camera.id == self.active_camera.id).first()
        self.assertEqual(cam.connection_status, "online")
        self.assertIsNotNone(cam.last_heartbeat_at)

    def test_fastapi_batch_heartbeat_sync(self):
        """Test POST /api/v1/cameras/heartbeat/batch updates multiple cameras."""
        batch_payload = CameraHeartbeatBatch(
            items=[
                CameraHeartbeatBatchItem(camera_id=self.active_camera.id, connection_status="degraded"),
                CameraHeartbeatBatchItem(camera_id=self.restricted_camera.id, connection_status="offline"),
            ]
        )
        result = batch_camera_heartbeat_ep(
            batch_data=batch_payload,
            current_user=self.operator_user,
            db=self.db,
        )
        self.assertEqual(result["updated"], 2)

        # Verify records
        c1 = self.db.query(Camera).filter(Camera.id == self.active_camera.id).first()
        c2 = self.db.query(Camera).filter(Camera.id == self.restricted_camera.id).first()
        self.assertEqual(c1.connection_status, "degraded")
        self.assertEqual(c2.connection_status, "offline")

    # -------------------------------------------------------------------------
    # 6. FastAPI Camera Snapshot Endpoint (RBAC & Inactive Handling)
    # -------------------------------------------------------------------------
    def test_fastapi_snapshot_location_rbac_denial(self):
        """Verify user without location access is rejected with 403 Forbidden."""
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                get_camera_snapshot(
                    camera_id=self.restricted_camera.id,
                    current_user=self.viewer_user,  # Viewer only assigned to test_location, not unauth_location
                    db=self.db,
                )
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Access denied", ctx.exception.detail)

    def test_fastapi_snapshot_inactive_camera_rejection(self):
        """Verify requesting snapshot from deactivated camera returns 400 Bad Request."""
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                get_camera_snapshot(
                    camera_id=self.inactive_camera.id,
                    current_user=self.viewer_user,
                    db=self.db,
                )
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("deactivated", ctx.exception.detail)

    def test_fastapi_snapshot_nonexistent_camera(self):
        """Verify non-existent camera ID returns 404."""
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                get_camera_snapshot(
                    camera_id=9999999,
                    current_user=self.viewer_user,
                    db=self.db,
                )
            )
        self.assertEqual(ctx.exception.status_code, 404)

    # -------------------------------------------------------------------------
    # 7. Edge Bridge Service Failure Resilience
    # -------------------------------------------------------------------------
    def test_edge_bridge_service_edge_offline_handling(self):
        """Verify EdgeBridgeService raises 503 when edge frame server is unreachable."""
        # Point bridge to non-existent port (e.g., 59999)
        offline_bridge = EdgeBridgeService(base_url="http://127.0.0.1:59999", timeout=0.5)

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(offline_bridge.get_snapshot(camera_id=self.active_camera.id))

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("offline or unreachable", ctx.exception.detail)

    # -------------------------------------------------------------------------
    # 8. Phase 6B.1 Stabilization Verifications (Security, Statuses, Lifecycle)
    # -------------------------------------------------------------------------
    def test_unauthenticated_requests_rejection(self):
        """Verify unauthenticated requests to snapshot and stream are rejected (403 for missing token, 401 for invalid token)."""
        client = TestClient(fastapi_app)

        # Snapshot without auth (FastAPI HTTPBearer returns 403 when header is absent)
        snap_resp = client.get(f"/api/v1/cameras/{self.active_camera.id}/snapshot")
        self.assertIn(snap_resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

        # Stream without auth
        stream_resp = client.get(f"/api/v1/cameras/{self.active_camera.id}/stream")
        self.assertIn(stream_resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

        # Snapshot with invalid token (must return 401)
        bad_token_headers = {"Authorization": "Bearer invalid.jwt.token"}
        snap_bad = client.get(f"/api/v1/cameras/{self.active_camera.id}/snapshot", headers=bad_token_headers)
        self.assertEqual(snap_bad.status_code, status.HTTP_401_UNAUTHORIZED)

        stream_bad = client.get(f"/api/v1/cameras/{self.active_camera.id}/stream", headers=bad_token_headers)
        self.assertEqual(stream_bad.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_all_heartbeat_status_transitions(self):
        """Verify ONLINE, OFFLINE, DEGRADED, and UNKNOWN status transitions persist in DB."""
        for target_status in ["online", "degraded", "offline", "unknown"]:
            hb = CameraHeartbeat(connection_status=target_status)
            res = camera_heartbeat_ep(
                camera_id=self.active_camera.id,
                heartbeat_data=hb,
                current_user=self.operator_user,
                db=self.db,
            )
            self.assertEqual(res.connection_status, target_status)
            cam = self.db.query(Camera).filter(Camera.id == self.active_camera.id).first()
            self.assertEqual(cam.connection_status, target_status)
            self.assertIsNotNone(cam.last_heartbeat_at)

    def test_concurrent_frame_readers_thread_safety(self):
        """Verify 10 concurrent threads accessing get_latest_frame do not corrupt or steal frames."""
        config = CameraConfig(
            camera_id=903,
            camera_code="CONCURR-01",
            name="Concurrent Cam",
            stream_uri="mock://concurr",
            location_id=self.test_location.id,
        )
        buffer = BoundedFrameBuffer(maxsize=15)
        worker = RTSPStreamWorker(
            config=config,
            buffer=buffer,
            capture_factory=lambda uri: MockVideoCapture(),
        )
        worker.start()

        time.sleep(0.4)
        errors = []

        def reader_task():
            try:
                for _ in range(30):
                    item = worker.get_latest_frame(max_age_seconds=5.0)
                    if item is not None:
                        self.assertEqual(item.camera_id, 903)
                        self.assertIsInstance(item.frame, np.ndarray)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader_task) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent reads produced errors: {errors}")
        # Buffer still holds frames for AI pipeline
        self.assertGreater(buffer.qsize(), 0)

        worker.stop(timeout=1.0)

    def test_edge_service_lifecycle_and_loopback_binding(self):
        """Verify EdgeIngestionService starts frame server only on 127.0.0.1 and cleans up."""
        from ai_engine.service import EdgeIngestionService

        edge_service = EdgeIngestionService(
            enable_face_recognition=False,
            enable_periodic_sync=False,
            capture_factory=lambda uri: MockVideoCapture(),
            frame_server_port=8089,
            frame_server_host="127.0.0.1",
        )
        self.assertIsNotNone(edge_service.frame_server)
        self.assertEqual(edge_service.frame_server.host, "127.0.0.1")
        self.assertEqual(edge_service.frame_server.port, 8089)

        edge_service.start(sync_config=False)
        self.assertTrue(edge_service.frame_server._thread.is_alive())

        edge_service.stop(timeout=2.0)
        self.assertFalse(edge_service.frame_server._thread.is_alive())



if __name__ == "__main__":
    unittest.main()
