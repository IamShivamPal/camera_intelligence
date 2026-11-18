"""
Workstation Occupancy State Tracker & Event State Machine
Manages per-zone employee occupancy, multi-occupant tracking, occlusion handling,
inactivity state transitions, and dispatches workstation_active / workstation_idle
events strictly on state changes and departures.
"""

import logging
import threading
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Any
import numpy as np

from ai_engine.analytics.polygon import PolygonZone
from ai_engine.analytics.inactivity_detector import InactivityDetector
from ai_engine.client.event_client import DetectionPayload
from ai_engine.config import (
    DEFAULT_OCCLUSION_TOLERANCE_SECONDS,
    DEFAULT_CAMERA_DISCONNECT_GRACE_PERIOD_SECONDS,
)

logger = logging.getLogger(__name__)


class OccupancyState(str, Enum):
    VACANT = "vacant"
    ACTIVE = "active"
    IDLE = "idle"


@dataclass
class ZoneOccupancySession:
    """Current live occupancy session within a single workstation polygon."""
    zone_id: int
    camera_id: int
    location_id: int
    occupancy_state: OccupancyState = OccupancyState.VACANT
    employee_id: int | None = None
    stream_tracker_id: str | None = None
    is_employee_recognized: bool = False
    entry_time: float | None = None
    last_seen_time: float | None = None
    exit_time: float | None = None
    consecutive_missing_frames: int = 0
    detector: InactivityDetector = field(default_factory=InactivityDetector)
    last_event_type: str | None = None

    @property
    def total_duration_seconds(self) -> float:
        if self.entry_time is None:
            return 0.0
        end = self.exit_time or self.last_seen_time or time.time()
        return max(0.0, end - self.entry_time)


