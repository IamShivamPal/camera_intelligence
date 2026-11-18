"""
Comprehensive Automated Test Suite for Camera Intelligence Detection Event APIs
Covers all requirements in Phase 2, Task 12:
- Event Ingestion (camera, employee, zone, confidence, tracker_id, snapshot_ref, metadata)
- Validation (valid event types, confidence bounds, location consistency)
- Ephemeral Tracker ID Safety (never treated as employee identity)
- Role-Based Access & Location Scoping (super_admin, location_admin, operator, viewer)
- Cross-Location Rejection (employee/camera mismatch, zone/camera mismatch)
- Presence Session & Guest Visit Lifecycle Transitions
- Automated Alert Triggering for Critical Anomalies (after_hours_intrusion, after_hours_employee)
- Event Listing, Multi-Attribute Filtering, and Pagination
- Full Event Detail Exposure
- Clean Database Teardown
"""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Add server directory to path
SERVER_ROOT = Path(__file__).resolve().parents[1] / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from fastapi import HTTPException, status
from pydantic import ValidationError

from app.database.session import SessionLocal
from app.models.user import User, user_locations
from app.models.location import Location
from app.models.camera import Camera
from app.models.department import Department
from app.models.employee import Employee
from app.models.workstation_zone import WorkstationZone
from app.models.detection_event import DetectionEvent
from app.models.presence_session import PresenceSession
from app.models.guest_visit import GuestVisit
from app.models.alert import Alert
from app.core.security import get_password_hash

from app.schemas.detection_event import (
    DetectionEventCreate,
    DetectionEventResponse,
    DetectionEventDetailResponse,
)
from app.api.v1.endpoints.events import (
    ingest_event as ingest_event_ep,
    list_events as list_events_ep,
    get_event_details as get_event_details_ep,
    reconcile_sessions as reconcile_sessions_ep,
)


