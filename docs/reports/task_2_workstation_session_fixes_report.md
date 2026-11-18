# Task 2 — Critical Workstation Session Lifecycle Fixes Report

**Project:** Camera Intelligence  
**Scope:** AI Engine Analytics, Edge Ingestion Pipeline, FastAPI Session Services, and PostgreSQL Ingestion  
**Status:** Successfully Implemented & Verified  
**Date:** November 2026  

---

## 1. Executive Summary

This report documents the implementation and verification of the four critical defects identified during the multi-employee occupancy tracking and workstation presence session audit ([`multi_employee_occupancy_session_audit.md`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/docs/reports/multi_employee_occupancy_session_audit.md)).

All four core deficiencies have been remediated, verified against genuine backend databases, and validated through an automated 12-scenario integration test suite without breaking existing API contracts or detection pipelines.

### Key Accomplishments
1. **Camera Disconnection & Grace Period Lifecycle:** Wired camera stream worker disconnections to `MultiZoneManager.reset_camera(camera_id, emit_exit_events=True)`. Integrated a configurable reconnect grace period (`DEFAULT_CAMERA_DISCONNECT_GRACE_PERIOD_SECONDS = 10.0s`). If a stream reconnects within the window, zone occupancy is preserved; if the drop persists, clean departure events (`reason: "camera_disconnect"`) are dispatched while completely isolating and preserving all other cameras' zone states.
2. **Late Face Recognition Integration:** When an occupant who entered anonymously has their identity verified on frame $N > 1$, `ZoneOccupancyTracker` detects identity resolution and emits a transition event `workstation_active` carrying `employee_id = sess.employee_id` and metadata `action: "identity_resolved"`. The backend receives this event and creates exactly one open `PresenceSession`. Subsequent recognized frames generate zero duplicate events.
3. **Active and Idle Duration Accumulation:** Implemented `_accumulate_workstation_duration` in `event_service.py`. Accurately accumulates `active_seconds` and `idle_seconds` across `ACTIVE -> IDLE -> ACTIVE -> Departure` cycles using optical flow metadata and server time deltas. Protects against negative durations and timestamp regressions from out-of-order deliveries.
4. **Stale Session Reconciliation:** Implemented `reconcile_stale_presence_sessions` in `event_service.py` and exposed the administrative endpoint `POST /api/v1/events/reconcile-sessions`. Automatically detects sessions on offline cameras or with missing heartbeats exceeding a grace threshold (`offline_camera_grace_seconds = 60.0s`), sets `ended_at = last_seen_at`, and closes sessions idempotently without creating phantom attendance time.
5. **Full Regression Passed:** Executed all 122 tests across the AI Engine, streaming, management, event, and lifecycle test suites with zero failures.

---

## 2. Modified and Created Files

| Component | File Path | Nature of Modification |
| :--- | :--- | :--- |
| **Configuration** | [`ai_engine/config.py`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/ai_engine/config.py) | Added `DEFAULT_CAMERA_DISCONNECT_GRACE_PERIOD_SECONDS = 10.0`. |
| **Occupancy Tracker** | [`ai_engine/analytics/occupancy_tracker.py`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/ai_engine/analytics/occupancy_tracker.py) | Added late face recognition event emission (`action: "identity_resolved"`), reentrant locking (`threading.RLock`), `handle_camera_disconnect()`, `handle_camera_reconnect()`, and camera isolation in `reset_camera()`. |
| **Stream Manager** | [`ai_engine/stream/stream_manager.py`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/ai_engine/stream/stream_manager.py) | Added multi-callback support (`_status_callbacks`, `add_status_callback`, `_dispatch_status_change`) so status events reach both heartbeat clients and disconnect handlers. |
| **Edge Ingestion Service** | [`ai_engine/service.py`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/ai_engine/service.py) | Added `_on_camera_status_change()`, `_trigger_camera_disconnect_reset()`, grace period timers, and clean departure flushes on service shutdown. |
| **Event Ingestion Service**| [`server/app/services/event_service.py`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/server/app/services/event_service.py) | Added `_accumulate_workstation_duration()`, updated `process_presence_on_event()` for duration accumulation and late recognition, and added `reconcile_stale_presence_sessions()`. |
| **Camera Service** | [`server/app/services/camera_service.py`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/server/app/services/camera_service.py) | Triggered automatic reconciliation when cameras report `offline` or `unknown` in heartbeat handlers. |
| **Event API Endpoint** | [`server/app/api/v1/endpoints/events.py`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/server/app/api/v1/endpoints/events.py) | Added administrative endpoint `POST /api/v1/events/reconcile-sessions`. |
| **Lifecycle Test Suite** | [`tests/test_workstation_session_lifecycle.py`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/tests/test_workstation_session_lifecycle.py) | Created comprehensive 12-scenario automated verification suite. |
| **Event API Test Suite** | [`tests/test_event_apis.py`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/tests/test_event_apis.py) | Added endpoint test `test_17_reconcile_sessions_endpoint`. |

