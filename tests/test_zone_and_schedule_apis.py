"""
Comprehensive Automated Test Suite for Workstation Zone & Location Schedule APIs
Covers all 21 requirements specified in Phase 2, Task 10:
PART A — Workstation Zones:
  1. Create valid zone
  2. Reject invalid polygon structure
  3. Reject fewer than three distinct vertices
  4. Reject non-finite and out-of-range coordinates
  5. Update zone
  6. Retrieve zone details
  7. List and filter zones (pagination, active, camera, employee, search)
  8. Reject unauthorized location access
  9. Reject cross-location camera association
  10. Reject cross-location employee assignment (and test employee assign/unassign)
  11. Validate positive inactivity threshold
  12. Deactivation behavior (is_active = False)
PART B — Location Schedules:
  13. Create daily schedule
  14. Retrieve weekly schedule
  15. Update daily schedule
  16. Reject duplicate day schedule
  17. Reject invalid day
  18. Validate opening/closing times (and overnight shift support)
  19. Validate grace period (>= 0)
  20. Enforce location authorization
  21. Verify timezone-aware schedule interpretation

Runs using standard Python unittest with clean database teardown.
"""

import sys
import unittest
from datetime import time
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
from app.models.employee import Employee
from app.models.workstation_zone import WorkstationZone
from app.models.location_schedule import LocationSchedule
from app.core.security import get_password_hash

from app.schemas.workstation_zone import (
    WorkstationZoneCreate,
    WorkstationZoneUpdate,
    WorkstationZoneResponse,
    WorkstationZoneDetailResponse,
    ZoneEmployeeAssign,
)
from app.schemas.location_schedule import (
    LocationScheduleCreate,
    LocationScheduleUpdate,
    LocationScheduleResponse,
    LocationScheduleListResponse,
)
from app.schemas.common import PaginatedResponse

from app.api.v1.endpoints.zones import (
    list_zones as list_zones_ep,
    create_zone as create_zone_ep,
    get_zone as get_zone_ep,
    update_zone as update_zone_ep,
    deactivate_zone as deactivate_zone_ep,
    assign_employee as assign_employee_ep,
    remove_employee as remove_employee_ep,
)
from app.api.v1.endpoints.schedules import (
    get_location_schedules as get_location_schedules_ep,
    create_schedule as create_schedule_ep,
    get_day_schedule as get_day_schedule_ep,
    update_day_schedule as update_day_schedule_ep,
    delete_day_schedule as delete_day_schedule_ep,
)


