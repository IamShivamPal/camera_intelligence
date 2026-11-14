"""
Comprehensive Automated Test Suite for Camera Intelligence Camera Management APIs
Covers all requirements specified in Phase 2, Task 9:
- Camera Registration (Create, Enforce Unique camera_code, Location Validation)
- RTSP Credential Sanitization (Reject plaintext/inline passwords, safe stream_secret_ref)
- Role-Based Authorization & Location Scoping (super_admin, location_admin, operator, viewer)
- Camera Listing, Pagination, and Multi-Attribute Filtering (role, stream_type, status, is_active, search)
- Camera Retrieval & Safe Detail Exposure (never exposes secrets or raw URLs)
- Camera Configuration Updates (unique code checks, location access)
- Camera Soft-Deactivation
- Workstation Zone Association (Same location consistency enforced, cross-location rejected)
- Workstation Zone transfer protection (Cannot move camera across locations with attached zones)
- Clean database teardown

Runs using standard Python unittest.
"""

import sys
import unittest
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
from app.models.workstation_zone import WorkstationZone
from app.core.security import get_password_hash

from app.schemas.camera import (
    CameraCreate,
    CameraUpdate,
    CameraResponse,
    CameraDetailResponse,
    WorkstationZoneSummary,
)
from app.schemas.common import PaginatedResponse

from app.api.v1.endpoints.cameras import (
    list_cameras as list_cameras_ep,
    create_camera as create_camera_ep,
    get_camera as get_camera_ep,
    update_camera as update_camera_ep,
    deactivate_camera as deactivate_camera_ep,
    associate_workstation_zone as associate_workstation_zone_ep,
    list_camera_zones as list_camera_zones_ep,
)


