"""
Comprehensive Test Suite for Workstation Session Lifecycle Fixes
Task 2 Verification

Covers:
1. Camera disconnection during occupancy (immediate & grace period resets).
2. Camera reconnection within grace period preserves occupancy state.
3. Camera disconnect grace period expiration & duplicate prevention.
4. Late face recognition: active occupant identity resolution emits workstation_active.
5. Late face recognition creates exactly one backend PresenceSession.
6. Active and idle duration accumulation across ACTIVE -> IDLE -> ACTIVE -> Departure.
7. Duration protection against negative durations and out-of-order timestamps.
8. Edge restart with active occupant (re-detection updates existing session without duplicate).
9. Stale session reconciliation for offline cameras.
10. Stale session reconciliation respects offline camera grace periods.
11. Duplicate departure handling (idempotent, safe).
12. Multi-employee isolation in shared workstation zones.
"""

import sys
import time
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Server sys.path
SERVER_ROOT = PROJECT_ROOT / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.database.session import SessionLocal
from app.models.location import Location
from app.models.camera import Camera
from app.models.employee import Employee
from app.models.workstation_zone import WorkstationZone
from app.models.presence_session import PresenceSession
from app.models.detection_event import DetectionEvent
from app.models.alert import Alert
from app.services.event_service import (
    process_presence_on_event,
    reconcile_stale_presence_sessions,
    _accumulate_workstation_duration,
)

from ai_engine.analytics.polygon import PolygonZone
from ai_engine.analytics.occupancy_tracker import (
    OccupancyState,
    ZoneOccupancyTracker,
    MultiZoneManager,
)
from ai_engine.pipeline.detector import TrackedPerson