class ZoneOccupancyTracker:
    """
    Manages live occupancy and inactivity state transitions for a workstation zone.
    Supports multiple simultaneous occupants per zone (e.g. shared benches or meeting zones)
    while maintaining independent state machines, inactivity timers, and identities.

    Guarantees:
      1. Events (workstation_active, workstation_idle) fire ONLY on state transitions.
      2. Tracker IDs are ephemeral telemetry and never treated as employee identities.
      3. Unknown persons are never assigned employee IDs.
      4. Temporary occlusions do not prematurely reset or end sessions.
      5. Zone departure emits a departure event to allow the backend to close the PresenceSession.
    """

    def __init__(
        self,
        zone: PolygonZone,
        occlusion_tolerance_seconds: float = DEFAULT_OCCLUSION_TOLERANCE_SECONDS,
        emit_exit_events: bool = True,
    ):
        self.zone = zone
        self.occlusion_tolerance_seconds = occlusion_tolerance_seconds
        self.emit_exit_events = emit_exit_events
        self.occupants: dict[str, ZoneOccupancySession] = {}
        self._default_vacant_session = ZoneOccupancySession(
            zone_id=zone.zone_id,
            camera_id=zone.camera_id,
            location_id=zone.location_id,
        )

    @property
    def session(self) -> ZoneOccupancySession:
        """
        Backward compatibility: Returns the primary active/idle occupant session,
        or the most recently seen session, or the default vacant session.
        """
        for sess in self.occupants.values():
            if sess.occupancy_state in (OccupancyState.ACTIVE, OccupancyState.IDLE):
                return sess
        if self.occupants:
            return list(self.occupants.values())[-1]
        return self._default_vacant_session

    @session.setter
    def session(self, sess: ZoneOccupancySession):
        self._default_vacant_session = sess

    def update(
        self,
        frame_bgr: np.ndarray,
        persons_in_camera: list[Any],
        timestamp: float | None = None,
    ) -> list[DetectionPayload]:
        """
        Evaluate all person detections against this workstation zone polygon.
        Updates occupancy state for all occupants in this zone and produces transition events.
        """
        now = timestamp or time.time()
        h, w = frame_bgr.shape[:2]

        # 1. Identify all persons currently inside the zone polygon
        inside_persons = []
        for person in persons_in_camera:
            box = getattr(person, "box_xyxy", None)
            if box is None:
                continue
            if self.zone.contains_person_base(box, frame_width=w, frame_height=h):
                inside_persons.append(person)

        events: list[DetectionPayload] = []
        seen_keys: set[str] = set()

        # Process each person found inside the polygon
        for idx, person in enumerate(inside_persons):
            raw_tid = getattr(person, "tracker_id", None)
            ephemeral_tid = (
                f"cam{self.zone.camera_id}_trk_{raw_tid}" if raw_tid is not None else None
            )
            recognized_emp_id = getattr(person, "recognized_employee_id", None)
            is_recognized = recognized_emp_id is not None

            # Determine occupant key: match existing session by employee_id or tracker_id
            matched_key = None
            if recognized_emp_id is not None:
                emp_key = f"emp_{recognized_emp_id}"
                if emp_key in self.occupants:
                    matched_key = emp_key
                else:
                    # Check if an earlier tracker-based session now has this employee recognized
                    for k, s in self.occupants.items():
                        if s.stream_tracker_id == ephemeral_tid:
                            matched_key = k
                            break

            if matched_key is None and ephemeral_tid is not None:
                for k, s in self.occupants.items():
                    if s.stream_tracker_id == ephemeral_tid:
                        matched_key = k
                        break

            if matched_key is None:
                matched_key = f"emp_{recognized_emp_id}" if is_recognized else (ephemeral_tid or f"idx_{idx}")

            occ_key = matched_key
            seen_keys.add(occ_key)

            if occ_key not in self.occupants:
                self.occupants[occ_key] = ZoneOccupancySession(
                    zone_id=self.zone.zone_id,
                    camera_id=self.zone.camera_id,
                    location_id=self.zone.location_id,
                    occupancy_state=OccupancyState.VACANT,
                    employee_id=recognized_emp_id,
                    stream_tracker_id=ephemeral_tid,
                    is_employee_recognized=is_recognized,
                    detector=InactivityDetector(),
                )

            sess = self.occupants[occ_key]
            sess.consecutive_missing_frames = 0
            sess.last_seen_time = now
            sess.stream_tracker_id = ephemeral_tid

            # Update employee recognition if newly recognized during active tracking
            just_recognized = False
            if not sess.is_employee_recognized and is_recognized:
                sess.employee_id = recognized_emp_id
                sess.is_employee_recognized = True
                just_recognized = True
                if occ_key != f"emp_{recognized_emp_id}":
                    new_key = f"emp_{recognized_emp_id}"
                    self.occupants[new_key] = self.occupants.pop(occ_key)
                    occ_key = new_key
                    seen_keys.add(occ_key)

            # Inactivity detection on person crop
            crop = person.extract_crop(frame_bgr)
            is_active, mean_motion, idle_seconds = sess.detector.update(crop, timestamp=now)

            prev_state = sess.occupancy_state

            # Transition 1: VACANT -> ACTIVE (Entry)
            if prev_state == OccupancyState.VACANT:
                sess.entry_time = now
                sess.exit_time = None
                sess.occupancy_state = OccupancyState.ACTIVE
                sess.last_event_type = "workstation_active"

                meta = {
                    "previous_state": "vacant",
                    "current_state": "active",
                    "zone_code": self.zone.zone_code,
                    "zone_name": self.zone.name,
                    "occupant_type": "employee" if sess.is_employee_recognized else "unknown",
                    "motion_score": round(mean_motion, 3),
                }

                events.append(
                    DetectionPayload(
                        camera_id=self.zone.camera_id,
                        location_id=self.zone.location_id,
                        event_type="workstation_active",
                        confidence=getattr(person, "confidence", 1.0),
                        employee_id=sess.employee_id,
                        workstation_zone_id=self.zone.zone_id,
                        tracker_id=sess.stream_tracker_id,
                        metadata_json=meta,
                    )
                )
                logger.info(
                    "Workstation %s occupant %s entered -> ACTIVE (emp=%s, tracker=%s)",
                    self.zone.zone_code,
                    occ_key,
                    sess.employee_id,
                    sess.stream_tracker_id,
                )

            # Transition 1B: Late Face Recognition (Already ACTIVE/IDLE, now identity resolved)
            elif just_recognized and prev_state in (OccupancyState.ACTIVE, OccupancyState.IDLE):
                sess.last_event_type = "workstation_active"
                meta = {
                    "previous_state": "vacant",
                    "current_state": prev_state.value,
                    "action": "identity_resolved",
                    "identification_event": "late_recognition",
                    "zone_code": self.zone.zone_code,
                    "zone_name": self.zone.name,
                    "occupant_type": "employee",
                    "motion_score": round(mean_motion, 3),
                }
                events.append(
                    DetectionPayload(
                        camera_id=self.zone.camera_id,
                        location_id=self.zone.location_id,
                        event_type="workstation_active",
                        confidence=getattr(person, "confidence", 1.0),
                        employee_id=sess.employee_id,
                        workstation_zone_id=self.zone.zone_id,
                        tracker_id=sess.stream_tracker_id,
                        metadata_json=meta,
                    )
                )
                logger.info(
                    "Workstation %s occupant %s identity resolved -> ACTIVE (emp=%s, tracker=%s)",
                    self.zone.zone_code,
                    occ_key,
                    sess.employee_id,
                    sess.stream_tracker_id,
                )

            # Transition 2: ACTIVE -> IDLE (Threshold Exceeded)
            elif (
                prev_state == OccupancyState.ACTIVE
                and idle_seconds >= self.zone.inactivity_threshold_seconds
            ):
                sess.occupancy_state = OccupancyState.IDLE
                sess.last_event_type = "workstation_idle"

                meta = {
                    "previous_state": "active",
                    "current_state": "idle",
                    "zone_code": self.zone.zone_code,
                    "zone_name": self.zone.name,
                    "inactivity_duration_seconds": round(idle_seconds, 1),
                    "inactivity_threshold_seconds": self.zone.inactivity_threshold_seconds,
                    "motion_score": round(mean_motion, 3),
                }

                events.append(
                    DetectionPayload(
                        camera_id=self.zone.camera_id,
                        location_id=self.zone.location_id,
                        event_type="workstation_idle",
                        confidence=getattr(person, "confidence", 1.0),
                        employee_id=sess.employee_id,
                        workstation_zone_id=self.zone.zone_id,
                        tracker_id=sess.stream_tracker_id,
                        metadata_json=meta,
                    )
                )
                logger.info(
                    "Workstation %s occupant %s became IDLE after %.1fs inactivity",
                    self.zone.zone_code,
                    occ_key,
                    idle_seconds,
                )

            # Transition 3: IDLE -> ACTIVE (Meaningful Movement Resumed)
            elif prev_state == OccupancyState.IDLE and is_active:
                sess.occupancy_state = OccupancyState.ACTIVE
                sess.last_event_type = "workstation_active"

                meta = {
                    "previous_state": "idle",
                    "current_state": "active",
                    "zone_code": self.zone.zone_code,
                    "zone_name": self.zone.name,
                    "resume_motion_score": round(mean_motion, 3),
                }

                events.append(
                    DetectionPayload(
                        camera_id=self.zone.camera_id,
                        location_id=self.zone.location_id,
                        event_type="workstation_active",
                        confidence=getattr(person, "confidence", 1.0),
                        employee_id=sess.employee_id,
                        workstation_zone_id=self.zone.zone_id,
                        tracker_id=sess.stream_tracker_id,
                        metadata_json=meta,
                    )
                )
                logger.info(
                    "Workstation %s occupant %s resumed activity -> ACTIVE (motion=%.2f)",
                    self.zone.zone_code,
                    occ_key,
                    mean_motion,
                )

        # 2. Check for missing occupants (occlusion handling and departure)
        for occ_key, sess in list(self.occupants.items()):
            if occ_key not in seen_keys:
                if sess.occupancy_state != OccupancyState.VACANT:
                    sess.consecutive_missing_frames += 1
                    time_missing = (
                        now - sess.last_seen_time
                        if sess.last_seen_time
                        else 0.0
                    )

                    # Occlusion tolerance window
                    if time_missing >= self.occlusion_tolerance_seconds:
                        sess.exit_time = sess.last_seen_time
                        prev_st = sess.occupancy_state
                        sess.occupancy_state = OccupancyState.VACANT
                        sess.detector.reset()

                        # Emit departure event to close backend PresenceSession
                        if self.emit_exit_events:
                            meta = {
                                "previous_state": prev_st.value,
                                "current_state": "vacant",
                                "action": "exit",
                                "is_departure": True,
                                "zone_code": self.zone.zone_code,
                                "zone_name": self.zone.name,
                                "total_duration_seconds": round(sess.total_duration_seconds, 1),
                            }
                            events.append(
                                DetectionPayload(
                                    camera_id=self.zone.camera_id,
                                    location_id=self.zone.location_id,
                                    event_type="workstation_idle",
                                    confidence=1.0,
                                    employee_id=sess.employee_id,
                                    workstation_zone_id=self.zone.zone_id,
                                    tracker_id=sess.stream_tracker_id,
                                    metadata_json=meta,
                                )
                            )

                        logger.info(
                            "Workstation %s occupant %s departed -> VACANT (duration=%.1fs)",
                            self.zone.zone_code,
                            occ_key,
                            sess.total_duration_seconds,
                        )
                        self._default_vacant_session = sess

        return events

    def reset(self, emit_exit_events: bool = False, timestamp: float | None = None) -> list[DetectionPayload]:
        """Reset the zone to clean vacant state (e.g. on camera reset or disconnect)."""
        now = timestamp or time.time()
        events = []
        if emit_exit_events:
            for occ_key, sess in self.occupants.items():
                if sess.occupancy_state in (OccupancyState.ACTIVE, OccupancyState.IDLE):
                    sess.exit_time = sess.last_seen_time or now
                    prev_st = sess.occupancy_state.value
                    sess.occupancy_state = OccupancyState.VACANT
                    sess.detector.reset()
                    events.append(
                        DetectionPayload(
                            camera_id=self.zone.camera_id,
                            location_id=self.zone.location_id,
                            event_type="workstation_idle",
                            confidence=1.0,
                            employee_id=sess.employee_id,
                            workstation_zone_id=self.zone.zone_id,
                            tracker_id=sess.stream_tracker_id,
                            metadata_json={
                                "previous_state": prev_st,
                                "current_state": "vacant",
                                "action": "exit",
                                "is_departure": True,
                                "reason": "camera_disconnect",
                                "zone_code": self.zone.zone_code,
                                "zone_name": self.zone.name,
                                "total_duration_seconds": round(sess.total_duration_seconds, 1),
                            },
                        )
                    )
        self.occupants.clear()
        self._default_vacant_session = ZoneOccupancySession(
            zone_id=self.zone.zone_id,
            camera_id=self.zone.camera_id,
            location_id=self.zone.location_id,
        )
        return events