---

## 3. Implementation Details

```mermaid
flowchart TD
    subgraph AI_Engine["AI Engine (Edge Deployment)"]
        StreamWorker["RTSP Worker / Stream Monitor"]
        StatusCB["StreamManager._dispatch_status_change()"]
        TimerMgr["EdgeIngestionService Grace Period Timer\n(10.0s window)"]
        ZoneMgr["MultiZoneManager.reset_camera()\n(Thread-Safe RLock)"]
        LateRec["Late Recognition Check\n(just_recognized == True)"]
    end

    subgraph Backend_FastAPI["FastAPI Backend Server"]
        EventEP["POST /api/v1/events\nPOST /api/v1/events/reconcile-sessions"]
        DurAccum["_accumulate_workstation_duration()\n(active_seconds / idle_seconds)"]
        PresProc["process_presence_on_event()"]
        Reconciler["reconcile_stale_presence_sessions()"]
    end

    subgraph Database["PostgreSQL Storage"]
        PS[("presence_sessions\n(Check Constraints >= 0)")]
        DE[("detection_events\n(Append-Only Log)")]
    end

    StreamWorker -->|Camera Disconnect| StatusCB
    StatusCB --> TimerMgr
    TimerMgr -->|Grace Period Expired| ZoneMgr
    ZoneMgr -->|Departure Event (reason: disconnect)| EventEP

    LateRec -->|workstation_active (action: identity_resolved)| EventEP
    EventEP --> PresProc
    PresProc --> DurAccum
    DurAccum --> PS
    Reconciler -->|Close Orphaned Sessions| PS
```

