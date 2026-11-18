"""
Automated Test Suite for Workstation Polygon Containment & Inactivity Detection
Phase 3, Task 2 Verification

Covers:
1. Point Inside Polygon (Ray-Casting Algorithm)
2. Point Outside Polygon
3. Polygon Boundary Edge Cases
4. Normalized Coordinate Conversion to Pixel Space
5. Person Bounding Box Bottom-Center Base Containment
6. Optical Flow Motion Energy & Inactivity Detection
7. Employee Occupancy Start and End Lifecycle
8. Inactivity Threshold Transition (workstation_idle)
9. Meaningful Movement Resetting Inactivity (idle -> active)
10. Occlusion & Temporary Detection Loss Tolerance Window
11. Duplicate Event Prevention (Transition-Driven Only)
12. Unknown Person Handling (No Fake Employee IDs Assigned)
13. Multiple Workstation Zones per Camera & Zone Switching
14. Camera Disconnection and State Reset
15. Backend Event Payload Schema Alignment
16. Live Pipeline Worker Integration with Workstation Analytics
"""

import sys
import time
import unittest
from pathlib import Path
import cv2
import numpy as np

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_engine.analytics.polygon import PolygonZone, ray_casting_contains_point
from ai_engine.analytics.inactivity_detector import InactivityDetector
from ai_engine.analytics.occupancy_tracker import (
    OccupancyState,
    ZoneOccupancyTracker,
    MultiZoneManager,
)
from ai_engine.pipeline.detector import TrackedPerson
from ai_engine.client.event_client import BackendEventClient, DetectionPayload