class TestWorkstationSessionLifecycle(unittest.TestCase):
    @classmethod
    def _cleanup_test_data(cls, db):
        loc_names = ["Lifecycle Test HQ"]
        locs = db.query(Location).filter(Location.name.in_(loc_names)).all()
        loc_ids = [l.id for l in locs]
        if loc_ids:
            # Delete dependent records
            db.query(Alert).filter(Alert.location_id.in_(loc_ids)).delete(synchronize_session=False)
            db.query(DetectionEvent).filter(DetectionEvent.location_id.in_(loc_ids)).delete(synchronize_session=False)
            db.query(PresenceSession).filter(PresenceSession.location_id.in_(loc_ids)).delete(synchronize_session=False)
            db.query(WorkstationZone).filter(WorkstationZone.location_id.in_(loc_ids)).delete(synchronize_session=False)
            db.query(Camera).filter(Camera.location_id.in_(loc_ids)).delete(synchronize_session=False)
            db.query(Employee).filter(Employee.location_id.in_(loc_ids)).delete(synchronize_session=False)
            db.query(Location).filter(Location.id.in_(loc_ids)).delete(synchronize_session=False)
            db.commit()

    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls._cleanup_test_data(cls.db)

        # Standard normalized polygon rectangle
        cls.norm_polygon = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]
        cls.frame = np.full((1000, 1000, 3), 120, dtype=np.uint8)

        # Create persistent test location, cameras, employees, zones
        cls.loc = Location(
            name="Lifecycle Test HQ",
            address="100 Test St",
            timezone="UTC",
            is_active=True,
        )
        cls.db.add(cls.loc)
        cls.db.commit()
        cls.db.refresh(cls.loc)

        cls.cam1 = Camera(
            camera_code="TEST-CAM-WSLC1",
            name="Zone Camera 1",
            location_id=cls.loc.id,
            camera_role="workstation",
            connection_status="online",
            is_active=True,
        )
        cls.cam2 = Camera(
            camera_code="TEST-CAM-WSLC2",
            name="Zone Camera 2",
            location_id=cls.loc.id,
            camera_role="workstation",
            connection_status="online",
            is_active=True,
        )
        cls.db.add_all([cls.cam1, cls.cam2])
        cls.db.commit()
        cls.db.refresh(cls.cam1)
        cls.db.refresh(cls.cam2)

        cls.emp1 = Employee(
            employee_code="TEST-EMP-WSLC1",
            full_name="Alice Smith",
            location_id=cls.loc.id,
            is_active=True,
        )
        cls.emp2 = Employee(
            employee_code="TEST-EMP-WSLC2",
            full_name="Bob Jones",
            location_id=cls.loc.id,
            is_active=True,
        )
        cls.db.add_all([cls.emp1, cls.emp2])
        cls.db.commit()
        cls.db.refresh(cls.emp1)
        cls.db.refresh(cls.emp2)

        cls.zone1 = WorkstationZone(
            zone_code="TEST-ZONE-WSLC1",
            name="Desk Zone 1",
            camera_id=cls.cam1.id,
            location_id=cls.loc.id,
            polygon_points=cls.norm_polygon,
            inactivity_threshold_seconds=15.0,
            is_active=True,
        )
        cls.zone2 = WorkstationZone(
            zone_code="TEST-ZONE-WSLC2",
            name="Desk Zone 2",
            camera_id=cls.cam2.id,
            location_id=cls.loc.id,
            polygon_points=cls.norm_polygon,
            inactivity_threshold_seconds=15.0,
            is_active=True,
        )
        cls.db.add_all([cls.zone1, cls.zone2])
        cls.db.commit()
        cls.db.refresh(cls.zone1)
        cls.db.refresh(cls.zone2)

        cls.loc_id = cls.loc.id
        cls.cam1_id = cls.cam1.id
        cls.cam2_id = cls.cam2.id
        cls.emp1_id = cls.emp1.id
        cls.emp2_id = cls.emp2.id
        cls.zone1_id = cls.zone1.id
        cls.zone2_id = cls.zone2.id
        cls.db.close()

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        cls._cleanup_test_data(db)
        db.close()

    def setUp(self):
        self.db = SessionLocal()
        self.db.query(Alert).filter(Alert.location_id == self.loc_id).delete(synchronize_session=False)
        self.db.query(DetectionEvent).filter(DetectionEvent.location_id == self.loc_id).delete(synchronize_session=False)
        self.db.query(PresenceSession).filter(PresenceSession.location_id == self.loc_id).delete(synchronize_session=False)
        self.cam1 = self.db.query(Camera).filter(Camera.id == self.cam1_id).first()
        self.cam2 = self.db.query(Camera).filter(Camera.id == self.cam2_id).first()
        self.emp1 = self.db.query(Employee).filter(Employee.id == self.emp1_id).first()
        self.emp2 = self.db.query(Employee).filter(Employee.id == self.emp2_id).first()
        self.zone1 = self.db.query(WorkstationZone).filter(WorkstationZone.id == self.zone1_id).first()
        self.zone2 = self.db.query(WorkstationZone).filter(WorkstationZone.id == self.zone2_id).first()
        self.cam1.connection_status = "online"
        self.cam1.is_active = True
        self.cam2.connection_status = "online"
        self.cam2.is_active = True
        self.db.commit()

    def tearDown(self):
        self.db.close()

    # -------------------------------------------------------------------------
    # 1. Camera Disconnect & Reconnect Handling Tests
    # -------------------------------------------------------------------------

    def test_01_camera_disconnection_during_occupancy(self):
        """1. Camera disconnect emits departure event, resets zone, and preserves other cameras."""
        mgr = MultiZoneManager(disconnect_grace_period_seconds=10.0)

        pz1 = PolygonZone(zone_id=self.zone1.id, zone_code="TEST-ZONE-WSLC1", name="Desk 1", camera_id=self.cam1.id, location_id=self.loc.id, polygon_points=self.norm_polygon)
        pz2 = PolygonZone(zone_id=self.zone2.id, zone_code="TEST-ZONE-WSLC2", name="Desk 2", camera_id=self.cam2.id, location_id=self.loc.id, polygon_points=self.norm_polygon)
        mgr.register_zone(pz1)
        mgr.register_zone(pz2)

        p1 = TrackedPerson(x1=300.0, y1=300.0, x2=450.0, y2=600.0, confidence=0.95, tracker_id=11, recognized_employee_id=self.emp1.id)
        p2 = TrackedPerson(x1=300.0, y1=300.0, x2=450.0, y2=600.0, confidence=0.95, tracker_id=22, recognized_employee_id=self.emp2.id)

        # Both cameras active at t=100
        mgr.process_frame(camera_id=self.cam1.id, frame_bgr=self.frame, persons=[p1], timestamp=100.0)
        mgr.process_frame(camera_id=self.cam2.id, frame_bgr=self.frame, persons=[p2], timestamp=100.0)

        # Camera 1 disconnects (immediate reset)
        departures = mgr.reset_camera(camera_id=self.cam1.id, emit_exit_events=True, timestamp=105.0)

        self.assertEqual(len(departures), 1)
        dep = departures[0]
        self.assertEqual(dep.camera_id, self.cam1.id)
        self.assertEqual(dep.employee_id, self.emp1.id)
        self.assertEqual(dep.event_type, "workstation_idle")
        self.assertEqual(dep.metadata_json["action"], "exit")
        self.assertEqual(dep.metadata_json["reason"], "camera_disconnect")
        self.assertTrue(dep.metadata_json["is_departure"])

        # Verify Camera 1 zone is now vacant
        tracker1 = mgr.get_zone_tracker(camera_id=self.cam1.id, zone_id=self.zone1.id)
        self.assertEqual(len(tracker1.occupants), 0)

        # Verify Camera 2 zone is completely preserved and still ACTIVE!
        tracker2 = mgr.get_zone_tracker(camera_id=self.cam2.id, zone_id=self.zone2.id)
        emp2_key = f"emp_{self.emp2.id}"
        self.assertIn(emp2_key, tracker2.occupants)
        self.assertEqual(tracker2.occupants[emp2_key].occupancy_state, OccupancyState.ACTIVE)

    def test_02_camera_reconnect_within_grace_period_preserves_state(self):
        """2. Temporary disconnect within reconnect grace period preserves occupancy state."""
        mgr = MultiZoneManager(disconnect_grace_period_seconds=10.0)
        pz1 = PolygonZone(zone_id=self.zone1.id, zone_code="TEST-ZONE-WSLC1", name="Desk 1", camera_id=self.cam1.id, location_id=self.loc.id, polygon_points=self.norm_polygon)
        mgr.register_zone(pz1)

        p1 = TrackedPerson(x1=300.0, y1=300.0, x2=450.0, y2=600.0, confidence=0.95, tracker_id=11, recognized_employee_id=self.emp1.id)
        mgr.process_frame(camera_id=self.cam1.id, frame_bgr=self.frame, persons=[p1], timestamp=100.0)

        # Disconnect detected at t=102.0
        evs1 = mgr.handle_camera_disconnect(camera_id=self.cam1.id, timestamp=102.0)
        self.assertEqual(len(evs1), 0)  # Grace period has not elapsed

        # Camera still degraded at t=108.0 (elapsed = 6.0s < 10.0s grace period)
        evs2 = mgr.handle_camera_disconnect(camera_id=self.cam1.id, timestamp=108.0)
        self.assertEqual(len(evs2), 0)

        # Camera successfully reconnects at t=109.0
        mgr.handle_camera_reconnect(camera_id=self.cam1.id)

        # State must remain ACTIVE
        tracker = mgr.get_zone_tracker(camera_id=self.cam1.id, zone_id=self.zone1.id)
        emp1_key = f"emp_{self.emp1.id}"
        self.assertEqual(tracker.occupants[emp1_key].occupancy_state, OccupancyState.ACTIVE)

    def test_03_camera_disconnect_grace_period_expiration(self):
        """3. When grace period expires, departure is emitted once and subsequent calls are idempotent."""
        mgr = MultiZoneManager(disconnect_grace_period_seconds=10.0)
        pz1 = PolygonZone(zone_id=self.zone1.id, zone_code="TEST-ZONE-WSLC1", name="Desk 1", camera_id=self.cam1.id, location_id=self.loc.id, polygon_points=self.norm_polygon)
        mgr.register_zone(pz1)

        p1 = TrackedPerson(x1=300.0, y1=300.0, x2=450.0, y2=600.0, confidence=0.95, tracker_id=11, recognized_employee_id=self.emp1.id)
        mgr.process_frame(camera_id=self.cam1.id, frame_bgr=self.frame, persons=[p1], timestamp=100.0)

        # Disconnect starts at t=100.0
        mgr.handle_camera_disconnect(camera_id=self.cam1.id, timestamp=100.0)

        # Check at t=111.0 (> 10.0s grace period)
        evs = mgr.handle_camera_disconnect(camera_id=self.cam1.id, timestamp=111.0)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0].employee_id, self.emp1.id)
        self.assertTrue(evs[0].metadata_json["is_departure"])

        # Check again at t=115.0: MUST BE IDEMPOTENT (0 events emitted)
        evs_dup = mgr.handle_camera_disconnect(camera_id=self.cam1.id, timestamp=115.0)
        self.assertEqual(len(evs_dup), 0)

    # -------------------------------------------------------------------------
    # 2. Late Face Recognition Tests
    # -------------------------------------------------------------------------

    def test_04_late_face_recognition_emits_workstation_active(self):
        """4. Occupant entering anonymously, when recognized later, emits workstation_active with employee_id."""
        zone = PolygonZone(zone_id=self.zone1.id, zone_code="TEST-ZONE-WSLC1", name="Desk 1", camera_id=self.cam1.id, location_id=self.loc.id, polygon_points=self.norm_polygon)
        tracker = ZoneOccupancyTracker(zone=zone)

        # Frame 1 (t=100): Person enters anonymously
        p_anon = TrackedPerson(x1=300.0, y1=300.0, x2=450.0, y2=600.0, confidence=0.92, tracker_id=77, recognized_employee_id=None)
        evs1 = tracker.update(self.frame, [p_anon], timestamp=100.0)
        self.assertEqual(len(evs1), 1)
        self.assertEqual(evs1[0].event_type, "workstation_active")
        self.assertIsNone(evs1[0].employee_id)
        self.assertEqual(evs1[0].tracker_id, f"cam{self.cam1.id}_trk_77")

        # Frame 2 (t=102): Face recognized as Employee 1
        p_rec = TrackedPerson(x1=300.0, y1=300.0, x2=450.0, y2=600.0, confidence=0.95, tracker_id=77, recognized_employee_id=self.emp1.id)
        evs2 = tracker.update(self.frame, [p_rec], timestamp=102.0)
        self.assertEqual(len(evs2), 1)
        self.assertEqual(evs2[0].event_type, "workstation_active")
        self.assertEqual(evs2[0].employee_id, self.emp1.id)
        self.assertEqual(evs2[0].metadata_json["action"], "identity_resolved")
        self.assertEqual(evs2[0].metadata_json["identification_event"], "late_recognition")

        # Frame 3 (t=104): Continued presence with employee recognized (NO DUPLICATE EVENT)
        evs3 = tracker.update(self.frame, [p_rec], timestamp=104.0)
        self.assertEqual(len(evs3), 0)

    def test_05_late_face_recognition_creates_single_backend_presence_session(self):
        """5. Late face recognition results in exactly one PresenceSession created in the backend."""
        now = datetime.now(timezone.utc)

        # 1. Anonymous entry event arrives
        ev_anon = DetectionEvent(
            location_id=self.loc.id,
            camera_id=self.cam1.id,
            event_type="workstation_active",
            occurred_at=now,
            employee_id=None,
            workstation_zone_id=self.zone1.id,
            tracker_id=f"cam{self.cam1.id}_trk_77",
            confidence=0.92,
            metadata_json={"previous_state": "vacant", "current_state": "active"},
        )
        self.db.add(ev_anon)
        self.db.flush()
        res_anon = process_presence_on_event(db=self.db, event=ev_anon, camera=self.cam1)
        self.assertIsNone(res_anon)  # Unidentified person does not create PresenceSession

        # 2. Late recognition event arrives with employee_id = emp1.id
        ev_late = DetectionEvent(
            location_id=self.loc.id,
            camera_id=self.cam1.id,
            event_type="workstation_active",
            occurred_at=now + timedelta(seconds=2),
            employee_id=self.emp1.id,
            workstation_zone_id=self.zone1.id,
            tracker_id=f"cam{self.cam1.id}_trk_77",
            confidence=0.95,
            metadata_json={"action": "identity_resolved", "identification_event": "late_recognition"},
        )
        self.db.add(ev_late)
        self.db.flush()
        res_late = process_presence_on_event(db=self.db, event=ev_late, camera=self.cam1)
        self.assertIsNotNone(res_late)
        self.assertEqual(res_late.employee_id, self.emp1.id)
        self.assertEqual(res_late.status, "active")

        # 3. Subsequent event arrives
        ev_sub = DetectionEvent(
            location_id=self.loc.id,
            camera_id=self.cam1.id,
            event_type="workstation_active",
            occurred_at=now + timedelta(seconds=4),
            employee_id=self.emp1.id,
            workstation_zone_id=self.zone1.id,
            tracker_id=f"cam{self.cam1.id}_trk_77",
            confidence=0.95,
        )
        self.db.add(ev_sub)
        self.db.flush()
        res_sub = process_presence_on_event(db=self.db, event=ev_sub, camera=self.cam1)
        self.assertEqual(res_sub.id, res_late.id)

        # Assert exactly ONE PresenceSession in database
        total_sessions = self.db.query(PresenceSession).filter(PresenceSession.location_id == self.loc.id).count()
        self.assertEqual(total_sessions, 1)

    # -------------------------------------------------------------------------
    # 3. Active and Idle Duration Accumulation Tests
    # -------------------------------------------------------------------------

    def test_06_active_and_idle_duration_accumulation(self):
        """6. PresenceSession correctly accumulates active_seconds and idle_seconds across transitions."""
        t0 = datetime(2026, 11, 17, 10, 0, 0, tzinfo=timezone.utc)

        # 1. Entry at t0
        ev_entry = DetectionEvent(
            location_id=self.loc.id,
            camera_id=self.cam1.id,
            event_type="workstation_active",
            occurred_at=t0,
            employee_id=self.emp1.id,
            workstation_zone_id=self.zone1.id,
            tracker_id="cam1_trk_1",
            confidence=1.0,
        )
        self.db.add(ev_entry)
        self.db.flush()
        sess = process_presence_on_event(db=self.db, event=ev_entry, camera=self.cam1)
        self.assertEqual(sess.active_seconds, 0)
        self.assertEqual(sess.idle_seconds, 0)

        # 2. Inactivity event at t0 + 900s (user stopped moving for 900s)
        t1 = t0 + timedelta(seconds=900)
        ev_idle = DetectionEvent(
            location_id=self.loc.id,
            camera_id=self.cam1.id,
            event_type="workstation_idle",
            occurred_at=t1,
            employee_id=self.emp1.id,
            workstation_zone_id=self.zone1.id,
            tracker_id="cam1_trk_1",
            confidence=1.0,
            metadata_json={"previous_state": "active", "current_state": "idle", "inactivity_duration_seconds": 900.0},
        )
        self.db.add(ev_idle)
        self.db.flush()
        sess = process_presence_on_event(db=self.db, event=ev_idle, camera=self.cam1)
        self.assertEqual(sess.status, "idle")
        self.assertEqual(sess.idle_seconds, 900)
        self.assertEqual(sess.active_seconds, 0)

        # 3. Resume activity event at t0 + 1000s (user resumed motion after 100s of idle)
        t2 = t0 + timedelta(seconds=1000)
        ev_resume = DetectionEvent(
            location_id=self.loc.id,
            camera_id=self.cam1.id,
            event_type="workstation_active",
            occurred_at=t2,
            employee_id=self.emp1.id,
            workstation_zone_id=self.zone1.id,
            tracker_id="cam1_trk_1",
            confidence=1.0,
            metadata_json={"previous_state": "idle", "current_state": "active"},
        )
        self.db.add(ev_resume)
        self.db.flush()
        sess = process_presence_on_event(db=self.db, event=ev_resume, camera=self.cam1)
        self.assertEqual(sess.status, "active")
        self.assertEqual(sess.idle_seconds, 1000)  # 900 + 100
        self.assertEqual(sess.active_seconds, 0)

        # 4. Departure event at t0 + 1150s (active for 150s, then departed)
        t3 = t0 + timedelta(seconds=1150)
        ev_exit = DetectionEvent(
            location_id=self.loc.id,
            camera_id=self.cam1.id,
            event_type="workstation_idle",
            occurred_at=t3,
            employee_id=self.emp1.id,
            workstation_zone_id=self.zone1.id,
            tracker_id="cam1_trk_1",
            confidence=1.0,
            metadata_json={"action": "exit", "is_departure": True, "total_duration_seconds": 1150.0},
        )
        self.db.add(ev_exit)
        self.db.flush()
        sess = process_presence_on_event(db=self.db, event=ev_exit, camera=self.cam1)
        self.assertEqual(sess.status, "closed")
        self.assertEqual(sess.ended_at, t3)
        self.assertEqual(sess.active_seconds, 150)
        self.assertEqual(sess.idle_seconds, 1000)
        # Total duration = 1150s
        self.assertEqual(sess.active_seconds + sess.idle_seconds, 1150)

    def test_07_duration_protection_against_negative_and_out_of_order(self):
        """7. Out-of-order events do not produce negative durations or regress last_seen_at."""
        t0 = datetime(2026, 11, 17, 10, 0, 0, tzinfo=timezone.utc)
        sess = PresenceSession(
            employee_id=self.emp1.id,
            location_id=self.loc.id,
            entry_camera_id=self.cam1.id,
            workstation_zone_id=self.zone1.id,
            session_type="workstation",
            status="active",
            started_at=t0,
            last_seen_at=t0 + timedelta(seconds=500),
            active_seconds=500,
            idle_seconds=0,
        )
        self.db.add(sess)
        self.db.commit()

        # Delayed event arriving with timestamp earlier than last_seen_at
        past_time = t0 + timedelta(seconds=200)
        _accumulate_workstation_duration(sess, past_time, "workstation_active", {})

        # Durations must remain unchanged
        self.assertEqual(sess.active_seconds, 500)
        self.assertEqual(sess.idle_seconds, 0)
        self.assertEqual(sess.last_seen_at, t0 + timedelta(seconds=500))

    # -------------------------------------------------------------------------
    # 4. Edge Restart and Stale Session Reconciliation Tests
    # -------------------------------------------------------------------------

    def test_08_edge_restart_handling(self):
        """8. Edge restart with existing open session updates last_seen_at without duplicate insert."""
        now = datetime.now(timezone.utc)

        # Existing session from prior Edge run
        existing = PresenceSession(
            employee_id=self.emp1.id,
            location_id=self.loc.id,
            entry_camera_id=self.cam1.id,
            workstation_zone_id=self.zone1.id,
            session_type="workstation",
            status="active",
            started_at=now - timedelta(minutes=10),
            last_seen_at=now - timedelta(minutes=10),
            active_seconds=0,
            idle_seconds=0,
        )
        self.db.add(existing)
        self.db.commit()

        # Edge restarts and detects occupant again
        ev_restart = DetectionEvent(
            location_id=self.loc.id,
            camera_id=self.cam1.id,
            event_type="workstation_active",
            occurred_at=now,
            employee_id=self.emp1.id,
            workstation_zone_id=self.zone1.id,
            tracker_id="cam1_trk_1",
            confidence=0.95,
        )
        self.db.add(ev_restart)
        self.db.flush()

        res = process_presence_on_event(db=self.db, event=ev_restart, camera=self.cam1)
        self.assertEqual(res.id, existing.id)
        self.assertEqual(res.last_seen_at, now)
        self.assertIsNone(res.ended_at)

        # Verify only 1 session exists
        self.assertEqual(self.db.query(PresenceSession).filter(PresenceSession.location_id == self.loc.id).count(), 1)

    def test_09_stale_session_cleanup_offline_camera(self):
        """9. Reconciles open sessions when associated camera is offline beyond grace period."""
        now = datetime.now(timezone.utc)

        # Session last seen 200 seconds ago on Camera 1
        stale_sess = PresenceSession(
            employee_id=self.emp1.id,
            location_id=self.loc.id,
            entry_camera_id=self.cam1.id,
            workstation_zone_id=self.zone1.id,
            session_type="workstation",
            status="active",
            started_at=now - timedelta(seconds=500),
            last_seen_at=now - timedelta(seconds=200),
            active_seconds=300,
            idle_seconds=0,
        )
        self.db.add(stale_sess)

        # Camera 1 is marked offline
        self.cam1.connection_status = "offline"
        self.cam1.last_heartbeat_at = now - timedelta(seconds=200)
        self.db.commit()

        # Run reconciliation with 60s offline grace period
        closed = reconcile_stale_presence_sessions(
            db=self.db,
            max_stale_seconds=900.0,
            offline_camera_grace_seconds=60.0,
            location_id=self.loc.id,
            reference_time=now,
        )

        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0].id, stale_sess.id)
        self.assertEqual(closed[0].status, "closed")
        self.assertEqual(closed[0].ended_at, stale_sess.last_seen_at)

        # Run reconciliation again: MUST BE IDEMPOTENT (0 closed)
        closed_again = reconcile_stale_presence_sessions(
            db=self.db,
            location_id=self.loc.id,
            reference_time=now,
        )
        self.assertEqual(len(closed_again), 0)

    def test_10_stale_session_cleanup_respects_grace_period(self):
        """10. Does not close sessions during momentary camera drops within grace period."""
        now = datetime.now(timezone.utc)

        sess = PresenceSession(
            employee_id=self.emp1.id,
            location_id=self.loc.id,
            entry_camera_id=self.cam1.id,
            workstation_zone_id=self.zone1.id,
            session_type="workstation",
            status="active",
            started_at=now - timedelta(seconds=100),
            last_seen_at=now - timedelta(seconds=15),
            active_seconds=85,
            idle_seconds=0,
        )
        self.db.add(sess)

        # Camera dropped 15 seconds ago (< 60s grace period)
        self.cam1.connection_status = "offline"
        self.cam1.last_heartbeat_at = now - timedelta(seconds=15)
        self.db.commit()

        closed = reconcile_stale_presence_sessions(
            db=self.db,
            max_stale_seconds=900.0,
            offline_camera_grace_seconds=60.0,
            location_id=self.loc.id,
            reference_time=now,
        )
        self.assertEqual(len(closed), 0)
        self.assertIsNone(sess.ended_at)

    def test_11_duplicate_departure_handling(self):
        """11. Duplicate departure event on already-closed session is safely ignored."""
        now = datetime.now(timezone.utc)

        # Already closed session
        closed_sess = PresenceSession(
            employee_id=self.emp1.id,
            location_id=self.loc.id,
            entry_camera_id=self.cam1.id,
            workstation_zone_id=self.zone1.id,
            session_type="workstation",
            status="closed",
            started_at=now - timedelta(minutes=30),
            last_seen_at=now - timedelta(minutes=10),
            ended_at=now - timedelta(minutes=10),
            active_seconds=1200,
            idle_seconds=0,
        )
        self.db.add(closed_sess)
        self.db.commit()

        # Duplicate departure event arrives
        ev_dup_exit = DetectionEvent(
            location_id=self.loc.id,
            camera_id=self.cam1.id,
            event_type="workstation_idle",
            occurred_at=now - timedelta(minutes=10),
            employee_id=self.emp1.id,
            workstation_zone_id=self.zone1.id,
            tracker_id="cam1_trk_1",
            confidence=1.0,
            metadata_json={"action": "exit", "is_departure": True},
        )
        self.db.add(ev_dup_exit)
        self.db.flush()

        res = process_presence_on_event(db=self.db, event=ev_dup_exit, camera=self.cam1)
        self.assertIsNone(res)  # Gracefully returns None
        self.assertEqual(closed_sess.status, "closed")

    def test_12_multi_employee_isolation_in_same_zone(self):
        """12. Two employees in same workstation zone have fully independent PresenceSession lifecycles."""
        now = datetime.now(timezone.utc)

        # Emp 1 and Emp 2 enter zone 1
        ev1 = DetectionEvent(
            location_id=self.loc.id, camera_id=self.cam1.id, event_type="workstation_active",
            occurred_at=now, employee_id=self.emp1.id, workstation_zone_id=self.zone1.id, tracker_id="cam1_trk_1", confidence=1.0
        )
        ev2 = DetectionEvent(
            location_id=self.loc.id, camera_id=self.cam1.id, event_type="workstation_active",
            occurred_at=now, employee_id=self.emp2.id, workstation_zone_id=self.zone1.id, tracker_id="cam1_trk_2", confidence=1.0
        )
        self.db.add_all([ev1, ev2])
        self.db.flush()

        s1 = process_presence_on_event(db=self.db, event=ev1, camera=self.cam1)
        s2 = process_presence_on_event(db=self.db, event=ev2, camera=self.cam1)

        self.assertIsNotNone(s1)
        self.assertIsNotNone(s2)
        self.assertNotEqual(s1.id, s2.id)

        # Emp 1 becomes idle after 300s
        t_idle = now + timedelta(seconds=300)
        ev1_idle = DetectionEvent(
            location_id=self.loc.id, camera_id=self.cam1.id, event_type="workstation_idle",
            occurred_at=t_idle, employee_id=self.emp1.id, workstation_zone_id=self.zone1.id, tracker_id="cam1_trk_1", confidence=1.0,
            metadata_json={"inactivity_duration_seconds": 300.0}
        )
        self.db.add(ev1_idle)
        self.db.flush()
        process_presence_on_event(db=self.db, event=ev1_idle, camera=self.cam1)

        self.assertEqual(s1.status, "idle")
        self.assertEqual(s2.status, "active")  # Emp 2 remains active!

        # Emp 1 departs after 400s
        t_exit = now + timedelta(seconds=400)
        ev1_exit = DetectionEvent(
            location_id=self.loc.id, camera_id=self.cam1.id, event_type="workstation_idle",
            occurred_at=t_exit, employee_id=self.emp1.id, workstation_zone_id=self.zone1.id, tracker_id="cam1_trk_1", confidence=1.0,
            metadata_json={"action": "exit", "is_departure": True}
        )
        self.db.add(ev1_exit)
        self.db.flush()
        process_presence_on_event(db=self.db, event=ev1_exit, camera=self.cam1)

        self.assertEqual(s1.status, "closed")
        self.assertEqual(s2.status, "active")  # Emp 2 STILL remains active!


if __name__ == "__main__":
    unittest.main()