### 1. Camera Disconnect Handling & Grace Period
- **Multi-Callback Architecture:** In [`stream_manager.py`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/ai_engine/stream/stream_manager.py#L34-L62), `CameraStreamManager` was upgraded from a single callback to a list of subscribers `_status_callbacks`. When any camera worker changes status (`ONLINE`, `DEGRADED`, `OFFLINE`, `ERROR`, `STOPPED`), all registered subscribers are notified safely.
- **Configurable Grace Period:** In [`service.py`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/ai_engine/service.py#L77-L135), `_on_camera_status_change` tracks camera drops. When a camera enters `OFFLINE`, `ERROR`, or `DEGRADED`, a timer of `disconnect_grace_period_seconds` (default 10.0s) is scheduled.
- **Grace Period Recovery:** If the camera reconnects and transitions to `ONLINE` within the 10.0s window, the timer is cancelled and `zone_manager.handle_camera_reconnect(camera_id)` restores normal tracking. Occupancy states in the zone remain untouched.
- **Departure Emission & Isolation:** If the grace period expires, `_trigger_camera_disconnect_reset` calls `zone_manager.reset_camera(camera_id, emit_exit_events=True)`. This resets **only** the zones assigned to that camera ID, clears in-memory occupant maps, and dispatches departure events (`reason: "camera_disconnect"`). All other cameras continue monitoring without interruption.
- **Shutdown Flush:** In [`service.py:317-327`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/ai_engine/service.py#L317-L327), calling `stop()` cancels all pending disconnect timers and flushes departure events for all registered cameras to the persistent dispatcher before shutdown.

### 2. Late Face Recognition
- **State Transition 1B:** In [`occupancy_tracker.py:180-265`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/ai_engine/analytics/occupancy_tracker.py#L180-L265), the tracker checks:
  ```python
  just_recognized = False
  if not sess.is_employee_recognized and is_recognized:
      sess.employee_id = recognized_emp_id
      sess.is_employee_recognized = True
      just_recognized = True
  ```
- **Dispatched Event:** When `just_recognized and prev_state in (OccupancyState.ACTIVE, OccupancyState.IDLE)`, the tracker emits a `workstation_active` event with:
  - `employee_id = sess.employee_id`
  - `metadata_json: {"action": "identity_resolved", "identification_event": "late_recognition", "previous_state": "vacant", "current_state": prev_state.value}`
- **Backend Session Creation:** In [`event_service.py:126-170`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/server/app/services/event_service.py#L126-L170), `process_presence_on_event` queries for an open `PresenceSession` matching `(employee_id, zone_id)`. None is found (since previous events were anonymous), so it creates a new `PresenceSession` with `status = "active"`.
- **Duplicate Suppression:** On frame $N+1$, `sess.is_employee_recognized` is already `True`. `just_recognized` evaluates to `False`. Zero duplicate events are emitted.

### 3. Active and Idle Duration Accumulation
- **Accumulation Helper:** Implemented `_accumulate_workstation_duration()` in [`event_service.py:27-68`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/server/app/services/event_service.py#L27-L68):
  - Calculates `delta_seconds = max(0.0, (event_time - session.last_seen_at).total_seconds())`.
  - If previous status was `"idle"`, adds delta to `session.idle_seconds`.
  - If previous status was `"active"` and the event is a transition to `workstation_idle` with `inactivity_duration_seconds` in metadata, it attributes the reported inactivity window to `idle_seconds` and any remainder to `active_seconds`.
  - Otherwise, adds delta to `session.active_seconds`.
- **Timestamp Protection:** If `event_time <= session.last_seen_at`, the function returns immediately. Out-of-order deliveries and duplicate events can never decrement durations or regress `last_seen_at`.
- **Non-Negative Guarantee:** All additions are derived from `max(0.0, ...)`, strictly satisfying database constraints `ck_presence_session_active_seconds` and `ck_presence_session_idle_seconds`.
- **Closure Attribution:** Applied during departure, zone switching, and regular state updates.

### 4. Stale Session Reconciliation Mechanism
- **Reconciliation Service:** Implemented `reconcile_stale_presence_sessions` in [`event_service.py:175-265`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/server/app/services/event_service.py#L175-L265):
  - Filters `PresenceSession` records where `session_type = 'workstation'` and `ended_at IS NULL`.
  - Joins `WorkstationZone` and `Camera`.
  - Matches sessions where:
    1. Camera is inactive (`is_active = False`).
    2. Camera status is `'offline'` or `'unknown'` for $\ge$ `offline_camera_grace_seconds` (default 60.0s).
    3. Session `last_seen_at` is older than `max_stale_seconds` (default 900.0s) and camera has no fresh heartbeat.
  - Sets `session.ended_at = session.last_seen_at` (avoids accumulating phantom attendance).
  - Sets `session.status = "closed"`.
  - Idempotent: repeated executions match zero rows and commit cleanly.
- **REST Endpoint:** Added `POST /api/v1/events/reconcile-sessions` in [`events.py:112-140`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/server/app/api/v1/endpoints/events.py#L112-L140) with query parameters `max_stale_seconds`, `offline_camera_grace_seconds`, `location_id`, and `camera_id`.
- **Heartbeat Hook:** In [`camera_service.py:408-445`](file:///c:/Users/user10/Desktop/Camera_Intelligence/camera_intelligence/server/app/services/camera_service.py#L408-L445), when single or batch heartbeats report a camera `offline` or `unknown`, reconciliation is automatically invoked for those cameras.

---

## 4. Test Suite Execution & Verification Results

### Lifecycle Integration Suite (`tests/test_workstation_session_lifecycle.py`)
Executed against PostgreSQL with full database transaction management:
```powershell
.\server\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_workstation_session_lifecycle.py"
```
**Result: 12 passed in 0.494s**

| Test Method | Focus Area | Observed Behavior | Status |
| :--- | :--- | :--- | :---: |
| `test_01_camera_disconnection_during_occupancy` | Disconnect Isolation | Emits departure (`reason: camera_disconnect`). Zone 1 reset; Zone 2 on Camera 2 remains ACTIVE. | **PASS** |
| `test_02_camera_reconnect_within_grace_period` | Reconnect Grace Window | Dropped at $t=102$, reconnected at $t=109$ (< 10s grace). No departures emitted; state preserved. | **PASS** |
| `test_03_camera_disconnect_grace_expiration` | Grace Expiration & Idempotency | Dropped at $t=100$, evaluated at $t=111$. Emits 1 departure. Evaluation at $t=115$ yields 0 events. | **PASS** |
| `test_04_late_face_rec_emits_workstation_active` | AI Identity Resolution | Anon entry at $t=100$. Face recognized at $t=102$. Emits `workstation_active` (emp=101). Frame 3: 0 events. | **PASS** |
| `test_05_late_face_rec_creates_single_session` | Single Session Creation | Anon event: 0 sessions. Late rec event: 1 session created. Frame 3 event: 1 session preserved. | **PASS** |
| `test_06_active_and_idle_duration_accumulation` | Metric Accumulation | $1150s$ visit: $1000s$ idle + $150s$ active accurately summed and committed. | **PASS** |
| `test_07_duration_protection_out_of_order` | Timestamp Safety | Event arriving with timestamp older than `last_seen_at` does not modify metrics or regress time. | **PASS** |
| `test_08_edge_restart_handling` | Edge Process Reboot | Re-detected occupant refreshes `last_seen_at` on existing DB session without duplicate insert. | **PASS** |
| `test_09_stale_session_cleanup_offline_camera` | Offline Reconciliation | Camera offline > 60s: session safely closed with `ended_at = last_seen_at`. Idempotent on 2nd run. | **PASS** |
| `test_10_stale_session_cleanup_respects_grace` | Transient Drop Protection | Camera dropped 15s ago (< 60s grace): session kept open. | **PASS** |
| `test_11_duplicate_departure_handling` | Duplicate Rejection | Duplicate exit event on closed session safely returns `None` without error. | **PASS** |
| `test_12_multi_employee_isolation_in_same_zone`| Multi-Occupant Isolation | Emp 101 becomes idle and departs; Emp 102 in same zone remains active throughout. | **PASS** |

---

### Regression Verification Suite Summary

| Test Suite | File Path | Total Tests | Execution Time | Result |
| :--- | :--- | :---: | :---: | :---: |
| **Workstation Lifecycle** | `tests/test_workstation_session_lifecycle.py` | 12 | 0.494s | **PASS** |
| **Workstation Inactivity**| `tests/test_workstation_inactivity.py` | 20 | 0.422s | **PASS** |
| **Stream Manager & Pipeline** | `tests/test_stream_manager_pipeline.py` | 14 | 7.876s | **PASS** |
| **Event APIs & Ingestion**| `tests/test_event_apis.py` | 17 | 0.465s | **PASS** |
| **Camera Management APIs**| `tests/test_camera_apis.py` | 14 | 0.372s | **PASS** |
| **Workstation Zone APIs** | `tests/test_zone_and_schedule_apis.py` | 21 | 0.426s | **PASS** |
| **System Management APIs**| `tests/test_management_apis.py` | 24 | 0.523s | **PASS** |
| **TOTAL** | — | **122** | **~10.6s** | **ALL PASSED** |

---

## 5. Failures Encountered & Mitigations

During testing and implementation, three non-trivial engineering obstacles were encountered and resolved:

1. **Lock Reentrancy Deadlock in `MultiZoneManager`:**
   - *Problem:* `handle_camera_disconnect` acquired `self._lock` and called `self.reset_camera()`, which also attempted to acquire `self._lock`. Because `_lock` was initialized as `threading.Lock()` (non-reentrant), worker threads deadlocked.
   - *Fix:* Upgraded `self._lock` to `threading.RLock()` in `occupancy_tracker.py`, allowing reentrant thread acquisition.
2. **`NoneType` Duration Addition during In-Memory Instantiation:**
   - *Problem:* In mock or unit test environments where `PresenceSession` was instantiated directly without database defaults, `session.active_seconds` evaluated to `None`, triggering `TypeError: unsupported operand type(s) for +=: 'NoneType' and 'int'`.
   - *Fix:* Added defensive initialization in `_accumulate_workstation_duration()`:
     ```python
     if session.active_seconds is None:
         session.active_seconds = 0
     if session.idle_seconds is None:
         session.idle_seconds = 0
     ```
3. **SQLite `JSONB` Dialect Incompatibility in Lifecycle Test:**
   - *Problem:* Initial test setup attempted in-memory SQLite (`sqlite:///:memory:`). SQLite's DDL compiler failed on PostgreSQL `JSONB` columns in `workstation_zones.polygon_points`.
   - *Fix:* Configured `test_workstation_session_lifecycle.py` to utilize `SessionLocal` against PostgreSQL with dedicated test fixture codes (`TEST-LOC-WSLC`, `TEST-CAM-WSLC1`) and isolated cleanup fixtures.

---

## 6. Remaining Limitations & Recommendations

1. **Dense Occlusion Bounding Box Crosstalk:**
   - When two people sit extremely close (e.g. side-by-side pair programming), their 2D bounding boxes can overlap by 30–50%. Optical flow inside Occupant A's box may capture movement from Occupant B. A future enhancement could mask out overlapping bounding boxes before optical flow computation.
2. **Scheduled Worker for Periodic Stale Session Reconciliation:**
   - Currently, `reconcile_stale_presence_sessions` is triggered via `POST /api/v1/events/reconcile-sessions` or when heartbeats report `offline`. In high-scale deployments, running this function every 5 minutes via a FastAPI background scheduler (or Celery beat) will ensure unattended orphan cleanup if the edge disconnects silently without emitting heartbeats.
