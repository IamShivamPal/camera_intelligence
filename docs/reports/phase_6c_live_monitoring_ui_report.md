# Phase 6C: Live Monitoring & CCTV Command Center UI Implementation Report

**Project:** Camera Intelligence  
**Phase:** 6C — Live Monitoring & CCTV Command Center UI  
**Execution Date:** 2026-11-16  
**Status:** Completed & Verified  

---

## 1. Executive Summary

Phase 6C delivers the enterprise-grade **Live Monitoring & CCTV Command Center UI** within the React/TypeScript/Vite frontend. It integrates natively with the FastAPI Edge Video Bridge, camera health heartbeat APIs, workstation zone polygon boundaries, and real-time AI detection telemetry.

The implementation strictly honors production engineering constraints:
1. **Zero Fake Overlays / Simulated Feeds:** Live video displays genuine decoded MJPEG frames streamed from the Edge Ingestion Service. Only genuine registered cameras are displayed.
2. **Authenticated MJPEG Streaming without URL Query Tokens:** To satisfy browser compatibility while eliminating URL token leaks, an authenticated streaming hook (`useMjpegStream`) uses `fetch()` with the `ReadableStream` API, transmitting standard `Authorization: Bearer <token>` HTTP headers directly and parsing binary JPEG SOI (`0xFF, 0xD8`) and EOI (`0xFF, 0xD9`) markers.
3. **Automatic Resource Teardown:** Removing camera tiles or unmounting the monitoring wall aborts the underlying HTTP `ReadableStream` via `AbortController`, closing connections and decrementing Edge Ingestion viewer concurrency counts.
4. **Normalized Spatial Overlays:** Workstation zones are rendered in SVG overlay coordinates mapped from normalized float points `[0, 1]`. AI detection bounding boxes are mapped dynamically from `DetectionEvent.metadata_json.bbox` when available without fabricating fictitious detections.

---

## 2. Files Created and Modified

### Frontend Created:
- `client/src/pages/LiveMonitoring.tsx` — Complete CCTV command center page with layout switcher (1×1, 2×2, 3×3, 4×4), location/role filters, camera picker modal, live feed wall, and event panel integration.
- `client/src/hooks/useMjpegStream.ts` — Custom authenticated MJPEG reader hook using `fetch()`, `ReadableStream`, binary SOI/EOI parsing, ObjectURL lifecycle management with zero memory leaks, frame telemetry, and snapshot fallback.
- `client/src/components/live/CameraTile.tsx` — Video tile component featuring live MJPEG frame rendering, HUD overlays (LIVE pill, measured FPS, frame counter), connection status indicators, heartbeat timestamps, snapshot downloads, and tile fullscreen toggle.
- `client/src/components/live/PolygonOverlay.tsx` — SVG polygon overlay mapping workstation boundary coordinates `[0, 1]` with centroid tags and real-time state distinction (Configured / Active / Idle).
- `client/src/components/live/DetectionOverlay.tsx` — SVG overlay for AI detection telemetry mapping bounding boxes `[x1, y1, x2, y2]`, tracking IDs, and employee recognition tags.
- `client/src/components/live/LiveControlToolbar.tsx` — Command toolbar with grid layout toggles, auto-fill online camera action, clear wall action, location/role filters, refresh trigger, and global fullscreen toggle.
- `client/src/components/live/LiveEventPanel.tsx` — Collapsible live telemetry feed panel rendering recent events from `GET /api/v1/events` with reactive timestamps, filtering, and camera focus shortcuts.
- `client/src/components/live/CameraSelectorModal.tsx` — Modal interface for selecting registered cameras and assigning them to active grid slots.

### Frontend Modified:
- `client/src/App.tsx` — Replaced placeholder `/live` route with `<LiveMonitoring />`.
- `client/src/services/cameraService.ts` — Added `getSnapshot(id, quality, maxAge)` and `getStreamUrl(id, fps, quality)`.
- `client/src/types/api.ts` — Added `workstation_zone_id` to `DetectionEvent`.

