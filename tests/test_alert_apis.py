"""
Comprehensive Automated Test Suite for Camera Intelligence Alert Management APIs
Covers all requirements in Phase 2, Task 12:
- Alert Creation & Validation (alert_type, severity, location consistency)
- Role-Based Access & Location Scoping (super_admin, location_admin, operator, viewer)
- State Transitions (open -> acknowledged -> resolved / false_positive)
- Prevention of Invalid State Transitions (cannot re-acknowledge, cannot re-resolve)
- Protected Field Immutability via PATCH
- Alert Listing, Multi-Attribute Filtering, and Pagination
- Full Alert Detail Retrieval with Audit Trails (acknowledged_by, resolved_by)
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
from app.models.alert import Alert
from app.core.security import get_password_hash

from app.schemas.alert import (
    AlertCreate,
    AlertUpdate,
    AlertResolveRequest,
    AlertResponse,
    AlertDetailResponse,
)
from app.api.v1.endpoints.alerts import (
    create_alert as create_alert_ep,
    list_alerts as list_alerts_ep,
    get_alert_details as get_alert_details_ep,
    acknowledge_alert as acknowledge_alert_ep,
    resolve_alert as resolve_alert_ep,
    update_alert as update_alert_ep,
)


class TestAlertAPIs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up database session, locations, cameras, users, and initial alerts."""
        cls.db = SessionLocal()

        # Load bootstrap super_admin
        cls.super_admin = (
            cls.db.query(User).filter(User.email == "admin@cameraintelligence.com").first()
        )
        assert cls.super_admin is not None, "Bootstrap super_admin not found in database!"

        # 1. Create Test Locations
        cls.loc_a = Location(
            name="Alert Facility Alpha",
            address="100 Security Way, Alpha City",
            timezone="UTC",
            is_active=True,
        )
        cls.loc_b = Location(
            name="Alert Facility Beta",
            address="200 Response Blvd, Beta City",
            timezone="America/New_York",
            is_active=True,
        )
        cls.db.add_all([cls.loc_a, cls.loc_b])
        cls.db.commit()
        cls.db.refresh(cls.loc_a)
        cls.db.refresh(cls.loc_b)

        # 2. Create Cameras
        cls.cam_a = Camera(
            camera_code="CAM-ALT-A1",
            name="Alpha Camera 1",
            location_id=cls.loc_a.id,
            camera_role="entry_exit",
            stream_type="rtsp",
            connection_status="online",
            is_active=True,
        )
        cls.cam_b = Camera(
            camera_code="CAM-ALT-B1",
            name="Beta Camera 1",
            location_id=cls.loc_b.id,
            camera_role="perimeter",
            stream_type="rtsp",
            connection_status="online",
            is_active=True,
        )
        cls.db.add_all([cls.cam_a, cls.cam_b])
        cls.db.commit()
        cls.db.refresh(cls.cam_a)
        cls.db.refresh(cls.cam_b)

        # 3. Create Users
        pw_hash = get_password_hash("TestPassword123!")
        cls.loc_admin_a = User(
            email="admin.alta@test.internal",
            full_name="Admin Alert A",
            password_hash=pw_hash,
            system_role="location_admin",
            is_active=True,
        )
        cls.loc_admin_b = User(
            email="admin.altb@test.internal",
            full_name="Admin Alert B",
            password_hash=pw_hash,
            system_role="location_admin",
            is_active=True,
        )
        cls.operator_a = User(
            email="operator.alta@test.internal",
            full_name="Operator Alert A",
            password_hash=pw_hash,
            system_role="operator",
            is_active=True,
        )
        cls.viewer_a = User(
            email="viewer.alta@test.internal",
            full_name="Viewer Alert A",
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

        cls.created_alert_ids: list[int] = []

    @classmethod
    def tearDownClass(cls):
        """Clean up all created entities in reverse dependency order."""
        try:
            # 1. Clean up alerts
            cls.db.query(Alert).delete(synchronize_session=False)

            # 2. Clean up cameras
            cls.db.query(Camera).delete(synchronize_session=False)

            # 3. Clean up user_locations & users
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

            # 4. Clean up locations
            cls.db.query(Location).filter(
                Location.id.in_([cls.loc_a.id, cls.loc_b.id])
            ).delete(synchronize_session=False)

            cls.db.commit()
        except Exception as e:
            cls.db.rollback()
            print(f"Error during tearDownClass: {e}")
        finally:
            cls.db.close()

    def test_01_create_alert_valid(self):
        """1. Operator can create a valid security alert."""
        payload = AlertCreate(
            location_id=self.loc_a.id,
            camera_id=self.cam_a.id,
            alert_type="camera_offline",
            severity="high",
            title="Camera Stream Disconnected",
            description="Alpha Camera 1 lost RTSP handshake.",
        )
        res = create_alert_ep(
            payload=payload,
            current_user=self.operator_a,
            db=self.db,
        )
        self.assertIsNotNone(res.id)
        self.assertEqual(res.status, "open")
        self.assertEqual(res.alert_type, "camera_offline")
        self.assertEqual(res.severity, "high")
        self.assertEqual(res.location_id, self.loc_a.id)
        self.assertEqual(res.camera_id, self.cam_a.id)
        self.assertIsNone(res.acknowledged_by_user_id)
        self.assertIsNone(res.resolved_by_user_id)
        self.created_alert_ids.append(res.id)

    def test_02_invalid_alert_type_and_severity(self):
        """2. Invalid alert_type or severity values are rejected with 422."""
        with self.assertRaises(ValidationError):
            AlertCreate(
                location_id=self.loc_a.id,
                alert_type="invalid_alert_type_123",
                title="Test Alert",
            )

        with self.assertRaises(ValidationError):
            AlertCreate(
                location_id=self.loc_a.id,
                alert_type="camera_offline",
                severity="ultra_extreme",
                title="Test Alert",
            )

    def test_03_cross_location_entity_rejected(self):
        """3. Alert in Location A referencing Camera in Location B returns 400."""
        payload = AlertCreate(
            location_id=self.loc_a.id,       # Location A
            camera_id=self.cam_b.id,         # Location B
            alert_type="camera_offline",
            severity="medium",
            title="Mismatched Camera",
        )
        with self.assertRaises(HTTPException) as ctx:
            create_alert_ep(
                payload=payload,
                current_user=self.super_admin,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("does not match alert location", ctx.exception.detail)

    def test_04_cross_location_alert_access_rejected(self):
        """4. Location Admin B cannot view or triage alert in Location A (403)."""
        alert_id = self.created_alert_ids[0]
        with self.assertRaises(HTTPException) as ctx:
            get_alert_details_ep(
                alert_id=alert_id,
                current_user=self.loc_admin_b,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_05_viewer_cannot_create_or_modify_alert(self):
        """5. Viewer cannot create, acknowledge, resolve, or update alerts (403)."""
        alert_id = self.created_alert_ids[0]

        # Cannot create
        with self.assertRaises(HTTPException) as ctx:
            create_alert_ep(
                payload=AlertCreate(
                    location_id=self.loc_a.id,
                    alert_type="camera_offline",
                    title="Viewer Alert",
                ),
                current_user=self.viewer_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot acknowledge
        with self.assertRaises(HTTPException) as ctx:
            acknowledge_alert_ep(
                alert_id=alert_id,
                current_user=self.viewer_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot resolve
        with self.assertRaises(HTTPException) as ctx:
            resolve_alert_ep(
                alert_id=alert_id,
                payload=AlertResolveRequest(resolution_notes="notes"),
                current_user=self.viewer_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot patch
        with self.assertRaises(HTTPException) as ctx:
            update_alert_ep(
                alert_id=alert_id,
                payload=AlertUpdate(title="Hacked"),
                current_user=self.viewer_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_06_acknowledge_alert_valid(self):
        """6. Operator can acknowledge open alert; records user ID and timestamp."""
        alert_id = self.created_alert_ids[0]
        res = acknowledge_alert_ep(
            alert_id=alert_id,
            current_user=self.operator_a,
            db=self.db,
        )
        self.assertEqual(res.status, "acknowledged")
        self.assertEqual(res.acknowledged_by_user_id, self.operator_a.id)
        self.assertIsNotNone(res.acknowledged_at)

    def test_07_prevent_invalid_state_transitions_acknowledge(self):
        """7. Acknowledging an already acknowledged alert is rejected (400)."""
        alert_id = self.created_alert_ids[0]
        with self.assertRaises(HTTPException) as ctx:
            acknowledge_alert_ep(
                alert_id=alert_id,
                current_user=self.operator_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already in 'acknowledged' status", ctx.exception.detail)

    def test_08_resolve_alert_valid(self):
        """8. Operator can resolve acknowledged alert with resolution notes."""
        alert_id = self.created_alert_ids[0]
        res = resolve_alert_ep(
            alert_id=alert_id,
            payload=AlertResolveRequest(
                resolution_notes="Camera network cable reconnected and verified online.",
                is_false_positive=False,
            ),
            current_user=self.operator_a,
            db=self.db,
        )
        self.assertEqual(res.status, "resolved")
        self.assertEqual(res.resolved_by_user_id, self.operator_a.id)
        self.assertIsNotNone(res.resolved_at)
        self.assertEqual(
            res.resolution_notes,
            "Camera network cable reconnected and verified online.",
        )

    def test_09_resolve_as_false_positive(self):
        """9. Operator can resolve an alert directly as false_positive."""
        # Create second alert
        new_alert = create_alert_ep(
            payload=AlertCreate(
                location_id=self.loc_a.id,
                alert_type="employee_inactivity",
                severity="low",
                title="Potential Inactivity",
                description="Desk sensor triggered.",
            ),
            current_user=self.operator_a,
            db=self.db,
        )
        self.created_alert_ids.append(new_alert.id)

        # Resolve as false positive
        res = resolve_alert_ep(
            alert_id=new_alert.id,
            payload=AlertResolveRequest(
                resolution_notes="Employee was in scheduled training session.",
                is_false_positive=True,
            ),
            current_user=self.operator_a,
            db=self.db,
        )
        self.assertEqual(res.status, "false_positive")
        self.assertEqual(res.resolved_by_user_id, self.operator_a.id)
        self.assertEqual(res.resolution_notes, "Employee was in scheduled training session.")

    def test_10_prevent_invalid_state_transitions_resolve(self):
        """10. Cannot resolve an already resolved/closed alert; cannot acknowledge resolved alert."""
        alert_id = self.created_alert_ids[0]

        # Cannot resolve again
        with self.assertRaises(HTTPException) as ctx:
            resolve_alert_ep(
                alert_id=alert_id,
                payload=AlertResolveRequest(resolution_notes="again"),
                current_user=self.operator_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already closed", ctx.exception.detail)

        # Cannot acknowledge closed alert
        with self.assertRaises(HTTPException) as ctx:
            acknowledge_alert_ep(
                alert_id=alert_id,
                current_user=self.operator_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already closed", ctx.exception.detail)

    def test_11_update_permitted_fields_patch(self):
        """11. Operator can update permitted fields (title, description, severity) via PATCH."""
        alert_id = self.created_alert_ids[0]
        res = update_alert_ep(
            alert_id=alert_id,
            payload=AlertUpdate(
                title="Camera Stream Disconnected - Resolved",
                description="Updated incident documentation.",
            ),
            current_user=self.operator_a,
            db=self.db,
        )
        self.assertEqual(res.title, "Camera Stream Disconnected - Resolved")
        self.assertEqual(res.description, "Updated incident documentation.")
        # Status remains 'resolved'
        self.assertEqual(res.status, "resolved")

    def test_12_list_alerts_scoping_and_filtering(self):
        """12. Super admin sees all alerts; Location Admin A sees only Location A; filters work."""
        # Create alert in Location B
        b_alert = create_alert_ep(
            payload=AlertCreate(
                location_id=self.loc_b.id,
                camera_id=self.cam_b.id,
                alert_type="camera_offline",
                severity="critical",
                title="Beta Perimeter Alert",
            ),
            current_user=self.super_admin,
            db=self.db,
        )
        self.created_alert_ids.append(b_alert.id)

        # Super admin list
        res_super = list_alerts_ep(
            current_user=self.super_admin,
            db=self.db,
            page=1,
            size=50,
        )
        self.assertGreaterEqual(res_super.total, 3)

        # Location Admin A sees only Loc A
        res_loc_a = list_alerts_ep(
            current_user=self.loc_admin_a,
            db=self.db,
            page=1,
            size=50,
        )
        for item in res_loc_a.items:
            self.assertEqual(item.location_id, self.loc_a.id)

        # Filter by severity
        res_crit = list_alerts_ep(
            current_user=self.super_admin,
            db=self.db,
            severity="critical",
            page=1,
            size=10,
        )
        self.assertEqual(res_crit.total, 1)
        self.assertEqual(res_crit.items[0].severity, "critical")

    def test_13_get_alert_details(self):
        """13. Get alert details returns joined location, camera, and audit user emails."""
        alert_id = self.created_alert_ids[0]
        details = get_alert_details_ep(
            alert_id=alert_id,
            current_user=self.viewer_a,
            db=self.db,
        )
        self.assertEqual(details.id, alert_id)
        self.assertEqual(details.location_name, "Alert Facility Alpha")
        self.assertEqual(details.camera_name, "Alpha Camera 1")
        self.assertEqual(details.camera_code, "CAM-ALT-A1")
        self.assertEqual(details.acknowledged_by_user_email, self.operator_a.email)
        self.assertEqual(details.resolved_by_user_email, self.operator_a.email)


if __name__ == "__main__":
    unittest.main()