class MultiZoneManager:
    """
    Orchestrates multiple workstation zones across multiple cameras.
    - Manages zone registries per camera ID.
    - Prevents duplicate sessions when an employee shifts between zones.
    - Handles camera disconnections, reconnect grace periods, and safe state cleanup.
    """

    def __init__(
        self,
        occlusion_tolerance_seconds: float = DEFAULT_OCCLUSION_TOLERANCE_SECONDS,
        disconnect_grace_period_seconds: float = DEFAULT_CAMERA_DISCONNECT_GRACE_PERIOD_SECONDS,
    ):
        self.occlusion_tolerance_seconds = occlusion_tolerance_seconds
        self.disconnect_grace_period_seconds = disconnect_grace_period_seconds
        # {camera_id: {zone_id: ZoneOccupancyTracker}}
        self._camera_zones: dict[int, dict[int, ZoneOccupancyTracker]] = {}
        # Track disconnected cameras to manage grace periods and prevent duplicate resets
        self._disconnected_cameras: dict[int, float] = {}  # camera_id -> disconnect_timestamp
        self._reset_cameras: set[int] = set()  # camera_id -> already reset
        self._lock = threading.RLock()

    def register_zone(self, zone: PolygonZone, emit_exit_events: bool = True):
        """Add or update a workstation zone for monitoring."""
        if zone.camera_id not in self._camera_zones:
            self._camera_zones[zone.camera_id] = {}

        tracker = ZoneOccupancyTracker(
            zone=zone,
            occlusion_tolerance_seconds=self.occlusion_tolerance_seconds,
            emit_exit_events=emit_exit_events,
        )
        self._camera_zones[zone.camera_id][zone.zone_id] = tracker
        logger.info(
            "Registered workstation zone '%s' (ID %d) on Camera ID %d",
            zone.zone_code,
            zone.zone_id,
            zone.camera_id,
        )

    def unregister_zone(self, camera_id: int, zone_id: int) -> bool:
        """Remove a zone from monitoring."""
        if camera_id in self._camera_zones:
            return self._camera_zones[camera_id].pop(zone_id, None) is not None
        return False

    def get_zones_for_camera(self, camera_id: int) -> list[PolygonZone]:
        """List all active zones registered under a camera."""
        if camera_id in self._camera_zones:
            return [t.zone for t in self._camera_zones[camera_id].values()]
        return []

    def get_zone_tracker(self, camera_id: int, zone_id: int) -> ZoneOccupancyTracker | None:
        """Get live tracker for a specific zone."""
        if camera_id in self._camera_zones:
            return self._camera_zones[camera_id].get(zone_id)
        return None

    def process_frame(
        self,
        camera_id: int,
        frame_bgr: np.ndarray,
        persons: list[Any],
        timestamp: float | None = None,
    ) -> list[DetectionPayload]:
        """
        Process a camera frame across all its workstation zones.
        Returns all generated state transition and departure events.
        """
        now = timestamp or time.time()
        trackers = self._camera_zones.get(camera_id, {})
        if not trackers:
            return []

        all_events: list[DetectionPayload] = []
        for zone_id, tracker in trackers.items():
            if not tracker.zone.is_active:
                continue
            evs = tracker.update(
                frame_bgr=frame_bgr,
                persons_in_camera=persons,
                timestamp=now,
            )
            all_events.extend(evs)

        return all_events

    def reset_camera(
        self,
        camera_id: int,
        emit_exit_events: bool = False,
        timestamp: float | None = None,
    ) -> list[DetectionPayload]:
        """
        Reset all zone sessions for a specific camera (e.g. on stream reconnect or disconnect).
        Guarantees that other cameras' occupancy states are completely preserved.
        """
        now = timestamp or time.time()
        with self._lock:
            trackers = self._camera_zones.get(camera_id, {})
            all_events = []
            for tracker in trackers.values():
                evs = tracker.reset(emit_exit_events=emit_exit_events, timestamp=now)
                all_events.extend(evs)
            self._reset_cameras.add(camera_id)
            return all_events

    def handle_camera_disconnect(
        self,
        camera_id: int,
        timestamp: float | None = None,
        immediate: bool = False,
    ) -> list[DetectionPayload]:
        """
        Record camera disconnection.
        If immediate=True or (now - disconnect_time) >= disconnect_grace_period_seconds,
        safely invokes reset_camera(camera_id, emit_exit_events=True) and returns departures.
        Idempotent: prevents duplicate departure events if called repeatedly.
        """
        now = timestamp or time.time()
        with self._lock:
            if camera_id not in self._disconnected_cameras:
                self._disconnected_cameras[camera_id] = now

            disc_time = self._disconnected_cameras[camera_id]
            if immediate or (now - disc_time) >= self.disconnect_grace_period_seconds:
                if camera_id not in self._reset_cameras:
                    return self.reset_camera(camera_id, emit_exit_events=True, timestamp=now)
        return []

    def handle_camera_reconnect(self, camera_id: int):
        """Clear disconnected state when camera resumes streaming online."""
        with self._lock:
            self._disconnected_cameras.pop(camera_id, None)
            self._reset_cameras.discard(camera_id)

    def get_all_occupancy_summaries(self) -> list[dict[str, Any]]:
        """Return human-readable diagnostic summaries for all monitored zones."""
        summaries = []
        for cam_id, zdict in self._camera_zones.items():
            for zid, tracker in zdict.items():
                if tracker.occupants:
                    for ok, sess in tracker.occupants.items():
                        summaries.append({
                            "camera_id": cam_id,
                            "zone_id": zid,
                            "zone_code": tracker.zone.zone_code,
                            "occupant_key": ok,
                            "state": sess.occupancy_state.value,
                            "employee_id": sess.employee_id,
                            "stream_tracker_id": sess.stream_tracker_id,
                            "duration_seconds": round(sess.total_duration_seconds, 1),
                            "idle_seconds": round(sess.detector.accumulated_idle_seconds, 1),
                        })
                else:
                    summaries.append({
                        "camera_id": cam_id,
                        "zone_id": zid,
                        "zone_code": tracker.zone.zone_code,
                        "occupant_key": None,
                        "state": OccupancyState.VACANT.value,
                        "employee_id": None,
                        "stream_tracker_id": None,
                        "duration_seconds": 0.0,
                        "idle_seconds": 0.0,
                    })
        return summaries
