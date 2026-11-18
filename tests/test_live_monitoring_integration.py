"""
Test Suite: Live Monitoring & CCTV Command Center Integration (Phase 6C)
Verifies:
- Authenticated MJPEG streaming and snapshot endpoints
- Location RBAC isolation for live streams
- Detection event telemetry and bounding box payload formats
- Workstation polygon coordinates retrieval for camera overlays
- Camera heartbeat telemetry and connection status transitions
"""

import math
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
import pytest

SERVER_ROOT = Path(__file__).resolve().parents[1] / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.session import SessionLocal
from app.models.user import User, user_locations
from app.models.location import Location
from app.models.camera import Camera
from app.models.workstation_zone import WorkstationZone
from app.models.detection_event import DetectionEvent
from app.core.security import create_access_token, get_password_hash
from app.core.permissions import SystemRole


class TestLiveMonitoringIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db: Session = SessionLocal()

        # Clean up any leftover test data
        cls.db.query(DetectionEvent).delete()
        cls.db.query(WorkstationZone).delete()
        cls.db.query(Camera).delete()
        cls.db.execute(user_locations.delete())
        cls.db.query(User).filter(User.email.like("test_live_%")).delete()
        cls.db.query(Location).filter(Location.name.like("Live Loc %")).delete()
        cls.db.commit()

        # 1. Setup Location A (Authorized) and Location B (Restricted)
        cls.loc_a = Location(name="Live Loc Alpha", timezone="UTC", is_active=True)
        cls.loc_b = Location(name="Live Loc Beta", timezone="UTC", is_active=True)
        cls.db.add_all([cls.loc_a, cls.loc_b])
        cls.db.commit()
        cls.db.refresh(cls.loc_a)
        cls.db.refresh(cls.loc_b)

        # 2. Setup Users: Super Admin & Location-Restricted Viewer
        cls.super_admin = User(
            email="test_live_admin@ci.com",
            password_hash=get_password_hash("AdminPass123!"),
            full_name="Live Super Admin",
            system_role=SystemRole.SUPER_ADMIN.value,
            is_active=True,
        )
        cls.viewer_a = User(
            email="test_live_viewer_a@ci.com",
            password_hash=get_password_hash("ViewerPass123!"),
            full_name="Viewer Loc A Only",
            system_role=SystemRole.VIEWER.value,
            is_active=True,
        )
        cls.db.add_all([cls.super_admin, cls.viewer_a])
        cls.db.commit()
        cls.db.refresh(cls.super_admin)
        cls.db.refresh(cls.viewer_a)

        # Assign viewer_a only to loc_a
        cls.db.execute(
            user_locations.insert().values(
                user_id=cls.viewer_a.id, location_id=cls.loc_a.id
            )
        )
        cls.db.commit()

        # Generate JWT Bearer tokens
        cls.admin_token, _, _ = create_access_token(
            subject=str(cls.super_admin.id),
            extra_claims={"role": cls.super_admin.system_role},
        )
        cls.viewer_token, _, _ = create_access_token(
            subject=str(cls.viewer_a.id),
            extra_claims={"role": cls.viewer_a.system_role},
        )

        # 3. Setup Cameras in Loc A and Loc B
        cls.cam_a = Camera(
            name="Main Entrance Gate",
            camera_code="CAM-LIVE-01",
            location_id=cls.loc_a.id,
            camera_role="entry_exit",
            stream_type="rtsp",
            connection_status="online",
            last_heartbeat_at=datetime.now(timezone.utc),
            is_active=True,
        )
        cls.cam_b = Camera(
            name="Restricted Vault Beta",
            camera_code="CAM-LIVE-02",
            location_id=cls.loc_b.id,
            camera_role="perimeter",
            stream_type="rtsp",
            connection_status="offline",
            last_heartbeat_at=None,
            is_active=True,
        )
        cls.cam_inactive = Camera(
            name="Decommissioned Hallway",
            camera_code="CAM-LIVE-03",
            location_id=cls.loc_a.id,
            camera_role="general",
            stream_type="rtsp",
            connection_status="unknown",
            is_active=False,
        )
        cls.db.add_all([cls.cam_a, cls.cam_b, cls.cam_inactive])
        cls.db.commit()
        cls.db.refresh(cls.cam_a)
        cls.db.refresh(cls.cam_b)
        cls.db.refresh(cls.cam_inactive)

        # 4. Setup Workstation Zone with Normalized Polygon Points for Cam A
        cls.zone = WorkstationZone(
            name="Reception Desk 1",
            zone_code="ZONE-REC-01",
            location_id=cls.loc_a.id,
            camera_id=cls.cam_a.id,
            polygon_points=[[0.2, 0.3], [0.8, 0.3], [0.85, 0.75], [0.15, 0.75]],
            inactivity_threshold_seconds=120,
            is_active=True,
        )
        cls.db.add(cls.zone)
        cls.db.commit()
        cls.db.refresh(cls.zone)

    @classmethod
    def tearDownClass(cls):
        cls.db.query(DetectionEvent).delete()
        cls.db.query(WorkstationZone).delete()
        cls.db.query(Camera).delete()
        cls.db.execute(user_locations.delete())
        cls.db.query(User).filter(User.email.like("test_live_%")).delete()
        cls.db.query(Location).filter(Location.name.like("Live Loc %")).delete()
        cls.db.commit()
        cls.db.close()

    def test_01_unauthenticated_stream_rejected(self):
        """Unauthenticated requests to live stream endpoint must be rejected."""
        resp = self.client.get(f"/api/v1/cameras/{self.cam_a.id}/stream")
        self.assertIn(resp.status_code, (401, 403))

    def test_02_location_rbac_isolation_enforced(self):
        """Viewer authorized only for Loc A cannot access Cam B (Loc B)."""
        headers = {"Authorization": f"Bearer {self.viewer_token}"}
        resp = self.client.get(
            f"/api/v1/cameras/{self.cam_b.id}/stream", headers=headers
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Access denied", resp.json()["detail"])

    def test_03_deactivated_camera_stream_rejected(self):
        """Deactivated camera must reject stream request with 400 Bad Request."""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        resp = self.client.get(
            f"/api/v1/cameras/{self.cam_inactive.id}/stream", headers=headers
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("deactivated", resp.json()["detail"].lower())

    def test_04_nonexistent_camera_returns_404(self):
        """Non-existent camera ID returns 404 Not Found."""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        resp = self.client.get("/api/v1/cameras/999999/stream", headers=headers)
        self.assertEqual(resp.status_code, 404)

    def test_05_camera_snapshot_rbac_and_offline_handling(self):
        """Snapshot endpoint enforces location RBAC and returns 503 if edge is offline."""
        headers_viewer = {"Authorization": f"Bearer {self.viewer_token}"}
        # Cam B is forbidden for viewer
        resp_b = self.client.get(
            f"/api/v1/cameras/{self.cam_b.id}/snapshot", headers=headers_viewer
        )
        self.assertEqual(resp_b.status_code, 403)

        # Cam A is authorized; if edge server loopback isn't running in this unit test, returns 503
        resp_a = self.client.get(
            f"/api/v1/cameras/{self.cam_a.id}/snapshot", headers=headers_viewer
        )
        self.assertIn(resp_a.status_code, (200, 503))

    def test_06_camera_zones_endpoint_returns_normalized_polygon(self):
        """GET /api/v1/cameras/{id}/zones returns associated workstation zones with polygon points."""
        headers = {"Authorization": f"Bearer {self.viewer_token}"}
        resp = self.client.get(
            f"/api/v1/cameras/{self.cam_a.id}/zones", headers=headers
        )
        self.assertEqual(resp.status_code, 200)
        zones = resp.json()
        self.assertIsInstance(zones, list)
        self.assertGreaterEqual(len(zones), 1)
        self.assertEqual(zones[0]["zone_code"], "ZONE-REC-01")

        # Query zone detail to verify polygon coordinates
        resp_zone = self.client.get(
            f"/api/v1/zones/{self.zone.id}", headers=headers
        )
        self.assertEqual(resp_zone.status_code, 200)
        zone_data = resp_zone.json()
        points = zone_data["polygon_points"]
        self.assertEqual(len(points), 4)
        for pt in points:
            self.assertGreaterEqual(pt[0], 0.0)
            self.assertLessEqual(pt[0], 1.0)
            self.assertGreaterEqual(pt[1], 0.0)
            self.assertLessEqual(pt[1], 1.0)

    def test_07_detection_event_ingestion_and_telemetry_filtering(self):
        """Ingest detection event with bounding box and verify listing filter by camera."""
        headers = {"Authorization": f"Bearer {self.admin_token}"}

        event_payload = {
            "camera_id": self.cam_a.id,
            "location_id": self.loc_a.id,
            "event_type": "employee_recognized",
            "confidence": 0.942,
            "tracker_id": "TRK-0012",
            "workstation_zone_id": self.zone.id,
            "metadata_json": {
                "bbox": [150.0, 200.0, 450.0, 800.0],
                "detector_conf": 0.9512,
                "face_conf": 0.9821,
                "face_sim": 0.8710,
            },
        }

        # Ingest
        resp_create = self.client.post(
            "/api/v1/events", json=event_payload, headers=headers
        )
        self.assertEqual(resp_create.status_code, 201)
        created = resp_create.json()
        self.assertEqual(created["camera_id"], self.cam_a.id)
        self.assertEqual(created["event_type"], "employee_recognized")
        self.assertEqual(created["tracker_id"], "TRK-0012")
        self.assertIsNotNone(created["metadata_json"])
        self.assertEqual(len(created["metadata_json"]["bbox"]), 4)

        # Query via viewer token
        headers_viewer = {"Authorization": f"Bearer {self.viewer_token}"}
        resp_list = self.client.get(
            f"/api/v1/events?camera_id={self.cam_a.id}&size=10",
            headers=headers_viewer,
        )
        self.assertEqual(resp_list.status_code, 200)
        items = resp_list.json()["items"]
        self.assertGreaterEqual(len(items), 1)
        self.assertEqual(items[0]["camera_id"], self.cam_a.id)
        self.assertEqual(items[0]["tracker_id"], "TRK-0012")

    def test_08_camera_heartbeat_telemetry_update(self):
        """POST /api/v1/cameras/{id}/heartbeat updates connection_status and heartbeat timestamp."""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        heartbeat_payload = {
            "connection_status": "online",
            "fps": 15.0,
            "dropped_frames": 0,
            "error_message": None,
        }
        resp = self.client.post(
            f"/api/v1/cameras/{self.cam_a.id}/heartbeat",
            json=heartbeat_payload,
            headers=headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["connection_status"], "online")
        self.assertIsNotNone(data["last_heartbeat_at"])


if __name__ == "__main__":
    unittest.main()