class TestWorkstationInactivity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Sample normalized polygon (rectangle: [0.2, 0.2] to [0.8, 0.8])
        cls.rect_points = [
            (0.2, 0.2),
            (0.8, 0.2),
            (0.8, 0.8),
            (0.2, 0.8),
        ]
        cls.frame_w = 1000
        cls.frame_h = 1000

    # -------------------------------------------------------------------------
    # 1. Polygon Containment & Coordinate Mapping Tests
    # -------------------------------------------------------------------------

    def test_01_point_inside_polygon(self):
        """1. Ray-Casting algorithm correctly identifies points inside convex & concave polygons."""
        # Convex rectangle
        self.assertTrue(ray_casting_contains_point((0.5, 0.5), self.rect_points))
        self.assertTrue(ray_casting_contains_point((0.3, 0.3), self.rect_points))

        # Concave L-shaped polygon
        l_shape = [
            (0.0, 0.0),
            (0.4, 0.0),
            (0.4, 0.2),
            (0.2, 0.2),
            (0.2, 0.4),
            (0.0, 0.4),
        ]
        # Inside the L
        self.assertTrue(ray_casting_contains_point((0.1, 0.1), l_shape))
        self.assertTrue(ray_casting_contains_point((0.1, 0.3), l_shape))
        self.assertTrue(ray_casting_contains_point((0.3, 0.1), l_shape))
        # Inside the cutout (outside polygon)
        self.assertFalse(ray_casting_contains_point((0.3, 0.3), l_shape))

    def test_02_point_outside_polygon(self):
        """2. Points outside the polygon are correctly identified as False."""
        self.assertFalse(ray_casting_contains_point((0.1, 0.5), self.rect_points))
        self.assertFalse(ray_casting_contains_point((0.9, 0.5), self.rect_points))
        self.assertFalse(ray_casting_contains_point((0.5, 0.1), self.rect_points))
        self.assertFalse(ray_casting_contains_point((0.5, 0.9), self.rect_points))

    def test_03_polygon_boundary(self):
        """3. Points on polygon boundary edges are inclusive when requested."""
        # Point directly on top edge (0.5, 0.2)
        on_edge = (0.5, 0.2)
        self.assertTrue(ray_casting_contains_point(on_edge, self.rect_points, boundary_inclusive=True))
        self.assertFalse(ray_casting_contains_point(on_edge, self.rect_points, boundary_inclusive=False))

        # Point directly on corner vertex (0.2, 0.2)
        corner = (0.2, 0.2)
        self.assertTrue(ray_casting_contains_point(corner, self.rect_points, boundary_inclusive=True))

    def test_04_normalized_coordinate_conversion(self):
        """4. Normalized [0.0, 1.0] coordinates convert accurately into frame pixel space."""
        zone = PolygonZone(
            zone_id=1,
            zone_code="ZONE-TEST-01",
            name="Desk 1",
            camera_id=10,
            location_id=1,
            polygon_points=self.rect_points,
            inactivity_threshold_seconds=60.0,
        )

        pixel_pts = zone.to_pixel_points(frame_width=1000, frame_height=500)
        expected = [(200.0, 100.0), (800.0, 100.0), (800.0, 400.0), (200.0, 400.0)]
        self.assertEqual(pixel_pts, expected)

        cv_pts = zone.to_cv2_points(frame_width=1000, frame_height=500)
        self.assertEqual(cv_pts.shape, (4, 1, 2))
        self.assertEqual(cv_pts.dtype, np.int32)

        # Bounding box
        bbox = zone.get_pixel_bounding_box(frame_width=1000, frame_height=500)
        self.assertEqual(bbox, (200, 100, 800, 400))

    def test_05_contains_person_base(self):
        """5. Zone checks person containment using bottom-center contact point ((x1+x2)/2, y2)."""
        zone = PolygonZone(
            zone_id=1,
            zone_code="ZONE-TEST-01",
            name="Desk 1",
            camera_id=10,
            location_id=1,
            polygon_points=self.rect_points,  # [200, 200] to [800, 800] in 1000x1000
        )

        # Person A: Base at x=(400+600)/2=500, y=600 -> Inside
        box_inside = (400.0, 300.0, 600.0, 600.0)
        self.assertTrue(zone.contains_person_base(box_inside, 1000, 1000))

        # Person B: Base at x=(100+300)/2=200, y=900 -> y=900 is outside polygon
        box_outside = (100.0, 700.0, 300.0, 900.0)
        self.assertFalse(zone.contains_person_base(box_outside, 1000, 1000))

    # -------------------------------------------------------------------------
    # 2. Inactivity & Optical Flow Detection Tests
    # -------------------------------------------------------------------------

    def test_06_inactivity_optical_flow_motion_energy(self):
        """6. Inactivity detector measures optical flow displacement between static vs moving frames."""
        detector = InactivityDetector(motion_threshold=0.8, diff_threshold=2.5)

        # Frame 1: Base image
        f1 = np.full((128, 128, 3), 120, dtype=np.uint8)
        # Frame 2: Identical (Static)
        f2 = np.full((128, 128, 3), 120, dtype=np.uint8)
        # Frame 3: Moved / Modified
        f3 = f1.copy()
        cv2.rectangle(f3, (20, 20), (108, 108), (255, 255, 255), -1)

        # Update with f1 (init)
        is_act, mag, idle = detector.update(f1, timestamp=100.0)
        self.assertTrue(is_act)
        self.assertEqual(idle, 0.0)

        # Update with f2 (static, dt=1.0s)
        is_act, mag, idle = detector.update(f2, timestamp=101.0)
        self.assertFalse(is_act)
        self.assertLess(mag, 0.5)
        self.assertAlmostEqual(idle, 1.0, places=2)

        # Update with f2 again (static, dt=2.0s)
        is_act, mag, idle = detector.update(f2, timestamp=103.0)
        self.assertFalse(is_act)
        self.assertAlmostEqual(idle, 3.0, places=2)

        # Update with f3 (movement occurred)
        is_act, mag, idle = detector.update(f3, timestamp=104.0)
        self.assertTrue(is_act)
        self.assertGreater(mag, 0.7)
        self.assertEqual(idle, 0.0)  # Reset on movement

    # -------------------------------------------------------------------------
    # 3. Workstation Occupancy & State Transition Tests
    # -------------------------------------------------------------------------

    def test_07_employee_occupancy_start_and_end(self):
        """7. Occupant entry generates workstation_active; departure sets vacant after tolerance."""
        zone = PolygonZone(
            zone_id=1,
            zone_code="ZONE-01",
            name="Zone 1",
            camera_id=10,
            location_id=1,
            polygon_points=self.rect_points,
            inactivity_threshold_seconds=10.0,
        )
        tracker = ZoneOccupancyTracker(zone=zone, occlusion_tolerance_seconds=2.0)
        frame = np.zeros((1000, 1000, 3), dtype=np.uint8)

        # Person inside with recognized employee ID
        p1 = TrackedPerson(
            x1=400.0, y1=300.0, x2=600.0, y2=600.0,
            confidence=0.95, tracker_id=5, recognized_employee_id=101,
        )

        # Frame 1: Person enters
        events = tracker.update(frame, [p1], timestamp=100.0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "workstation_active")
        self.assertEqual(events[0].employee_id, 101)
        self.assertEqual(events[0].workstation_zone_id, 1)
        self.assertEqual(tracker.session.occupancy_state, OccupancyState.ACTIVE)

        # Frame 2: Person remains inside (no duplicate event)
        events2 = tracker.update(frame, [p1], timestamp=101.0)
        self.assertEqual(len(events2), 0)
        self.assertEqual(tracker.session.occupancy_state, OccupancyState.ACTIVE)

        # Frame 3: Person leaves (empty list of persons) at t=102.0
        events3 = tracker.update(frame, [], timestamp=102.0)
        self.assertEqual(len(events3), 0)
        # Within occlusion tolerance (2.0s), still active
        self.assertEqual(tracker.session.occupancy_state, OccupancyState.ACTIVE)

        # Frame 4: Person still missing at t=104.5 (> 2.0s tolerance)
        events4 = tracker.update(frame, [], timestamp=104.5)
        self.assertEqual(len(events4), 1)
        self.assertEqual(events4[0].event_type, "workstation_idle")
        self.assertEqual(events4[0].metadata_json["action"], "exit")
        self.assertEqual(events4[0].metadata_json["current_state"], "vacant")
        self.assertTrue(events4[0].metadata_json["is_departure"])
        self.assertEqual(tracker.session.occupancy_state, OccupancyState.VACANT)
        self.assertAlmostEqual(tracker.session.total_duration_seconds, 1.0, places=1)

    def test_08_inactivity_threshold_triggers_workstation_idle(self):
        """8. Prolonged inactivity beyond threshold triggers workstation_idle event."""
        zone = PolygonZone(
            zone_id=2,
            zone_code="ZONE-02",
            name="Zone 2",
            camera_id=10,
            location_id=1,
            polygon_points=self.rect_points,
            inactivity_threshold_seconds=5.0,  # 5 seconds threshold
        )
        tracker = ZoneOccupancyTracker(zone=zone)

        # Static frame (no motion)
        static_frame = np.full((1000, 1000, 3), 150, dtype=np.uint8)
        p1 = TrackedPerson(
            x1=400.0, y1=300.0, x2=600.0, y2=600.0,
            confidence=0.90, tracker_id=7, recognized_employee_id=102,
        )

        # t=0: Entry -> workstation_active
        evs0 = tracker.update(static_frame, [p1], timestamp=100.0)
        self.assertEqual(len(evs0), 1)
        self.assertEqual(evs0[0].event_type, "workstation_active")

        # t=3s: Still active, idle=3s (< 5s threshold)
        evs1 = tracker.update(static_frame, [p1], timestamp=103.0)
        self.assertEqual(len(evs1), 0)
        self.assertEqual(tracker.session.occupancy_state, OccupancyState.ACTIVE)

        # t=6s: Inactivity threshold exceeded (idle=6s >= 5s) -> workstation_idle
        evs2 = tracker.update(static_frame, [p1], timestamp=106.0)
        self.assertEqual(len(evs2), 1)
        self.assertEqual(evs2[0].event_type, "workstation_idle")
        self.assertEqual(evs2[0].employee_id, 102)
        self.assertEqual(tracker.session.occupancy_state, OccupancyState.IDLE)

        # t=8s: Still idle, no duplicate event
        evs3 = tracker.update(static_frame, [p1], timestamp=108.0)
        self.assertEqual(len(evs3), 0)
        self.assertEqual(tracker.session.occupancy_state, OccupancyState.IDLE)

    def test_09_meaningful_movement_resets_inactivity(self):
        """9. When occupant is IDLE, meaningful movement triggers workstation_active."""
        zone = PolygonZone(
            zone_id=2,
            zone_code="ZONE-02",
            name="Zone 2",
            camera_id=10,
            location_id=1,
            polygon_points=self.rect_points,
            inactivity_threshold_seconds=2.0,
        )
        tracker = ZoneOccupancyTracker(zone=zone)

        static_f = np.full((1000, 1000, 3), 100, dtype=np.uint8)
        p1 = TrackedPerson(
            x1=400.0, y1=300.0, x2=600.0, y2=600.0,
            confidence=0.92, tracker_id=8, recognized_employee_id=103,
        )

        # t=100: Entry
        tracker.update(static_f, [p1], timestamp=100.0)
        # t=103: Exceeds 2s threshold -> becomes IDLE
        evs_idle = tracker.update(static_f, [p1], timestamp=103.0)
        self.assertEqual(tracker.session.occupancy_state, OccupancyState.IDLE)
        self.assertEqual(evs_idle[0].event_type, "workstation_idle")

        # t=104: Movement occurs in crop
        moving_f = static_f.copy()
        cv2.circle(moving_f, (500, 450), 40, (255, 255, 255), -1)

        evs_resume = tracker.update(moving_f, [p1], timestamp=104.0)
        self.assertEqual(len(evs_resume), 1)
        self.assertEqual(evs_resume[0].event_type, "workstation_active")
        self.assertEqual(tracker.session.occupancy_state, OccupancyState.ACTIVE)
        self.assertEqual(tracker.session.detector.accumulated_idle_seconds, 0.0)

    def test_10_occlusion_tolerance_window(self):
        """10. Temporary occlusion (< tolerance) maintains session continuity; > tolerance resets."""
        zone = PolygonZone(
            zone_id=3,
            zone_code="ZONE-03",
            name="Zone 3",
            camera_id=10,
            location_id=1,
            polygon_points=self.rect_points,
            inactivity_threshold_seconds=30.0,
        )
        tracker = ZoneOccupancyTracker(zone=zone, occlusion_tolerance_seconds=3.0)
        frame = np.zeros((1000, 1000, 3), dtype=np.uint8)
        p1 = TrackedPerson(
            x1=400.0, y1=300.0, x2=600.0, y2=600.0,
            confidence=0.95, tracker_id=9, recognized_employee_id=104,
        )

        # t=10: Enter
        tracker.update(frame, [p1], timestamp=10.0)
        self.assertEqual(tracker.session.occupancy_state, OccupancyState.ACTIVE)

        # t=11: Person briefly occluded (missing for 1.0s)
        tracker.update(frame, [], timestamp=11.0)
        self.assertEqual(tracker.session.occupancy_state, OccupancyState.ACTIVE)

        # t=12: Person reappears within 3.0s window -> continuous session
        evs = tracker.update(frame, [p1], timestamp=12.0)
        self.assertEqual(len(evs), 0)  # No new entry event, still same session
        self.assertEqual(tracker.session.occupancy_state, OccupancyState.ACTIVE)
        self.assertEqual(tracker.session.entry_time, 10.0)

        # t=16: Person missing for 4.0s (> 3.0s tolerance) -> VACANT
        tracker.update(frame, [], timestamp=16.0)
        self.assertEqual(tracker.session.occupancy_state, OccupancyState.VACANT)

    def test_11_duplicate_event_prevention(self):
        """11. Consecutive frames in the same state do not spam duplicate events."""
        zone = PolygonZone(
            zone_id=4,
            zone_code="ZONE-04",
            name="Zone 4",
            camera_id=10,
            location_id=1,
            polygon_points=self.rect_points,
            inactivity_threshold_seconds=5.0,
        )
        tracker = ZoneOccupancyTracker(zone=zone)
        frame = np.zeros((1000, 1000, 3), dtype=np.uint8)
        p1 = TrackedPerson(
            x1=400.0, y1=300.0, x2=600.0, y2=600.0,
            confidence=0.90, tracker_id=10, recognized_employee_id=105,
        )

        # 10 consecutive active frames
        total_events = 0
        for t in range(10):
            evs = tracker.update(frame, [p1], timestamp=100.0 + t * 0.1)
            total_events += len(evs)

        # Exactly 1 event (initial entry workstation_active), 0 duplicates
        self.assertEqual(total_events, 1)

    def test_12_unknown_person_handling(self):
        """12. Unknown persons trigger workstation events without being assigned employee IDs."""
        zone = PolygonZone(
            zone_id=5,
            zone_code="ZONE-05",
            name="Zone 5",
            camera_id=10,
            location_id=1,
            polygon_points=self.rect_points,
            inactivity_threshold_seconds=5.0,
        )
        tracker = ZoneOccupancyTracker(zone=zone)
        frame = np.zeros((1000, 1000, 3), dtype=np.uint8)

        # Person without recognized_employee_id (None)
        unknown_person = TrackedPerson(
            x1=400.0, y1=300.0, x2=600.0, y2=600.0,
            confidence=0.85, tracker_id=11, recognized_employee_id=None,
        )

        evs = tracker.update(frame, [unknown_person], timestamp=100.0)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0].event_type, "workstation_active")
        # Employee ID MUST be None
        self.assertIsNone(evs[0].employee_id)
        # Tracker ID passed as ephemeral telemetry metadata only
        self.assertEqual(evs[0].tracker_id, "cam10_trk_11")
        self.assertEqual(evs[0].metadata_json["occupant_type"], "unknown")

    # -------------------------------------------------------------------------
    # 4. Multi-Zone & Multi-Camera Management Tests
    # -------------------------------------------------------------------------

    def test_13_multiple_zones_per_camera(self):
        """13. MultiZoneManager supports multiple adjacent zones and employee zone movement."""
        mgr = MultiZoneManager(occlusion_tolerance_seconds=1.0)

        # Zone A: [0.1, 0.1] to [0.4, 0.8]
        zone_a = PolygonZone(
            zone_id=101,
            zone_code="DESK-A",
            name="Desk A",
            camera_id=1,
            location_id=1,
            polygon_points=[(0.1, 0.1), (0.4, 0.1), (0.4, 0.8), (0.1, 0.8)],
            inactivity_threshold_seconds=10.0,
        )
        # Zone B: [0.6, 0.1] to [0.9, 0.8]
        zone_b = PolygonZone(
            zone_id=102,
            zone_code="DESK-B",
            name="Desk B",
            camera_id=1,
            location_id=1,
            polygon_points=[(0.6, 0.1), (0.9, 0.1), (0.9, 0.8), (0.6, 0.8)],
            inactivity_threshold_seconds=10.0,
        )

        mgr.register_zone(zone_a)
        mgr.register_zone(zone_b)

        frame = np.zeros((1000, 1000, 3), dtype=np.uint8)

        # Step 1: Employee is at Desk A
        p_at_a = TrackedPerson(
            x1=200.0, y1=300.0, x2=300.0, y2=600.0,  # Base at (250, 600) -> in Desk A
            confidence=0.92, tracker_id=20, recognized_employee_id=201,
        )
        evs1 = mgr.process_frame(camera_id=1, frame_bgr=frame, persons=[p_at_a], timestamp=10.0)
        self.assertEqual(len(evs1), 1)
        self.assertEqual(evs1[0].workstation_zone_id, 101)
        self.assertEqual(evs1[0].event_type, "workstation_active")

        # Desk B remains vacant
        tracker_b = mgr.get_zone_tracker(1, 102)
        self.assertEqual(tracker_b.session.occupancy_state, OccupancyState.VACANT)

        # Step 2: Employee moves from Desk A to Desk B
        p_at_b = TrackedPerson(
            x1=700.0, y1=300.0, x2=800.0, y2=600.0,  # Base at (750, 600) -> in Desk B
            confidence=0.92, tracker_id=20, recognized_employee_id=201,
        )
        evs2 = mgr.process_frame(camera_id=1, frame_bgr=frame, persons=[p_at_b], timestamp=11.5)
        # 2 events: Desk B active entry + Desk A departure exit event
        self.assertEqual(len(evs2), 2)
        event_types = {e.event_type for e in evs2}
        self.assertIn("workstation_active", event_types)
        self.assertIn("workstation_idle", event_types)

        # After tolerance window, Desk A becomes vacant
        tracker_a = mgr.get_zone_tracker(1, 101)
        self.assertEqual(tracker_a.session.occupancy_state, OccupancyState.VACANT)
        self.assertEqual(tracker_b.session.occupancy_state, OccupancyState.ACTIVE)

    def test_14_camera_disconnection_and_reset(self):
        """14. Resetting a camera clears active zone state cleanly."""
        mgr = MultiZoneManager()
        zone = PolygonZone(
            zone_id=105,
            zone_code="DESK-C",
            name="Desk C",
            camera_id=2,
            location_id=1,
            polygon_points=self.rect_points,
        )
        mgr.register_zone(zone)

        frame = np.zeros((1000, 1000, 3), dtype=np.uint8)
        p1 = TrackedPerson(
            x1=400.0, y1=300.0, x2=600.0, y2=600.0,
            confidence=0.90, tracker_id=22, recognized_employee_id=202,
        )
        mgr.process_frame(camera_id=2, frame_bgr=frame, persons=[p1], timestamp=10.0)

        tracker = mgr.get_zone_tracker(2, 105)
        self.assertEqual(tracker.session.occupancy_state, OccupancyState.ACTIVE)

        # Camera disconnect / reset
        mgr.reset_camera(camera_id=2)
        self.assertEqual(tracker.session.occupancy_state, OccupancyState.VACANT)
        self.assertIsNone(tracker.session.entry_time)

    # -------------------------------------------------------------------------
    # 5. Backend Event Schema Alignment & Integration
    # -------------------------------------------------------------------------

    def test_15_backend_event_payload_validation(self):
        """15. Generated workstation events adhere strictly to DetectionEventCreate constraints."""
        zone = PolygonZone(
            zone_id=110,
            zone_code="DESK-SCHEMA",
            name="Schema Test Desk",
            camera_id=5,
            location_id=2,
            polygon_points=self.rect_points,
            inactivity_threshold_seconds=1.0,
        )
        tracker = ZoneOccupancyTracker(zone=zone)
        frame = np.full((1000, 1000, 3), 128, dtype=np.uint8)
        p1 = TrackedPerson(
            x1=400.0, y1=300.0, x2=600.0, y2=600.0,
            confidence=0.96, tracker_id=30, recognized_employee_id=301,
        )

        # 1. workstation_active payload
        evs_active = tracker.update(frame, [p1], timestamp=10.0)
        p_act = evs_active[0]
        self.assertEqual(p_act.event_type, "workstation_active")
        self.assertEqual(p_act.camera_id, 5)
        self.assertEqual(p_act.location_id, 2)
        self.assertEqual(p_act.employee_id, 301)
        self.assertEqual(p_act.workstation_zone_id, 110)
        self.assertTrue(0.0 <= p_act.confidence <= 1.0)
        self.assertIsNotNone(p_act.metadata_json)

        # Verify as dict (ready for JSON serialization)
        d_act = p_act.to_dict()
        self.assertEqual(d_act["event_type"], "workstation_active")
        self.assertNotIn("embedding", d_act)
        self.assertNotIn("raw_image", d_act)

        # 2. workstation_idle payload
        evs_idle = tracker.update(frame, [p1], timestamp=12.0)
        p_idle = evs_idle[0]
        self.assertEqual(p_idle.event_type, "workstation_idle")
        d_idle = p_idle.to_dict()
        self.assertEqual(d_idle["event_type"], "workstation_idle")
        self.assertIn("inactivity_duration_seconds", d_idle["metadata_json"])

    # -------------------------------------------------------------------------
    # 6. Multi-Occupancy & Lighting Invariance Tests
    # -------------------------------------------------------------------------

    def test_16_multiple_occupants_in_same_zone(self):
        """16. Zone tracks multiple simultaneous employees with independent state machines."""
        zone = PolygonZone(
            zone_id=201,
            zone_code="SHARED-DESK-01",
            name="Collaborative Bench",
            camera_id=1,
            location_id=1,
            polygon_points=self.rect_points,
            inactivity_threshold_seconds=10.0,
        )
        tracker = ZoneOccupancyTracker(zone=zone)
        frame = np.zeros((1000, 1000, 3), dtype=np.uint8)

        p1 = TrackedPerson(
            x1=300.0, y1=300.0, x2=450.0, y2=600.0,
            confidence=0.92, tracker_id=51, recognized_employee_id=101,
        )
        p2 = TrackedPerson(
            x1=550.0, y1=300.0, x2=700.0, y2=600.0,
            confidence=0.94, tracker_id=52, recognized_employee_id=102,
        )

        # Both enter at t=100.0
        events = tracker.update(frame, [p1, p2], timestamp=100.0)
        self.assertEqual(len(events), 2)
        emp_ids = {e.employee_id for e in events}
        self.assertEqual(emp_ids, {101, 102})
        self.assertTrue(all(e.event_type == "workstation_active" for e in events))

        # Check occupants map
        self.assertIn("emp_101", tracker.occupants)
        self.assertIn("emp_102", tracker.occupants)
        self.assertEqual(tracker.occupants["emp_101"].occupancy_state, OccupancyState.ACTIVE)
        self.assertEqual(tracker.occupants["emp_102"].occupancy_state, OccupancyState.ACTIVE)

    def test_17_multi_occupant_one_leaves_one_remains(self):
        """17. When one occupant leaves a shared zone, departure event fires only for that occupant."""
        zone = PolygonZone(
            zone_id=202,
            zone_code="SHARED-DESK-02",
            name="Shared Bench 2",
            camera_id=1,
            location_id=1,
            polygon_points=self.rect_points,
            inactivity_threshold_seconds=10.0,
        )
        tracker = ZoneOccupancyTracker(zone=zone, occlusion_tolerance_seconds=2.0)
        frame = np.zeros((1000, 1000, 3), dtype=np.uint8)

        p1 = TrackedPerson(
            x1=300.0, y1=300.0, x2=450.0, y2=600.0,
            confidence=0.90, tracker_id=61, recognized_employee_id=201,
        )
        p2 = TrackedPerson(
            x1=550.0, y1=300.0, x2=700.0, y2=600.0,
            confidence=0.95, tracker_id=62, recognized_employee_id=202,
        )

        # Both enter
        tracker.update(frame, [p1, p2], timestamp=100.0)

        # p1 leaves (only p2 visible) at t=101.0
        tracker.update(frame, [p2], timestamp=101.0)

        # t=103.5 (> 2.0s tolerance): p1 considered departed
        evs = tracker.update(frame, [p2], timestamp=103.5)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0].event_type, "workstation_idle")
        self.assertEqual(evs[0].employee_id, 201)
        self.assertEqual(evs[0].metadata_json["action"], "exit")
        self.assertTrue(evs[0].metadata_json["is_departure"])

        # p2 remains active
        self.assertEqual(tracker.occupants["emp_202"].occupancy_state, OccupancyState.ACTIVE)
        self.assertEqual(tracker.occupants["emp_201"].occupancy_state, OccupancyState.VACANT)

    def test_18_multi_occupant_one_idle_one_active(self):
        """18. One occupant becoming idle does not affect other active occupants in the same zone."""
        zone = PolygonZone(
            zone_id=203,
            zone_code="SHARED-DESK-03",
            name="Pair Desk",
            camera_id=1,
            location_id=1,
            polygon_points=self.rect_points,
            inactivity_threshold_seconds=3.0,
        )
        tracker = ZoneOccupancyTracker(zone=zone)

        # Frame 1: Initial entry
        f1 = np.full((1000, 1000, 3), 100, dtype=np.uint8)
        p1 = TrackedPerson(
            x1=300.0, y1=300.0, x2=450.0, y2=600.0,
            confidence=0.91, tracker_id=71, recognized_employee_id=301,
        )
        p2 = TrackedPerson(
            x1=550.0, y1=300.0, x2=700.0, y2=600.0,
            confidence=0.93, tracker_id=72, recognized_employee_id=302,
        )
        tracker.update(f1, [p1, p2], timestamp=100.0)

        # Frame 2: p1 moves (active typing), p2 stays static. dt=4.0s > 3.0s threshold
        f2 = f1.copy()
        cv2.circle(f2, (375, 450), 30, (255, 255, 255), -1)  # Motion inside p1's bbox only

        evs = tracker.update(f2, [p1, p2], timestamp=104.0)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0].event_type, "workstation_idle")
        self.assertEqual(evs[0].employee_id, 302)

        # Verify states
        self.assertEqual(tracker.occupants["emp_301"].occupancy_state, OccupancyState.ACTIVE)
        self.assertEqual(tracker.occupants["emp_302"].occupancy_state, OccupancyState.IDLE)

    def test_19_lighting_flicker_and_sensor_noise_rejection(self):
        """19. InactivityDetector rejects global lighting shifts and sensor noise, detecting only motion."""
        detector = InactivityDetector(motion_threshold=0.8, diff_threshold=2.5)

        base_gray = np.full((128, 128), 120, dtype=np.uint8)
        # 1. Init
        is_act, mag, idle = detector.update(base_gray, timestamp=10.0)
        self.assertTrue(is_act)

        # 2. Global lighting shift (+10 luminance across whole ROI)
        light_shifted = np.full((128, 128), 130, dtype=np.uint8)
        is_act, mag, idle = detector.update(light_shifted, timestamp=11.0)
        self.assertFalse(is_act)
        self.assertAlmostEqual(idle, 1.0, places=2)

        # 3. Camera sensor Gaussian noise (std=2.0)
        np.random.seed(42)
        noise = np.random.normal(0, 2.0, (128, 128))
        noisy_frame = np.clip(light_shifted.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        is_act, mag, idle = detector.update(noisy_frame, timestamp=12.0)
        self.assertFalse(is_act)
        self.assertAlmostEqual(idle, 2.0, places=2)

        # 4. Localized movement (typing in 25x25 patch)
        typing_frame = noisy_frame.copy()
        typing_frame[50:75, 50:75] = 230
        is_act, mag, idle = detector.update(typing_frame, timestamp=13.0)
        self.assertTrue(is_act)
        self.assertEqual(idle, 0.0)

    def test_20_presence_session_lifecycle_closure(self):
        """20. Backend process_presence_on_event correctly closes PresenceSession on departure."""
        import os
        import sys
        server_root = str(PROJECT_ROOT / "server")
        if server_root not in sys.path:
            sys.path.insert(0, server_root)
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        from unittest.mock import MagicMock
        from datetime import datetime, timezone
        from app.services.event_service import process_presence_on_event
        from app.models.detection_event import DetectionEvent
        from app.models.presence_session import PresenceSession

        db = MagicMock()
        camera = MagicMock(id=1, location_id=10)

        # 1. Existing open session
        open_ws = PresenceSession(
            id=77,
            employee_id=101,
            location_id=10,
            entry_camera_id=1,
            workstation_zone_id=5,
            session_type="workstation",
            status="active",
            started_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db.query.return_value.filter.return_value.first.return_value = open_ws

        # 2. Ingest departure event
        exit_event = DetectionEvent(
            id=300,
            location_id=10,
            camera_id=1,
            event_type="workstation_idle",
            employee_id=101,
            workstation_zone_id=5,
            occurred_at=datetime.now(timezone.utc),
            metadata_json={"action": "exit", "current_state": "vacant", "is_departure": True},
        )

        res = process_presence_on_event(db=db, event=exit_event, camera=camera)
        self.assertIsNotNone(res)
        self.assertEqual(res.status, "closed")
        self.assertEqual(res.ended_at, exit_event.occurred_at)
        self.assertEqual(exit_event.presence_session_id, 77)


if __name__ == "__main__":
    unittest.main()