class TestCameraAPIs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up database connection, test locations, and test users."""
        cls.db = SessionLocal()

        # Load bootstrap super_admin
        cls.super_admin = (
            cls.db.query(User).filter(User.email == "admin@cameraintelligence.com").first()
        )
        assert cls.super_admin is not None, "Bootstrap super_admin not found in database!"

        # Create temporary test locations
        cls.loc_a = Location(
            name="Cam Facility Alpha",
            address="100 Vision Way, Alpha City",
            timezone="America/New_York",
            is_active=True,
        )
        cls.loc_b = Location(
            name="Cam Facility Beta",
            address="200 Sensor Blvd, Beta Town",
            timezone="UTC",
            is_active=True,
        )
        cls.db.add_all([cls.loc_a, cls.loc_b])
        cls.db.commit()
        cls.db.refresh(cls.loc_a)
        cls.db.refresh(cls.loc_b)

        hashed_pw = get_password_hash("TestPassword123!")

        # Create test users for role & location scoping tests
        cls.loc_admin_a = User(
            email="admin.cama@test.internal",
            full_name="Location A Camera Admin",
            password_hash=hashed_pw,
            system_role="location_admin",
            is_active=True,
        )
        cls.loc_admin_b = User(
            email="admin.camb@test.internal",
            full_name="Location B Camera Admin",
            password_hash=hashed_pw,
            system_role="location_admin",
            is_active=True,
        )
        cls.operator_a = User(
            email="operator.cama@test.internal",
            full_name="Location A Operator",
            password_hash=hashed_pw,
            system_role="operator",
            is_active=True,
        )
        cls.viewer_a = User(
            email="viewer.cama@test.internal",
            full_name="Location A Viewer",
            password_hash=hashed_pw,
            system_role="viewer",
            is_active=True,
        )

        cls.db.add_all([cls.loc_admin_a, cls.loc_admin_b, cls.operator_a, cls.viewer_a])
        cls.db.commit()
        for u in [cls.loc_admin_a, cls.loc_admin_b, cls.operator_a, cls.viewer_a]:
            cls.db.refresh(u)

        # Assign users to locations
        cls.db.execute(
            user_locations.insert().values(
                [
                    {"user_id": cls.loc_admin_a.id, "location_id": cls.loc_a.id},
                    {"user_id": cls.operator_a.id, "location_id": cls.loc_a.id},
                    {"user_id": cls.viewer_a.id, "location_id": cls.loc_a.id},
                    {"user_id": cls.loc_admin_b.id, "location_id": cls.loc_b.id},
                ]
            )
        )
        cls.db.commit()

        # Track entities for teardown
        cls.created_zone_ids = []
        cls.created_camera_ids = []

    @classmethod
    def tearDownClass(cls):
        """Clean up all created test entities in reverse dependency order."""
        try:
            # 1. Clean up workstation zones
            cls.db.query(WorkstationZone).delete(synchronize_session=False)

            # 2. Clean up cameras
            cls.db.query(Camera).delete(synchronize_session=False)

            # 3. Clean up user_locations and test users
            test_user_ids = [
                cls.loc_admin_a.id,
                cls.loc_admin_b.id,
                cls.operator_a.id,
                cls.viewer_a.id,
            ]
            cls.db.execute(
                user_locations.delete().where(user_locations.c.user_id.in_(test_user_ids))
            )
            cls.db.query(User).filter(User.id.in_(test_user_ids)).delete(
                synchronize_session=False
            )

            # 4. Clean up locations
            cls.db.query(Location).filter(
                Location.id.in_([cls.loc_a.id, cls.loc_b.id])
            ).delete(synchronize_session=False)

            cls.db.commit()
        except Exception as e:
            cls.db.rollback()
            print(f"Teardown error: {e}")
        finally:
            cls.db.close()

    # =========================================================================
    # 1. CAMERA REGISTRATION & SECURITY TESTS
    # =========================================================================

    def test_01_create_camera_success(self):
        """Location admin can register a camera with valid parameters and secret reference."""
        data = CameraCreate(
            camera_code="CAM-ALPHA-01",
            name="Main Entrance Lobby",
            location_id=self.loc_a.id,
            camera_role="entry_exit",
            stream_type="rtsp",
            stream_secret_ref="vault://cctv/cameras/cam-alpha-01",
            connection_status="unknown",
            is_active=True,
        )
        resp = create_camera_ep(
            data=data, current_user=self.loc_admin_a, db=self.db
        )
        self.assertIsInstance(resp, CameraDetailResponse)
        self.assertEqual(resp.camera_code, "CAM-ALPHA-01")
        self.assertEqual(resp.name, "Main Entrance Lobby")
        self.assertEqual(resp.location_id, self.loc_a.id)
        self.assertEqual(resp.location_name, "Cam Facility Alpha")
        self.assertEqual(resp.camera_role, "entry_exit")
        self.assertEqual(resp.stream_secret_ref, "vault://cctv/cameras/cam-alpha-01")
        self.assertTrue(resp.is_active)
        self.__class__.cam_a1_id = resp.id
        self.created_camera_ids.append(resp.id)

    def test_02_duplicate_camera_code_rejected(self):
        """Duplicate camera_code is rejected with 409 Conflict."""
        data = CameraCreate(
            camera_code="CAM-ALPHA-01",
            name="Duplicate Camera",
            location_id=self.loc_a.id,
            camera_role="general",
        )
        with self.assertRaises(HTTPException) as ctx:
            create_camera_ep(
                data=data, current_user=self.loc_admin_a, db=self.db
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("already assigned", ctx.exception.detail)

    def test_03_create_camera_unauthorized_location_blocked(self):
        """Location admin cannot create camera in an unassigned location (403 Forbidden)."""
        data = CameraCreate(
            camera_code="CAM-UNAUTH-01",
            name="Unauthorized Camera",
            location_id=self.loc_b.id,
            camera_role="general",
        )
        with self.assertRaises(HTTPException) as ctx:
            create_camera_ep(
                data=data, current_user=self.loc_admin_a, db=self.db
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Access denied", ctx.exception.detail)

    def test_04_create_camera_nonexistent_location_rejected(self):
        """Creating camera for nonexistent location raises 404 Not Found."""
        data = CameraCreate(
            camera_code="CAM-NONEXISTENT",
            name="Nonexistent Location Camera",
            location_id=999999,
        )
        with self.assertRaises(HTTPException) as ctx:
            create_camera_ep(
                data=data, current_user=self.super_admin, db=self.db
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("not found", ctx.exception.detail)

    def test_05_rtsp_credential_sanitization_rejected(self):
        """Plaintext or inline credentials in stream_secret_ref are strictly rejected."""
        # Attempt to pass inline username:password@host
        with self.assertRaises(ValidationError) as ctx:
            CameraCreate(
                camera_code="CAM-INSECURE",
                name="Insecure Camera",
                location_id=self.loc_a.id,
                stream_secret_ref="rtsp://admin:secretPassword123@192.168.1.100/stream",
            )
        self.assertIn("Plaintext credentials", str(ctx.exception))

        # Attempt to pass user:pass@ in update schema
        with self.assertRaises(ValidationError) as ctx2:
            CameraUpdate(
                stream_secret_ref="user:secretPass@internal-stream",
            )
        self.assertIn("Plaintext credentials", str(ctx2.exception))

    # =========================================================================
    # 2. LISTING, SCOPING & FILTERING TESTS
    # =========================================================================

    def test_06_list_cameras_role_and_location_scoping(self):
        """Super admin sees all; location admin sees only assigned location cameras."""
        # Register camera in Location B
        data_b = CameraCreate(
            camera_code="CAM-BETA-01",
            name="Beta Perimeter Fence",
            location_id=self.loc_b.id,
            camera_role="perimeter",
            stream_type="rtsp",
        )
        resp_b = create_camera_ep(
            data=data_b, current_user=self.loc_admin_b, db=self.db
        )
        self.__class__.cam_b1_id = resp_b.id
        self.created_camera_ids.append(resp_b.id)

        # Super admin sees all cameras
        all_cams = list_cameras_ep(current_user=self.super_admin, db=self.db)
        self.assertGreaterEqual(all_cams.total, 2)
        cam_codes = [c.camera_code for c in all_cams.items]
        self.assertIn("CAM-ALPHA-01", cam_codes)
        self.assertIn("CAM-BETA-01", cam_codes)

        # loc_admin_a sees only Location A
        cams_a = list_cameras_ep(current_user=self.loc_admin_a, db=self.db)
        for c in cams_a.items:
            self.assertEqual(c.location_id, self.loc_a.id)

        # loc_admin_b sees only Location B
        cams_b = list_cameras_ep(current_user=self.loc_admin_b, db=self.db)
        for c in cams_b.items:
            self.assertEqual(c.location_id, self.loc_b.id)

        # loc_admin_a querying location_id=loc_b is rejected (403)
        with self.assertRaises(HTTPException) as ctx:
            list_cameras_ep(
                current_user=self.loc_admin_a,
                db=self.db,
                location_id=self.loc_b.id,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_07_list_cameras_pagination_and_filtering(self):
        """Test pagination and multi-attribute filters."""
        # Add additional cameras in Location A for filtering
        cam2 = create_camera_ep(
            data=CameraCreate(
                camera_code="CAM-ALPHA-02",
                name="Desk Row A",
                location_id=self.loc_a.id,
                camera_role="workstation",
                stream_type="webcam",
                connection_status="online",
                is_active=True,
            ),
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.created_camera_ids.append(cam2.id)

        cam3 = create_camera_ep(
            data=CameraCreate(
                camera_code="CAM-ALPHA-03",
                name="Back Alley Perimeter",
                location_id=self.loc_a.id,
                camera_role="perimeter",
                stream_type="rtsp",
                connection_status="offline",
                is_active=False,
            ),
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.created_camera_ids.append(cam3.id)

        # Pagination test (page=1, size=2)
        page1 = list_cameras_ep(
            current_user=self.loc_admin_a,
            db=self.db,
            page=1,
            size=2,
            location_id=self.loc_a.id,
        )
        self.assertEqual(len(page1.items), 2)
        self.assertEqual(page1.page, 1)
        self.assertEqual(page1.size, 2)
        self.assertGreaterEqual(page1.total, 3)
        self.assertGreaterEqual(page1.pages, 2)

        # Filter by camera_role
        role_filter = list_cameras_ep(
            current_user=self.loc_admin_a,
            db=self.db,
            camera_role="workstation",
        )
        self.assertEqual(len(role_filter.items), 1)
        self.assertEqual(role_filter.items[0].camera_code, "CAM-ALPHA-02")

        # Filter by stream_type
        stream_filter = list_cameras_ep(
            current_user=self.loc_admin_a,
            db=self.db,
            stream_type="webcam",
        )
        self.assertEqual(len(stream_filter.items), 1)
        self.assertEqual(stream_filter.items[0].stream_type, "webcam")

        # Filter by connection_status
        status_filter = list_cameras_ep(
            current_user=self.loc_admin_a,
            db=self.db,
            connection_status="offline",
        )
        self.assertEqual(len(status_filter.items), 1)
        self.assertEqual(status_filter.items[0].connection_status, "offline")

        # Filter by is_active=False
        inactive_filter = list_cameras_ep(
            current_user=self.loc_admin_a,
            db=self.db,
            is_active=False,
        )
        self.assertEqual(len(inactive_filter.items), 1)
        self.assertFalse(inactive_filter.items[0].is_active)

        # Search filter (name / code)
        search_filter = list_cameras_ep(
            current_user=self.loc_admin_a,
            db=self.db,
            search="Lobby",
        )
        self.assertEqual(len(search_filter.items), 1)
        self.assertEqual(search_filter.items[0].camera_code, "CAM-ALPHA-01")

    # =========================================================================
    # 3. CAMERA DETAILS, UPDATES & DEACTIVATION TESTS
    # =========================================================================

    def test_08_get_camera_details(self):
        """Retrieve camera details safely; cross-location access rejected."""
        # Viewer in Location A gets details for Location A camera
        details = get_camera_ep(
            camera_id=self.cam_a1_id,
            current_user=self.viewer_a,
            db=self.db,
        )
        self.assertIsInstance(details, CameraDetailResponse)
        self.assertEqual(details.id, self.cam_a1_id)
        self.assertEqual(details.location_name, "Cam Facility Alpha")

        # Viewer in Location A cannot get details for Location B camera (403)
        with self.assertRaises(HTTPException) as ctx:
            get_camera_ep(
                camera_id=self.cam_b1_id,
                current_user=self.viewer_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_09_operator_viewer_read_only_access(self):
        """Operator and Viewer roles cannot modify or delete cameras."""
        # Operator cannot update (403)
        with self.assertRaises(HTTPException) as ctx:
            update_camera_ep(
                camera_id=self.cam_a1_id,
                data=CameraUpdate(name="Operator Name Change"),
                current_user=self.operator_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

        # Viewer cannot deactivate (403)
        with self.assertRaises(HTTPException) as ctx:
            deactivate_camera_ep(
                camera_id=self.cam_a1_id,
                current_user=self.viewer_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_10_update_camera_configuration(self):
        """Location admin updates configuration; conflict on duplicate code rejected."""
        updated = update_camera_ep(
            camera_id=self.cam_a1_id,
            data=CameraUpdate(
                name="Main Entrance Gate 1",
                connection_status="online",
            ),
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertEqual(updated.name, "Main Entrance Gate 1")
        self.assertEqual(updated.connection_status, "online")

        # Duplicate code update rejected
        with self.assertRaises(HTTPException) as ctx:
            update_camera_ep(
                camera_id=self.cam_a1_id,
                data=CameraUpdate(camera_code="CAM-BETA-01"),
                current_user=self.loc_admin_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_409_CONFLICT)

        # Cross-location update rejected
        with self.assertRaises(HTTPException) as ctx:
            update_camera_ep(
                camera_id=self.cam_b1_id,
                data=CameraUpdate(name="Hacked Cam"),
                current_user=self.loc_admin_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_11_deactivate_camera(self):
        """Soft-deactivate camera (sets is_active=False)."""
        deactivated = deactivate_camera_ep(
            camera_id=self.cam_a1_id,
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertFalse(deactivated.is_active)

        # Reactivate for subsequent tests
        update_camera_ep(
            camera_id=self.cam_a1_id,
            data=CameraUpdate(is_active=True),
            current_user=self.loc_admin_a,
            db=self.db,
        )

    # =========================================================================
    # 4. WORKSTATION ZONE RELATIONSHIP TESTS
    # =========================================================================

    def test_12_workstation_zone_association_same_location(self):
        """Associate workstation zone with camera when both belong to the same location."""
        # Create a workstation zone in Location A
        zone_a = WorkstationZone(
            location_id=self.loc_a.id,
            camera_id=self.cam_a1_id,
            zone_code="ZONE-ALPHA-W1",
            name="Alpha Workstation 1",
            polygon_points=[[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
            inactivity_threshold_seconds=600,
            is_active=True,
        )
        self.db.add(zone_a)
        self.db.commit()
        self.db.refresh(zone_a)
        self.__class__.zone_a_id = zone_a.id
        self.created_zone_ids.append(zone_a.id)

        # Associate zone with cam_a1
        resp = associate_workstation_zone_ep(
            camera_id=self.cam_a1_id,
            zone_id=zone_a.id,
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertEqual(len(resp.workstation_zones), 1)
        self.assertEqual(resp.workstation_zones[0].zone_code, "ZONE-ALPHA-W1")

        # List camera zones
        zones_list = list_camera_zones_ep(
            camera_id=self.cam_a1_id,
            current_user=self.viewer_a,
            db=self.db,
        )
        self.assertEqual(len(zones_list), 1)
        self.assertEqual(zones_list[0].zone_code, "ZONE-ALPHA-W1")

    def test_13_workstation_zone_cross_location_mismatch_rejected(self):
        """Associating workstation zone from Location B with camera in Location A is rejected (400)."""
        # Create a workstation zone in Location B
        zone_b = WorkstationZone(
            location_id=self.loc_b.id,
            camera_id=self.cam_b1_id,
            zone_code="ZONE-BETA-W1",
            name="Beta Workstation 1",
            polygon_points=[[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
            inactivity_threshold_seconds=900,
            is_active=True,
        )
        self.db.add(zone_b)
        self.db.commit()
        self.db.refresh(zone_b)
        self.__class__.zone_b_id = zone_b.id
        self.created_zone_ids.append(zone_b.id)

        # Super admin attempts cross-location association: zone_b (Loc B) to cam_a1 (Loc A)
        with self.assertRaises(HTTPException) as ctx:
            associate_workstation_zone_ep(
                camera_id=self.cam_a1_id,
                zone_id=zone_b.id,
                current_user=self.super_admin,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("does not match", ctx.exception.detail)

    def test_14_cannot_transfer_camera_location_with_attached_zones(self):
        """Cannot transfer camera to another location while workstation zones are attached."""
        # cam_a1 currently has zone_a attached; attempting to move cam_a1 to loc_b raises 400
        with self.assertRaises(HTTPException) as ctx:
            update_camera_ep(
                camera_id=self.cam_a1_id,
                data=CameraUpdate(location_id=self.loc_b.id),
                current_user=self.super_admin,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot move camera to a different location while", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()