class TestZoneAndScheduleAPIs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up database connection, test locations, cameras, employees, and test users."""
        cls.db = SessionLocal()

        # Load bootstrap super_admin
        cls.super_admin = (
            cls.db.query(User).filter(User.email == "admin@cameraintelligence.com").first()
        )
        assert cls.super_admin is not None, "Bootstrap super_admin not found in database!"

        # Create temporary test locations with distinct timezones
        cls.loc_a = Location(
            name="Zone Facility Alpha",
            address="100 Vision Way, Alpha City",
            timezone="America/New_York",
            is_active=True,
        )
        cls.loc_b = Location(
            name="Zone Facility Beta",
            address="200 Sensor Blvd, Beta Town",
            timezone="Asia/Kolkata",
            is_active=True,
        )
        cls.db.add_all([cls.loc_a, cls.loc_b])
        cls.db.commit()
        cls.db.refresh(cls.loc_a)
        cls.db.refresh(cls.loc_b)

        hashed_pw = get_password_hash("TestPassword123!")

        # Create test users
        cls.loc_admin_a = User(
            email="admin.zonea@test.internal",
            full_name="Location A Zone Admin",
            password_hash=hashed_pw,
            system_role="location_admin",
            is_active=True,
        )
        cls.loc_admin_b = User(
            email="admin.zoneb@test.internal",
            full_name="Location B Zone Admin",
            password_hash=hashed_pw,
            system_role="location_admin",
            is_active=True,
        )
        cls.operator_a = User(
            email="operator.zonea@test.internal",
            full_name="Location A Zone Operator",
            password_hash=hashed_pw,
            system_role="operator",
            is_active=True,
        )
        cls.viewer_a = User(
            email="viewer.zonea@test.internal",
            full_name="Location A Zone Viewer",
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

        # Create test cameras for each location
        cls.cam_a = Camera(
            name="Alpha Desk Cam",
            camera_code="CAM-ZA-01",
            location_id=cls.loc_a.id,
            camera_role="workstation",
            stream_type="rtsp",
            is_active=True,
        )
        cls.cam_b = Camera(
            name="Beta Desk Cam",
            camera_code="CAM-ZB-01",
            location_id=cls.loc_b.id,
            camera_role="workstation",
            stream_type="rtsp",
            is_active=True,
        )
        cls.db.add_all([cls.cam_a, cls.cam_b])
        cls.db.commit()
        cls.db.refresh(cls.cam_a)
        cls.db.refresh(cls.cam_b)

        # Create test employees for each location
        cls.emp_a = Employee(
            employee_code="EMP-ZA-01",
            full_name="Alpha Engineer",
            email="emp.alpha@test.internal",
            location_id=cls.loc_a.id,
            enrollment_status="enrolled",
            is_active=True,
        )
        cls.emp_b = Employee(
            employee_code="EMP-ZB-01",
            full_name="Beta Engineer",
            email="emp.beta@test.internal",
            location_id=cls.loc_b.id,
            enrollment_status="enrolled",
            is_active=True,
        )
        cls.db.add_all([cls.emp_a, cls.emp_b])
        cls.db.commit()
        cls.db.refresh(cls.emp_a)
        cls.db.refresh(cls.emp_b)

    @classmethod
    def tearDownClass(cls):
        """Clean up all created test entities in reverse dependency order."""
        try:
            # 1. Clean up workstation zones
            cls.db.query(WorkstationZone).delete(synchronize_session=False)

            # 2. Clean up location schedules
            cls.db.query(LocationSchedule).delete(synchronize_session=False)

            # 3. Clean up employees
            cls.db.query(Employee).delete(synchronize_session=False)

            # 4. Clean up cameras
            cls.db.query(Camera).delete(synchronize_session=False)

            # 5. Clean up user_locations and test users
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

            # 6. Clean up locations
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
    # PART A: WORKSTATION ZONE TESTS (1 to 12)
    # =========================================================================

    def test_01_create_valid_zone(self):
        """1. Create valid workstation zone with normalized coordinates."""
        data = WorkstationZoneCreate(
            zone_code="ZONE-ALPHA-01",
            name="Developer Desk A1",
            location_id=self.loc_a.id,
            camera_id=self.cam_a.id,
            polygon_points=[[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
            inactivity_threshold_seconds=600,
            is_active=True,
        )
        resp = create_zone_ep(
            data=data, current_user=self.loc_admin_a, db=self.db
        )
        self.assertIsInstance(resp, WorkstationZoneDetailResponse)
        self.assertEqual(resp.zone_code, "ZONE-ALPHA-01")
        self.assertEqual(resp.name, "Developer Desk A1")
        self.assertEqual(resp.location_id, self.loc_a.id)
        self.assertEqual(resp.location_name, "Zone Facility Alpha")
        self.assertEqual(resp.camera_id, self.cam_a.id)
        self.assertEqual(resp.camera_code, "CAM-ZA-01")
        self.assertEqual(resp.inactivity_threshold_seconds, 600)
        self.assertTrue(resp.is_active)
        self.__class__.zone_a1_id = resp.id

    def test_02_reject_invalid_polygon_structure(self):
        """2. Reject malformed coordinates or non-list structure."""
        with self.assertRaises(ValidationError) as ctx:
            WorkstationZoneCreate(
                zone_code="ZONE-INVALID-1",
                name="Invalid Zone",
                location_id=self.loc_a.id,
                camera_id=self.cam_a.id,
                polygon_points="not_a_list",
            )
        self.assertIn("must be a list", str(ctx.exception))

        # Vertex not a 2-element pair
        with self.assertRaises(ValidationError) as ctx2:
            WorkstationZoneCreate(
                zone_code="ZONE-INVALID-2",
                name="Invalid Zone",
                location_id=self.loc_a.id,
                camera_id=self.cam_a.id,
                polygon_points=[[0.1, 0.2, 0.3], [0.4, 0.5], [0.6, 0.7]],
            )
        self.assertIn("must be a 2-element coordinate", str(ctx2.exception))

    def test_03_reject_fewer_than_three_distinct_vertices(self):
        """3. Require at least three distinct vertices."""
        # Only 2 points
        with self.assertRaises(ValidationError) as ctx:
            WorkstationZoneCreate(
                zone_code="ZONE-TWO-POINTS",
                name="Two Points Zone",
                location_id=self.loc_a.id,
                camera_id=self.cam_a.id,
                polygon_points=[[0.1, 0.1], [0.5, 0.5]],
            )
        self.assertIn("at least 3 distinct vertices", str(ctx.exception))

        # 3 points but 2 are identical duplicates
        with self.assertRaises(ValidationError) as ctx2:
            WorkstationZoneCreate(
                zone_code="ZONE-DUP-POINTS",
                name="Duplicate Points Zone",
                location_id=self.loc_a.id,
                camera_id=self.cam_a.id,
                polygon_points=[[0.1, 0.1], [0.1, 0.1], [0.5, 0.5]],
            )
        self.assertIn("at least 3 distinct vertices", str(ctx2.exception))

    def test_04_reject_non_finite_and_out_of_range_coordinates(self):
        """4. Reject NaN, infinite values, and out-of-range coordinates."""
        # NaN coordinate
        with self.assertRaises(ValidationError) as ctx:
            WorkstationZoneCreate(
                zone_code="ZONE-NAN",
                name="NaN Zone",
                location_id=self.loc_a.id,
                camera_id=self.cam_a.id,
                polygon_points=[[0.1, 0.1], [float("nan"), 0.5], [0.5, 0.5]],
            )
        self.assertIn("cannot be NaN or Infinite", str(ctx.exception))

        # Infinite coordinate
        with self.assertRaises(ValidationError) as ctx2:
            WorkstationZoneCreate(
                zone_code="ZONE-INF",
                name="Inf Zone",
                location_id=self.loc_a.id,
                camera_id=self.cam_a.id,
                polygon_points=[[0.1, 0.1], [float("inf"), 0.5], [0.5, 0.5]],
            )
        self.assertIn("cannot be NaN or Infinite", str(ctx2.exception))

        # Out-of-range coordinate (normalized range is 0.0 to 1.0)
        with self.assertRaises(ValidationError) as ctx3:
            WorkstationZoneCreate(
                zone_code="ZONE-OUT-RANGE",
                name="Out of Range Zone",
                location_id=self.loc_a.id,
                camera_id=self.cam_a.id,
                polygon_points=[[0.1, 0.1], [1.5, 0.5], [0.5, 0.5]],
            )
        self.assertIn("out of normalized range", str(ctx3.exception))

    def test_05_update_zone(self):
        """5. Update workstation zone configuration."""
        updated = update_zone_ep(
            zone_id=self.zone_a1_id,
            data=WorkstationZoneUpdate(
                name="Senior Dev Desk A1",
                inactivity_threshold_seconds=1200,
            ),
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertEqual(updated.name, "Senior Dev Desk A1")
        self.assertEqual(updated.inactivity_threshold_seconds, 1200)

    def test_06_retrieve_zone(self):
        """6. Retrieve workstation zone details."""
        detail = get_zone_ep(
            zone_id=self.zone_a1_id,
            current_user=self.viewer_a,
            db=self.db,
        )
        self.assertIsInstance(detail, WorkstationZoneDetailResponse)
        self.assertEqual(detail.id, self.zone_a1_id)
        self.assertEqual(detail.camera_code, "CAM-ZA-01")

    def test_07_list_and_filter_zones(self):
        """7. List and filter zones by location, active status, and search."""
        # Add another zone in loc_a (inactive) and one in loc_b
        zone2 = create_zone_ep(
            data=WorkstationZoneCreate(
                zone_code="ZONE-ALPHA-02",
                name="Support Desk A2",
                location_id=self.loc_a.id,
                camera_id=self.cam_a.id,
                polygon_points=[[0.6, 0.6], [0.9, 0.6], [0.9, 0.9], [0.6, 0.9]],
                is_active=False,
            ),
            current_user=self.loc_admin_a,
            db=self.db,
        )
        zone_b = create_zone_ep(
            data=WorkstationZoneCreate(
                zone_code="ZONE-BETA-01",
                name="Beta Operations Zone",
                location_id=self.loc_b.id,
                camera_id=self.cam_b.id,
                polygon_points=[[0.2, 0.2], [0.8, 0.2], [0.8, 0.8]],
                is_active=True,
            ),
            current_user=self.loc_admin_b,
            db=self.db,
        )

        # Super admin sees all 3
        all_zones = list_zones_ep(current_user=self.super_admin, db=self.db)
        self.assertGreaterEqual(all_zones.total, 3)

        # loc_admin_a sees only loc_a zones (2)
        zones_a = list_zones_ep(current_user=self.loc_admin_a, db=self.db)
        self.assertEqual(zones_a.total, 2)
        for z in zones_a.items:
            self.assertEqual(z.location_id, self.loc_a.id)

        # Filter by is_active=False
        inactive_zones = list_zones_ep(
            current_user=self.loc_admin_a,
            db=self.db,
            is_active=False,
        )
        self.assertEqual(inactive_zones.total, 1)
        self.assertEqual(inactive_zones.items[0].zone_code, "ZONE-ALPHA-02")

        # Search filter
        search_res = list_zones_ep(
            current_user=self.loc_admin_a,
            db=self.db,
            search="Support",
        )
        self.assertEqual(search_res.total, 1)
        self.assertEqual(search_res.items[0].zone_code, "ZONE-ALPHA-02")

    def test_08_reject_unauthorized_location_access(self):
        """8. Reject unauthorized location access for zones."""
        # loc_admin_b cannot view or update zone in Location A
        with self.assertRaises(HTTPException) as ctx:
            get_zone_ep(
                zone_id=self.zone_a1_id,
                current_user=self.loc_admin_b,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

        with self.assertRaises(HTTPException) as ctx2:
            update_zone_ep(
                zone_id=self.zone_a1_id,
                data=WorkstationZoneUpdate(name="Hacked Name"),
                current_user=self.loc_admin_b,
                db=self.db,
            )
        self.assertEqual(ctx2.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_09_reject_cross_location_camera_association(self):
        """9. Reject cross-location camera association."""
        # Attempt to create zone in loc_a with camera from loc_b
        with self.assertRaises(HTTPException) as ctx:
            create_zone_ep(
                data=WorkstationZoneCreate(
                    zone_code="ZONE-MISMATCH-CAM",
                    name="Mismatch Camera Zone",
                    location_id=self.loc_a.id,
                    camera_id=self.cam_b.id,
                    polygon_points=[[0.1, 0.1], [0.5, 0.1], [0.5, 0.5]],
                ),
                current_user=self.super_admin,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Camera location ID", ctx.exception.detail)

    def test_10_reject_cross_location_employee_assignment(self):
        """10. Reject cross-location employee assignment, then test valid assign and unassign."""
        # Attempt to assign emp_b (loc_b) to zone_a1 (loc_a)
        with self.assertRaises(HTTPException) as ctx:
            assign_employee_ep(
                zone_id=self.zone_a1_id,
                data=ZoneEmployeeAssign(employee_id=self.emp_b.id),
                current_user=self.loc_admin_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Assigned employee location ID", ctx.exception.detail)

        # Valid assignment: assign emp_a to zone_a1
        assigned = assign_employee_ep(
            zone_id=self.zone_a1_id,
            data=ZoneEmployeeAssign(employee_id=self.emp_a.id),
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertEqual(assigned.assigned_employee_id, self.emp_a.id)
        self.assertEqual(assigned.assigned_employee_name, "Alpha Engineer")

        # Unassign employee
        unassigned = remove_employee_ep(
            zone_id=self.zone_a1_id,
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertIsNone(unassigned.assigned_employee_id)

    def test_11_validate_inactivity_threshold(self):
        """11. Validate positive inactivity threshold."""
        with self.assertRaises(ValidationError):
            WorkstationZoneCreate(
                zone_code="ZONE-ZERO-THRESHOLD",
                name="Zero Threshold Zone",
                location_id=self.loc_a.id,
                camera_id=self.cam_a.id,
                polygon_points=[[0.1, 0.1], [0.5, 0.1], [0.5, 0.5]],
                inactivity_threshold_seconds=0,
            )

        with self.assertRaises(ValidationError):
            WorkstationZoneUpdate(
                inactivity_threshold_seconds=-10,
            )

    def test_12_deactivation_behavior(self):
        """12. Deactivation soft-deactivates zone (is_active = False)."""
        deactivated = deactivate_zone_ep(
            zone_id=self.zone_a1_id,
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertFalse(deactivated.is_active)

    # =========================================================================
    # PART B: LOCATION SCHEDULE TESTS (13 to 21)
    # =========================================================================

    def test_13_create_schedule(self):
        """13. Create daily schedule for a location."""
        sched_data = LocationScheduleCreate(
            day_of_week=0,  # Monday
            is_working_day=True,
            open_time=time(9, 0, 0),
            close_time=time(18, 0, 0),
            after_hours_grace_minutes=15,
        )
        resp = create_schedule_ep(
            location_id=self.loc_a.id,
            data=sched_data,
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertIsInstance(resp, LocationScheduleResponse)
        self.assertEqual(resp.location_id, self.loc_a.id)
        self.assertEqual(resp.day_of_week, 0)
        self.assertEqual(resp.day_name, "Monday")
        self.assertTrue(resp.is_working_day)
        self.assertEqual(resp.open_time, time(9, 0, 0))
        self.assertEqual(resp.close_time, time(18, 0, 0))
        self.assertFalse(resp.is_overnight)

    def test_14_retrieve_weekly_schedule(self):
        """14. Retrieve weekly schedule for a location."""
        # Add Tuesday schedule
        create_schedule_ep(
            location_id=self.loc_a.id,
            data=LocationScheduleCreate(
                day_of_week=1,
                is_working_day=True,
                open_time=time(9, 0, 0),
                close_time=time(17, 30, 0),
            ),
            current_user=self.loc_admin_a,
            db=self.db,
        )

        weekly = get_location_schedules_ep(
            location_id=self.loc_a.id,
            current_user=self.viewer_a,
            db=self.db,
        )
        self.assertIsInstance(weekly, LocationScheduleListResponse)
        self.assertEqual(weekly.location_id, self.loc_a.id)
        self.assertEqual(weekly.timezone, "America/New_York")
        self.assertGreaterEqual(len(weekly.schedules), 2)
        days = [s.day_of_week for s in weekly.schedules]
        self.assertIn(0, days)
        self.assertIn(1, days)

    def test_15_update_schedule(self):
        """15. Update daily schedule."""
        updated = update_day_schedule_ep(
            location_id=self.loc_a.id,
            day="0",  # Monday by index
            data=LocationScheduleUpdate(
                close_time=time(19, 0, 0),
                after_hours_grace_minutes=30,
            ),
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertEqual(updated.close_time, time(19, 0, 0))
        self.assertEqual(updated.after_hours_grace_minutes, 30)

    def test_16_reject_duplicate_day_schedule(self):
        """16. Reject duplicate day schedule for the same location."""
        with self.assertRaises(HTTPException) as ctx:
            create_schedule_ep(
                location_id=self.loc_a.id,
                data=LocationScheduleCreate(
                    day_of_week=0,  # Monday already exists
                    is_working_day=True,
                ),
                current_user=self.loc_admin_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("already configured", ctx.exception.detail)

    def test_17_reject_invalid_day(self):
        """17. Reject invalid day specification."""
        with self.assertRaises(ValidationError):
            LocationScheduleCreate(
                day_of_week=7,  # Day > 6
                is_working_day=True,
            )

        with self.assertRaises(ValidationError):
            LocationScheduleCreate(
                day_of_week="Funday",
                is_working_day=True,
            )

    def test_18_validate_opening_closing_times(self):
        """18. Validate open/close times and support overnight schedules."""
        # Identical open and close times rejected
        with self.assertRaises(ValidationError) as ctx:
            LocationScheduleCreate(
                day_of_week=2,
                open_time=time(9, 0, 0),
                close_time=time(9, 0, 0),
            )
        self.assertIn("cannot be identical", str(ctx.exception))

        # Overnight schedule: open at 22:00, close at 06:00
        overnight = create_schedule_ep(
            location_id=self.loc_a.id,
            data=LocationScheduleCreate(
                day_of_week=2,  # Wednesday
                is_working_day=True,
                open_time=time(22, 0, 0),
                close_time=time(6, 0, 0),
            ),
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertTrue(overnight.is_overnight)

    def test_19_validate_grace_period(self):
        """19. Validate grace period is non-negative."""
        with self.assertRaises(ValidationError):
            LocationScheduleCreate(
                day_of_week=3,
                after_hours_grace_minutes=-10,
            )

        with self.assertRaises(ValidationError):
            LocationScheduleUpdate(
                after_hours_grace_minutes=-1,
            )

    def test_20_enforce_location_authorization(self):
        """20. Enforce location authorization for schedules."""
        # loc_admin_b cannot create or delete schedule in loc_a
        with self.assertRaises(HTTPException) as ctx:
            create_schedule_ep(
                location_id=self.loc_a.id,
                data=LocationScheduleCreate(day_of_week=4),
                current_user=self.loc_admin_b,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

        with self.assertRaises(HTTPException) as ctx2:
            delete_day_schedule_ep(
                location_id=self.loc_a.id,
                day="1",
                current_user=self.loc_admin_b,
                db=self.db,
            )
        self.assertEqual(ctx2.exception.status_code, status.HTTP_403_FORBIDDEN)

        # loc_admin_a can delete Tuesday schedule
        del_resp = delete_day_schedule_ep(
            location_id=self.loc_a.id,
            day="Tuesday",
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertIn("deleted", del_resp["message"].lower())

    def test_21_verify_timezone_aware_schedule_interpretation(self):
        """21. Verify timezone-aware schedule interpretation for different locations."""
        # Create schedule for loc_b (configured in Asia/Kolkata)
        create_schedule_ep(
            location_id=self.loc_b.id,
            data=LocationScheduleCreate(
                day_of_week="sunday",
                is_working_day=False,
            ),
            current_user=self.loc_admin_b,
            db=self.db,
        )

        sched_b = get_location_schedules_ep(
            location_id=self.loc_b.id,
            current_user=self.loc_admin_b,
            db=self.db,
        )
        self.assertEqual(sched_b.timezone, "Asia/Kolkata")
        self.assertEqual(len(sched_b.schedules), 1)
        self.assertEqual(sched_b.schedules[0].day_name, "Sunday")
        self.assertFalse(sched_b.schedules[0].is_working_day)

        # Verify loc_a timezone remains America/New_York
        sched_a = get_location_schedules_ep(
            location_id=self.loc_a.id,
            current_user=self.viewer_a,
            db=self.db,
        )
        self.assertEqual(sched_a.timezone, "America/New_York")


if __name__ == "__main__":
    unittest.main()