### Backend & Test Files Created / Modified:
- `tests/test_live_monitoring_integration.py` — New 8-test integration suite covering unauthenticated streaming rejection, location RBAC stream isolation, deactivated camera rejection, 404 handling, snapshot fallback, normalized polygon retrieval, detection event telemetry ingestion/filtering, and camera heartbeats.
- `tests/test_auth_api.py` & `tests/test_management_apis.py` — Added idempotent test setup pre-cleaning to ensure isolated, repeatable test execution.

---

## 3. Integrated API Contracts

| Feature / UI Action | HTTP Method | Endpoint | Authorization | Notes |
|---|---|---|---|---|
| Camera Inventory | `GET` | `/api/v1/cameras?page=1&size=100` | `require_viewer` | Location-scoped camera listing |
| Location Directory | `GET` | `/api/v1/locations?is_active=true` | `require_viewer` | Used for location filter dropdown |
| MJPEG Video Stream | `GET` | `/api/v1/cameras/{id}/stream?fps=15&quality=75` | `require_viewer` | Multipart stream via `fetch` with Bearer token |
| Camera Snapshot | `GET` | `/api/v1/cameras/{id}/snapshot?quality=80` | `require_viewer` | Single JPEG frame fallback and download |
| Camera Workstation Zones | `GET` | `/api/v1/cameras/{id}/zones` | `require_viewer` | Retrieves linked zones |
| Workstation Zone Details | `GET` | `/api/v1/zones?camera_id={id}` | `require_viewer` | Retrieves normalized polygon points |
| Detection Telemetry Feed | `GET` | `/api/v1/events?camera_id={id}&size=50` | `require_viewer` | Bounded polling (4s) for live event activity |
| Camera Heartbeat | `POST` | `/api/v1/cameras/{id}/heartbeat` | `require_operator` | Updates status: online/degraded/offline |

---

## 4. Streaming Authentication Approach

### Problem Analysis
Standard HTML `<img src="/api/v1/cameras/{id}/stream">` elements cannot pass custom HTTP request headers (such as `Authorization: Bearer <token>`). Common anti-patterns place JWT tokens in URL query strings (e.g., `?token=...`), which exposes credentials in browser history, server access logs, reverse proxy telemetry, and network monitoring tools.

### Solution: Authenticated Fetch with `ReadableStream`
The `useMjpegStream` React hook implements client-side authenticated streaming:
1. Dispatches `fetch()` to `GET /api/v1/cameras/{id}/stream` with standard `Authorization: Bearer <token>` in HTTP headers.
2. If the backend responds with non-200 status (e.g. 401 Unauthorized, 403 Location Denied, 404 Not Found, 429 Viewer Limit, 503 Edge Offline), captures the exact error status code and JSON detail.
3. Accesses `response.body.getReader()` to stream incoming `Uint8Array` binary chunks.
4. Searches binary chunks for standard JPEG Start-Of-Image (`0xFF, 0xD8`) and End-Of-Image (`0xFF, 0xD9`) markers.
5. Slices each complete JPEG payload and constructs `new Blob([bytes], { type: 'image/jpeg' })`.
6. Generates an Object URL (`URL.createObjectURL(blob)`) and immediately revokes the previous frame's URL via `URL.revokeObjectURL()` to prevent memory accumulation.
7. Measures real-time frame reception rate (`FPS`) and total frame count.
8. Attaches an `AbortController` signal: when a tile is closed or the page unmounts, `abortController.abort()` immediately terminates the connection, alerting FastAPI and Edge Ingestion to release the viewer slot.

---

## 5. Camera Grid & CCTV Wall Functionality

- **Grid Matrix Switcher:** Supports 1×1 (focused single-camera inspection), 2×2 (4-camera matrix), 3×3 (9-camera command wall), and 4×4 (16-camera surveillance wall).
- **Slot Management:** Empty grid slots provide an interactive "Assign Camera" target. Users can selectively remove tiles, reorder cameras, or clear the entire grid.
- **Auto-Fill Online Action:** Automatically queries available online cameras and assigns them to unfilled grid slots with one click.
- **Location & Role Scoping:** Allows operators to filter available cameras by facility location, camera role (`entry_exit`, `workstation`, `perimeter`, `general`), or connectivity status.
- **Dual Fullscreen Modes:** Fullscreen inspection can be triggered either for an individual camera tile or for the entire CCTV video wall container.