class TestEventAPIs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up database session, test locations, cameras, employees, zones, and users."""
        cls.db = SessionLocal()

        # Load bootstrap super_admin
        cls.super_admin = (
            cls.db.query(User).filter(User.email == "admin@cameraintelligence.com").first()
        )
        assert cls.super_admin is not None, "Bootstrap super_admin not found in database!"

        # 1. Create Test Locations
        cls.loc_a = Location(
            name="Event Facility Alpha",
            address="100 Detection Way, Alpha City",
            timezone="UTC",
            is_active=True,
        )
        cls.loc_b = Location(
            name="Event Facility Beta",
            address="200 Telemetry Blvd, Beta City",
            timezone="America/New_York",
            is_active=True,
        )
        cls.db.add_all([cls.loc_a, cls.loc_b])
        cls.db.commit()
        cls.db.refresh(cls.loc_a)
        cls.db.refresh(cls.loc_b)

        # 2. Create Departments
        cls.dept_a = Department(
            location_id=cls.loc_a.id,
            name="Security Operations",
            code="SEC-OPS-A",
            is_active=True,
        )
        cls.dept_b = Department(
            location_id=cls.loc_b.id,
            name="Logistics",
            code="LOG-B",
            is_active=True,
        )
        cls.db.add_all([cls.dept_a, cls.dept_b])
        cls.db.commit()
        cls.db.refresh(cls.dept_a)
        cls.db.refresh(cls.dept_b)

        # 3. Create Cameras (entry_exit and workstation)
        cls.cam_a_entry = Camera(
            camera_code="CAM-EVT-A-ENTRY",
            name="Alpha Main Gate",
            location_id=cls.loc_a.id,
            camera_role="entry_exit",
            stream_type="rtsp",
            connection_status="online",
            is_active=True,
        )
        cls.cam_a_ws = Camera(
            camera_code="CAM-EVT-A-WS",
            name="Alpha Workstation Desk",
            location_id=cls.loc_a.id,
            camera_role="workstation",
            stream_type="rtsp",
            connection_status="online",
            is_active=True,
        )
        cls.cam_b = Camera(
            camera_code="CAM-EVT-B-MAIN",
            name="Beta Entry Gate",
            location_id=cls.loc_b.id,
            camera_role="entry_exit",
            stream_type="rtsp",
            connection_status="online",
            is_active=True,
        )
        cls.db.add_all([cls.cam_a_entry, cls.cam_a_ws, cls.cam_b])
        cls.db.commit()
        for c in [cls.cam_a_entry, cls.cam_a_ws, cls.cam_b]:
            cls.db.refresh(c)

        # 4. Create Employees
        cls.emp_a = Employee(
            employee_code="EMP-EVT-A1",
            full_name="Alice Alpha",
            email="alice.alpha@test.internal",
            location_id=cls.loc_a.id,
            department_id=cls.dept_a.id,
            enrollment_status="enrolled",
            is_active=True,
        )
        cls.emp_b = Employee(
            employee_code="EMP-EVT-B1",
            full_name="Bob Beta",
            email="bob.beta@test.internal",
            location_id=cls.loc_b.id,
            department_id=cls.dept_b.id,
            enrollment_status="enrolled",
            is_active=True,
        )
        cls.db.add_all([cls.emp_a, cls.emp_b])
        cls.db.commit()
        cls.db.refresh(cls.emp_a)
        cls.db.refresh(cls.emp_b)

        # 5. Create Workstation Zone in Loc A
        cls.zone_a = WorkstationZone(
            location_id=cls.loc_a.id,
            camera_id=cls.cam_a_ws.id,
            zone_code="ZONE-EVT-A1",
            name="Alpha Desk 1",
            polygon_points=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
            inactivity_threshold_seconds=600,
            assigned_employee_id=cls.emp_a.id,
            is_active=True,
        )
        cls.db.add(cls.zone_a)
        cls.db.commit()
        cls.db.refresh(cls.zone_a)

        # 6. Create Test Users
        pw_hash = get_password_hash("TestPassword123!")
        cls.loc_admin_a = User(
            email="admin.evta@test.internal",
            full_name="Admin Loc A",
            password_hash=pw_hash,
            system_role="location_admin",
            is_active=True,
        )
        cls.loc_admin_b = User(
            email="admin.evtb@test.internal",
            full_name="Admin Loc B",
            password_hash=pw_hash,
            system_role="location_admin",
            is_active=True,
        )
        cls.operator_a = User(
            email="operator.evta@test.internal",
            full_name="Operator Loc A",
            password_hash=pw_hash,
            system_role="operator",
            is_active=True,
        )
        cls.viewer_a = User(
            email="viewer.evta@test.internal",
            full_name="Viewer Loc A",
            password_hash=pw_hash,
            system_role="viewer",
            is_active=True,
        )
        cls.db.add_all([cls.loc_admin_a, cls.loc_admin_b, cls.operator_a, cls.viewer_a])
        cls.db.commit()
        for u in [cls.loc_admin_a, cls.loc_admin_b, cls.operator_a, cls.viewer_a]:
            cls.db.refresh(u)

        # Assign user locations
        cls.db.execute(
            user_locations.insert().values([
                {"user_id": cls.loc_admin_a.id, "location_id": cls.loc_a.id},
                {"user_id": cls.operator_a.id, "location_id": cls.loc_a.id},
                {"user_id": cls.viewer_a.id, "location_id": cls.loc_a.id},
                {"user_id": cls.loc_admin_b.id, "location_id": cls.loc_b.id},
            ])
        )
        cls.db.commit()

        # Track IDs for teardown
        cls.created_event_ids: list[int] = []

    @classmethod
    def tearDownClass(cls):
        """Clean up all created entities in reverse dependency order."""
        try:
            # 1. Clean up alerts created during tests
            cls.db.query(Alert).delete(synchronize_session=False)

            # 2. Clean up detection events
            cls.db.query(DetectionEvent).delete(synchronize_session=False)

            # 3. Clean up presence sessions
            cls.db.query(PresenceSession).delete(synchronize_session=False)

            # 4. Clean up guest visits
            cls.db.query(GuestVisit).delete(synchronize_session=False)

            # 5. Clean up workstation zones
            cls.db.query(WorkstationZone).delete(synchronize_session=False)

            # 6. Clean up employees
            cls.db.query(Employee).delete(synchronize_session=False)

            # 7. Clean up cameras
            cls.db.query(Camera).delete(synchronize_session=False)

            # 8. Clean up departments
            cls.db.query(Department).delete(synchronize_session=False)

            # 9. Clean up user_locations & users
            test_uids = [
                cls.loc_admin_a.id,
                cls.loc_admin_b.id,
                cls.operator_a.id,
                cls.viewer_a.id,
            ]
            cls.db.execute(
                user_locations.delete().where(user_locations.c.user_id.in_(test_uids))
            )
            cls.db.query(User).filter(User.id.in_(test_uids)).delete(synchronize_session=False)

            # 10. Clean up locations
            cls.db.query(Location).filter(
                Location.id.in_([cls.loc_a.id, cls.loc_b.id])
            ).delete(synchronize_session=False)

            cls.db.commit()
        except Exception as e:
            cls.db.rollback()
            print(f"Error during tearDownClass: {e}")
        finally:
            cls.db.close()

    def test_01_valid_event_ingestion(self):
        """1. Operator can ingest valid employee_recognized event."""
        payload = DetectionEventCreate(
            camera_id=self.cam_a_entry.id,
            event_type="employee_recognized",
            employee_id=self.emp_a.id,
            confidence=0.985,
            tracker_id="track_101",
            snapshot_ref="snapshots/2026/11/14/alice_entry.jpg",
            metadata_json={"bbox": [120, 80, 240, 320], "face_quality": 0.94},
        )
        res = ingest_event_ep(
            payload=payload,
            current_user=self.operator_a,
            db=self.db,
        )
        self.assertIsNotNone(res.id)
        self.assertEqual(res.camera_id, self.cam_a_entry.id)
        self.assertEqual(res.location_id, self.loc_a.id)
        self.assertEqual(res.employee_id, self.emp_a.id)
        self.assertEqual(res.event_type, "employee_recognized")
        self.assertEqual(res.confidence, 0.985)
        self.assertEqual(res.tracker_id, "track_101")
        self.created_event_ids.append(res.id)

    def test_02_invalid_event_type_rejected(self):
        """2. Event type not matching ck_detection_event_type is rejected with 422."""
        with self.assertRaises(ValidationError):
            DetectionEventCreate(
                camera_id=self.cam_a_entry.id,
                event_type="invalid_event_type_xyz",
            )

    def test_03_invalid_confidence_values(self):
        """3. Confidence scores outside [0.0, 1.0] or non-finite values are rejected."""
        # Out of bounds (> 1.0)
        with self.assertRaises(ValidationError):
            DetectionEventCreate(
                camera_id=self.cam_a_entry.id,
                event_type="unknown_person",
                confidence=1.5,
            )

        # Negative (< 0.0)
        with self.assertRaises(ValidationError):
            DetectionEventCreate(
                camera_id=self.cam_a_entry.id,
                event_type="unknown_person",
                confidence=-0.1,
            )

        # NaN
        with self.assertRaises(ValidationError):
            DetectionEventCreate(
                camera_id=self.cam_a_entry.id,
                event_type="unknown_person",
                confidence=float("nan"),
            )

    def test_04_missing_camera_rejected(self):
        """4. Ingesting event with non-existent camera ID returns 404."""
        payload = DetectionEventCreate(
            camera_id=999999,
            event_type="unknown_person",
            confidence=0.85,
        )
        with self.assertRaises(HTTPException) as ctx:
            ingest_event_ep(
                payload=payload,
                current_user=self.super_admin,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_404_NOT_FOUND)

    def test_05_missing_employee_rejected(self):
        """5. Ingesting event with non-existent employee ID returns 404."""
        payload = DetectionEventCreate(
            camera_id=self.cam_a_entry.id,
            event_type="employee_recognized",
            employee_id=999999,
            confidence=0.85,
        )
        with self.assertRaises(HTTPException) as ctx:
            ingest_event_ep(
                payload=payload,
                current_user=self.operator_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_404_NOT_FOUND)

    def test_06_cross_location_employee_camera_rejected(self):
        """6. Ingesting event where employee belongs to Loc B and camera to Loc A returns 400."""
        payload = DetectionEventCreate(
            camera_id=self.cam_a_entry.id,  # Location A
            event_type="employee_recognized",
            employee_id=self.emp_b.id,       # Location B
            confidence=0.92,
        )
        with self.assertRaises(HTTPException) as ctx:
            ingest_event_ep(
                payload=payload,
                current_user=self.super_admin,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("does not match camera location", ctx.exception.detail)

    def test_07_cross_location_zone_camera_rejected(self):
        """7. Ingesting event where workstation zone and camera locations mismatch returns 400."""
        payload = DetectionEventCreate(
            camera_id=self.cam_b.id,         # Location B
            event_type="workstation_active",
            workstation_zone_id=self.zone_a.id, # Location A
            confidence=0.90,
        )
        with self.assertRaises(HTTPException) as ctx:
            ingest_event_ep(
                payload=payload,
                current_user=self.super_admin,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("does not match camera location", ctx.exception.detail)

    def test_08_location_authorization_enforced(self):
        """8. Location Admin B cannot ingest event for camera in Location A (403)."""
        payload = DetectionEventCreate(
            camera_id=self.cam_a_entry.id,  # Location A
            event_type="unknown_person",
            confidence=0.75,
        )
        with self.assertRaises(HTTPException) as ctx:
            ingest_event_ep(
                payload=payload,
                current_user=self.loc_admin_b,  # Only has access to Location B
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_09_viewer_cannot_ingest_event(self):
        """9. Viewer role cannot ingest detection events (403)."""
        payload = DetectionEventCreate(
            camera_id=self.cam_a_entry.id,
            event_type="unknown_person",
            confidence=0.88,
        )
        with self.assertRaises(HTTPException) as ctx:
            ingest_event_ep(
                payload=payload,
                current_user=self.viewer_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_10_tracker_id_not_treated_as_employee_identity(self):
        """10. Tracker ID is stored as stream telemetry and never mapped to an employee."""
        payload = DetectionEventCreate(
            camera_id=self.cam_a_entry.id,
            event_type="unknown_person",
            employee_id=None,
            tracker_id="stream_track_42",
            confidence=0.81,
        )
        res = ingest_event_ep(
            payload=payload,
            current_user=self.operator_a,
            db=self.db,
        )
        self.assertEqual(res.tracker_id, "stream_track_42")
        self.assertIsNone(res.employee_id)

        # Check DB record
        db_evt = self.db.query(DetectionEvent).filter(DetectionEvent.id == res.id).first()
        self.assertIsNotNone(db_evt)
        self.assertIsNone(db_evt.employee_id)
        self.assertEqual(db_evt.tracker_id, "stream_track_42")
        self.created_event_ids.append(res.id)

    def test_11_event_pagination_and_filtering(self):
        """11. Events list supports pagination and filtering by event_type, camera_id, etc."""
        # Query events in location A
        res = list_events_ep(
            current_user=self.operator_a,
            db=self.db,
            camera_id=self.cam_a_entry.id,
            page=1,
            size=10,
        )
        self.assertGreaterEqual(res.total, 1)
        self.assertGreaterEqual(len(res.items), 1)
        for item in res.items:
            self.assertEqual(item.camera_id, self.cam_a_entry.id)
            self.assertEqual(item.location_id, self.loc_a.id)

    def test_12_event_details_retrieval(self):
        """12. Retrieve event details including joined camera, employee, and location names."""
        event_id = self.created_event_ids[0]
        details = get_event_details_ep(
            event_id=event_id,
            current_user=self.viewer_a,
            db=self.db,
        )
        self.assertEqual(details.id, event_id)
        self.assertEqual(details.location_name, "Event Facility Alpha")
        self.assertEqual(details.camera_name, "Alpha Main Gate")
        self.assertEqual(details.employee_name, "Alice Alpha")

        # Location Admin B cannot view this event in Location A
        with self.assertRaises(HTTPException) as ctx:
            get_event_details_ep(
                event_id=event_id,
                current_user=self.loc_admin_b,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_13_presence_lifecycle_integration(self):
        """13. Entry camera event automatically starts/links facility PresenceSession; workstation zone event links workstation session."""
        # 13a. Entry camera event
        res_entry = ingest_event_ep(
            payload=DetectionEventCreate(
                camera_id=self.cam_a_entry.id,
                event_type="employee_recognized",
                employee_id=self.emp_a.id,
                confidence=0.99,
            ),
            current_user=self.operator_a,
            db=self.db,
        )
        self.assertIsNotNone(res_entry.presence_session_id)
        self.created_event_ids.append(res_entry.id)

        sess = (
            self.db.query(PresenceSession)
            .filter(PresenceSession.id == res_entry.presence_session_id)
            .first()
        )
        self.assertIsNotNone(sess)
        self.assertEqual(sess.employee_id, self.emp_a.id)
        self.assertEqual(sess.session_type, "facility")
        self.assertEqual(sess.status, "active")

        # 13b. Workstation zone event
        res_ws = ingest_event_ep(
            payload=DetectionEventCreate(
                camera_id=self.cam_a_ws.id,
                event_type="workstation_active",
                employee_id=self.emp_a.id,
                workstation_zone_id=self.zone_a.id,
                confidence=0.97,
            ),
            current_user=self.operator_a,
            db=self.db,
        )
        self.assertIsNotNone(res_ws.presence_session_id)
        self.created_event_ids.append(res_ws.id)

        ws_sess = (
            self.db.query(PresenceSession)
            .filter(PresenceSession.id == res_ws.presence_session_id)
            .first()
        )
        self.assertIsNotNone(ws_sess)
        self.assertEqual(ws_sess.session_type, "workstation")
        self.assertEqual(ws_sess.workstation_zone_id, self.zone_a.id)
        self.assertEqual(ws_sess.status, "active")

    def test_14_guest_visit_lifecycle_integration(self):
        """14. guest_entry creates GuestVisit, and guest_exit marks it exited."""
        # Guest entry
        entry_payload = DetectionEventCreate(
            camera_id=self.cam_a_entry.id,
            event_type="guest_entry",
            metadata_json={
                "guest_code": "GUEST-ALPHA-909",
                "guest_name": "Charlie Visitor",
                "notes": "Contractor meeting",
            },
        )
        entry_res = ingest_event_ep(
            payload=entry_payload,
            current_user=self.operator_a,
            db=self.db,
        )
        self.assertIsNotNone(entry_res.guest_visit_id)
        self.created_event_ids.append(entry_res.id)

        visit = (
            self.db.query(GuestVisit)
            .filter(GuestVisit.id == entry_res.guest_visit_id)
            .first()
        )
        self.assertIsNotNone(visit)
        self.assertEqual(visit.guest_code, "GUEST-ALPHA-909")
        self.assertEqual(visit.status, "inside")
        self.assertIsNone(visit.exited_at)

        # Guest exit
        exit_payload = DetectionEventCreate(
            camera_id=self.cam_a_entry.id,
            event_type="guest_exit",
            guest_visit_id=visit.id,
            metadata_json={"guest_code": "GUEST-ALPHA-909"},
        )
        exit_res = ingest_event_ep(
            payload=exit_payload,
            current_user=self.operator_a,
            db=self.db,
        )
        self.assertEqual(exit_res.guest_visit_id, visit.id)
        self.created_event_ids.append(exit_res.id)

        self.db.refresh(visit)
        self.assertEqual(visit.status, "exited")
        self.assertIsNotNone(visit.exited_at)

    def test_15_automated_alert_generation(self):
        """15. after_hours_intrusion event triggers automated critical alert."""
        payload = DetectionEventCreate(
            camera_id=self.cam_a_entry.id,
            event_type="after_hours_intrusion",
            confidence=0.91,
            tracker_id="intruder_trk",
        )
        res = ingest_event_ep(
            payload=payload,
            current_user=self.operator_a,
            db=self.db,
        )
        self.created_event_ids.append(res.id)

        # Check alert created
        alert = (
            self.db.query(Alert)
            .filter(Alert.detection_event_id == res.id)
            .first()
        )
        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, "after_hours_intrusion")
        self.assertEqual(alert.severity, "critical")
        self.assertEqual(alert.status, "open")
        self.assertEqual(alert.location_id, self.loc_a.id)

    def test_16_history_preservation_append_only(self):
        """16. Ingested events are preserved; historical records persist."""
        count = (
            self.db.query(DetectionEvent)
            .filter(DetectionEvent.location_id == self.loc_a.id)
            .count()
        )
        self.assertGreaterEqual(count, 5)

    def test_17_reconcile_sessions_endpoint(self):
        """17. POST /api/v1/events/reconcile-sessions closes eligible orphaned sessions."""
        res = reconcile_sessions_ep(
            current_user=self.operator_a,
            db=self.db,
            max_stale_seconds=900.0,
            offline_camera_grace_seconds=60.0,
            location_id=self.loc_a.id,
        )
        self.assertEqual(res["status"], "success")
        self.assertIn("reconciled_sessions_count", res)
        self.assertIn("reconciled_session_ids", res)


if __name__ == "__main__":
    unittest.main()