---

## 6. Overlays & Telemetry Verification

### Workstation Polygons
- Extracted from `polygon_points` in `WorkstationZone`.
- Polygons are stored in normalized float coordinates `[0, 1]` relative to frame aspect ratio.
- Rendered using responsive SVG with `viewBox="0 0 1000 562.5"` (16:9 aspect ratio) overlaid on the video element.
- Centroid labels display `zone_code` and occupancy status.
- Configured zones are styled in cyan (`#06b6d4`). When a genuine backend event reports `workstation_active`, the zone illuminates in emerald green (`#10b981`); when `workstation_idle` occurs, it illuminates in amber (`#f59e0b`). No occupancy states are fabricated in the absence of genuine events.

### AI Detection Bounding Boxes
- Detection events from `GET /api/v1/events` are inspected for `metadata_json.bbox`.
- When available, `bbox` coordinates `[x1, y1, x2, y2]` are scaled to the SVG canvas.
- Displayed elements:
  - Bounding box with corner bracket accents.
  - Recognized employee badge (green) or unknown person badge (sky/blue).
  - Confidence percentage (e.g. `94% conf`) when provided.
  - Ephemeral stream tracking ID (e.g. `#TRK-0012`).
- If no bounding boxes are present in telemetry, the overlay strictly refrains from fabricating boxes, displaying a subtle indicator: *"No live bboxes"*.

---

## 7. Performance & Security Verification

1. **Viewer Concurrency Control:**
   - Edge Ingestion caps concurrent viewers per camera stream at `MAX_STREAM_VIEWERS_PER_CAMERA = 10`.
   - Exceeding the limit returns `429 Too Many Requests`. The UI cleanly renders a specific concurrency error with a reconnect button.
2. **Resource Teardown:**
   - Tile removal triggers `useMjpegStream` teardown: `abortController.abort()` cancels the `ReadableStream` reader and revokes all active blob URLs.
3. **Location Isolation (RBAC):**
   - Verified that a viewer assigned exclusively to Location A cannot access `/api/v1/cameras/{id}/stream` or `/snapshot` for cameras in Location B (HTTP 403 Forbidden).
4. **Credential Privacy:**
   - RTSP URLs and credentials are never transmitted to the browser.
   - Authentication tokens are never exposed in URL query parameters.

---

## 8. Verification & Test Results

### Automated Test Suite Execution:
```bash
python -m pytest tests/test_live_monitoring_integration.py \
                 tests/test_edge_video_bridge.py \
                 tests/test_camera_apis.py \
                 tests/test_event_apis.py \
                 tests/test_auth_api.py \
                 tests/test_management_apis.py \
                 tests/test_zone_and_schedule_apis.py \
                 tests/test_face_enrollment_apis.py
```
**Result:** **129 passed, 0 failed** in 15.40s.

### Frontend Quality Checks:
- `oxlint`: **0 warnings, 0 errors** across all 59 files.
- `tsc -b && vite build`: **Passed cleanly** in 441ms. Production bundle generated in `dist/`.

### Physical Camera Streaming Verification:
> **Status: NOT RUN**  
> Physical RTSP IP cameras were not connected to the local development environment during this phase. All video delivery and pipeline tests were verified using synthetic encoded JPEG frames, loopback edge stream workers, and mocked RTSP frame buffers.

---

## 9. Remaining Limitations

1. **Polling vs. WebSocket for Telemetry:** Detection events are retrieved via bounded REST polling (`GET /api/v1/events` every 4–5 seconds). A future Phase could implement a WebSocket or Server-Sent Events (SSE) telemetry channel for sub-second bounding box updates without polling overhead.
2. **WebRTC Ultra-Low Latency:** MJPEG streaming provides broad browser compatibility and per-frame JPEG inspection with 100–250ms latency. For sub-50ms latency at high scale, a WebRTC media server bridge (e.g., Janus / mediasoup) can be integrated in later phases.
