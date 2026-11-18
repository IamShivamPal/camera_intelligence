# Camera Intelligence — Phase 6A: Live Monitoring Architecture Audit

## 1. Executive Summary

This architecture audit establishes the exact current capabilities, technical limitations, and required components for implementing a production-grade **Live Monitoring & CCTV Grid UI** in the Camera Intelligence platform.

### Core Audit Findings
1. **No Browser Video Streaming Protocols Exist**: The system currently captures and processes video exclusively within the Python `EdgeIngestionService` process via OpenCV (`cv2.VideoCapture`). There is **zero implementation** of HLS (HTTP Live Streaming), WebRTC, MJPEG, RTSP rebroadcasting, or WebSocket binary frame streaming. Modern browsers cannot directly consume raw RTSP streams.
2. **Decoded Frames Are Inaccessible to External Clients**: Decoded frames exist exclusively in ephemeral in-memory queues (`BoundedFrameBuffer`) as NumPy arrays. Neither FastAPI nor the edge service provides frame snapshot endpoints (`GET /cameras/{id}/snapshot`) or video feeds.
3. **AI Telemetry Is Asynchronous & Decoupled from Video**: YOLO bounding boxes, ByteTrack IDs, employee recognition results, and workstation occupancy transitions are dispatched as JSON telemetry events to `POST /api/v1/events` and persisted in PostgreSQL. However, because video frames are not transmitted to the browser, there is no video layer to anchor these bounding boxes onto.
4. **Camera Connectivity Status in PostgreSQL Is Static**: While `RTSPStreamWorker` actively tracks live connection health in memory (`ONLINE`, `OFFLINE`, `DEGRADED`, `ERROR`), these state changes are **never pushed back** to the PostgreSQL `cameras.connection_status` column. The database retains whatever static status was assigned during camera registration (default: `'unknown'`).
5. **Face Enrollment Pipeline Has an Architectural Gap**: While the backend and AI Engine possess deep learning components for RetinaFace alignment and AuraFace v1 512D embeddings, the FastAPI backend currently exposes **no image upload endpoint** (`multipart/form-data`) that accepts a raw portrait and executes the ONNX pipeline.

---

## 2. Current Architecture & Component Inventory

```mermaid
flowchart TD
    subgraph Edge ["Edge Ingestion Service (Python Process)"]
        CamWorker["RTSPStreamWorker (Thread per camera)"]
        CV2["cv2.VideoCapture (RTSP / MP4 / Webcam)"]
        FrameBuf["BoundedFrameBuffer (FIFO, maxsize=15, in-memory ndarray)"]
        Worker["LivePipelineWorker (Inference Thread)"]
        YOLO["YOLO11s (Person Detection) + ByteTrack"]
        FacePipe["FaceProcessingPipeline (RetinaFace + AuraFace ONNX)"]
        ZoneMgr["MultiZoneManager (Polygon Ray-Casting & Optical Flow)"]
        Dispatcher["PersistentTelemetryDispatcher (SQLite Queue)"]
    end

    subgraph Backend ["FastAPI Application (Port 8000)"]
        EventEP["POST /api/v1/events (Detection Ingestion)"]
        CamEP["/api/v1/cameras (Inventory CRUD only)"]
        ZoneEP["/api/v1/zones (Polygon Definitions)"]
        FaceEP["/api/v1/face-enrollments (512D Vector Only)"]
        DB[(PostgreSQL Database)]
    end

    subgraph Client ["React Frontend (Browser)"]
        ClientPages["Overview / Cameras / Workstations / Employees"]
        NoVideo["MISSING: No Video Stream / No WebSocket / No WebRTC Player"]
    end

    CV2 --> CamWorker
    CamWorker --> FrameBuf
    FrameBuf --> Worker
    Worker --> YOLO
    Worker --> FacePipe
    Worker --> ZoneMgr
    Worker --> Dispatcher
    Dispatcher -- "HTTP POST JSON (offline queue)" --> EventEP
    EventEP --> DB
    ClientPages -- "REST Polling" --> Backend
    ClientPages -. "NO VIDEO PIPELINE" .- NoVideo
```

### Detailed Component Inventory

| Component | File Path | Current Capability | Video Output |
|---|---|---|---|
| **RTSP Stream Worker** | `ai_engine/stream/rtsp_worker.py` | Dedicated capture thread per camera, auto-reconnect with exponential backoff, downsampling to `sampling_fps` (5.0 FPS). | In-memory `FrameItem` (NumPy BGR array) |
| **Bounded Frame Buffer** | `ai_engine/stream/frame_buffer.py` | Thread-safe bounded queue (`deque(maxlen=15)`) with automatic FIFO dropping of oldest frames under load. | In-memory only; no external IPC or network exposure |
| **Camera Stream Manager** | `ai_engine/stream/stream_manager.py` | Multi-camera lifecycle orchestrator, per-camera worker registry, health telemetry collector. | In-memory frame access via `get_frame(camera_id)` |
| **Live Pipeline Worker** | `ai_engine/pipeline/pipeline_worker.py` | Continuous inference loop: runs YOLO11s, ByteTrack, RetinaFace, AuraFace, and Farneback optical flow. | Dispatches JSON `DetectionPayload` to dispatcher |
| **Event Client & Dispatcher** | `ai_engine/client/event_client.py` & `persistent_dispatcher.py` | SQLite-backed offline resilient queue (`runs/telemetry_queue.db`) dispatching events to `POST /api/v1/events`. | JSON HTTP payloads only |
| **FastAPI Camera Router** | `server/app/api/v1/endpoints/cameras.py` | REST CRUD operations for camera inventory (`camera_code`, `name`, `location_id`, `camera_role`, `stream_secret_ref`). | Zero streaming or snapshot endpoints |

---

## 3. Existing Streaming Protocols & Evidence

An exhaustive code audit was performed across all backend and edge services. Below is the direct evidence of what exists and what does not exist:

| Protocol / Capability | Status | Evidence from Codebase |
|---|---|---|
| **RTSP Ingestion (Ingress)** | **IMPLEMENTED** | Implemented in `ai_engine/stream/rtsp_worker.py` line 97: `self._cap = self.capture_factory(uri)`. Uses OpenCV VideoCapture over TCP/UDP RTSP, local video files, or USB webcam indices. |
| **RTSP Rebroadcast / Egress** | **NOT IMPLEMENTED** | No RTSP server (e.g. MediaMTX, Live555, or GStreamer rtsp-server) exists to rebroadcast streams. |
| **HLS (HTTP Live Streaming)** | **NOT IMPLEMENTED** | Zero `.m3u8` playlist generation, zero `.ts` or fMP4 segmenting, and no FFmpeg HLS muxer present in codebase. |
| **WebRTC (WHEP / WHIP)** | **NOT IMPLEMENTED** | No WebRTC signaling server, no ICE/STUN/TURN configuration, and no `aiortc`, MediaSoup, Pion, or LiveKit dependencies installed. |
| **MJPEG (`multipart/x-mixed-replace`)** | **NOT IMPLEMENTED** | No FastAPI streaming endpoint (`StreamingResponse(..., media_type="multipart/x-mixed-replace")`) exists. |
| **WebSocket Video Streaming** | **NOT IMPLEMENTED** | FastAPI router has zero WebSocket routes (`@router.websocket`). No binary frame transfer over WebSockets exists. |
| **Frame Snapshot Endpoint** | **NOT IMPLEMENTED** | Neither `server/app/api/v1/endpoints/cameras.py` nor `ai_engine` implements any JPEG frame extraction endpoint (`GET /cameras/{id}/snapshot`). |
| **Browser-Compatible Stream URLs** | **NOT IMPLEMENTED** | Cameras table stores raw `stream_secret_ref` strings. Modern browsers cannot open `rtsp://` URLs without browser plugins (deprecated since NPAPI removal). |
| **Multi-Camera Isolation** | **IMPLEMENTED** | `CameraStreamManager` isolates each camera in its own Python thread. A timeout or failure on Camera A does not block Camera B. |
| **Backend Connection State Sync** | **NOT IMPLEMENTED** | `StreamHealth.status` is tracked in Python memory only. No mechanism exists to write `online`/`offline`/`degraded` back to PostgreSQL `cameras.connection_status`. |

---

## 4. Available Detection Telemetry

While video streaming is absent, the AI Engine produces rich real-time detection telemetry that is persisted in PostgreSQL:

| Telemetry Type | Generation Source | Persistence in Database | Delivered to Frontend? |
|---|---|---|---|
| **YOLO Bounding Boxes** | `PersonDetector` (`YOLO11s`) | `detection_events.metadata_json["bbox"]` as `[x1, y1, x2, y2]` in pixel coordinates. | Accessible via `GET /api/v1/events` (REST polling). |
| **ByteTrack Ephemeral IDs** | `StreamTrackerManager` | `detection_events.tracker_id` (e.g., `trk_0042`). | Accessible via `GET /api/v1/events`. |
| **Employee Face Recognition** | `FaceProcessingPipeline` (AuraFace v1) | `detection_events.employee_id` and `event_type = 'employee_recognized'`. | Accessible via `GET /api/v1/events`. |
| **Recognition Confidence** | `FaceProcessingPipeline` (Cosine similarity) | `detection_events.metadata_json["face_conf"]` & `["face_sim"]`. | Accessible via `GET /api/v1/events`. |
| **Workstation Polygon Boundaries** | Workstation Zones Configuration | `workstation_zones.polygon_points` as normalized $[0.0, 1.0]$ coordinates. | Fully accessible via `GET /api/v1/zones`. |
| **Workstation Occupancy Transitions** | `MultiZoneManager` (Jordan Ray-Casting) | `detection_events.event_type = 'workstation_active'` or `'workstation_idle'`. | Accessible via `GET /api/v1/events`. |
| **Farneback Inactivity Events** | `InactivityDetector` (Optical Flow) | `alerts` table (`alert_type = 'workstation_inactivity'`). | Accessible via `GET /api/v1/alerts`. |
| **Unknown Person Events** | Face pipeline classification `< 0.45` | `detection_events.event_type = 'unknown_person'`. | Accessible via `GET /api/v1/events`. |

### Critical Limitation for UI
Because the bounding boxes in `metadata_json["bbox"]` represent pixel coordinates $[x_1, y_1, x_2, y_2]$ of the camera frame, rendering them requires an active frame of identical aspect ratio and resolution. Without a video stream or live snapshot feed, rendering bounding boxes on an empty canvas produces a disjointed and confusing user experience.

---

## 5. Face Enrollment Pipeline Verification

The portrait enrollment pipeline was audited stage by stage:

$$\text{Portrait Image} \longrightarrow \text{Face Detection} \longrightarrow \text{Face Alignment} \longrightarrow \text{AuraFace 512D} \longrightarrow \text{Backend Enrollment} \longrightarrow \text{PostgreSQL} \longrightarrow \text{Edge Recognition}$$

```mermaid
flowchart LR
    Stage1["1. Portrait Image<br/>(File Picker)"]
    Stage2["2. Face Detection<br/>(RetinaFace R34)"]
    Stage3["3. Face Alignment<br/>(112x112 Affine)"]
    Stage4["4. AuraFace 512D<br/>(ONNX Runtime)"]
    Stage5["5. Backend POST<br/>(/face-enrollments)"]
    Stage6["6. PostgreSQL<br/>(Vector Registry)"]
    Stage7["7. Edge Sync<br/>(Live Pipeline)"]

    Stage1 -. "DISCONNECTED" .-> Stage2
    Stage2 --> Stage3
    Stage3 --> Stage4
    Stage4 -. "DISCONNECTED" .-> Stage5
    Stage5 --> Stage6
    Stage6 -. "DISCONNECTED (No Push)" .-> Stage7

    classDef implemented fill:#064e3b,stroke:#059669,color:#fff;
    classDef gap fill:#7f1d1d,stroke:#dc2626,color:#fff;
    class Stage1,Stage6 implemented;
    class Stage2,Stage3,Stage4 implemented;
    class Stage5 implemented;
    class Stage7 gap;
```

### Stage-by-Stage Findings

| Stage | Operation | Implemented Location | Operational Status & Gap Analysis |
|---|---|---|---|
| **1. Portrait Image Selection** | File Picker / Drag & Drop | `client/src/components/enrollment/FaceEnrollmentModal.tsx` | **Working in UI**: User selects image; creates temporary client-side `blob:` preview with alignment guide. |
| **2. Face Detection** | RetinaFace ResNet34 landmarks | `ai_engine/pipeline/face_pipeline.py:170` | **Implemented in AI Engine only**. Not exposed via HTTP. FastAPI has no route to receive an image and call RetinaFace. |
| **3. Face Alignment** | 112x112 Canonical Affine Warp | `ai_engine/pipeline/face_pipeline.py:246` | **Implemented in AI Engine only**. Operates on OpenCV images using `cv2.estimateAffinePartial2D`. |
| **4. Embedding Extraction** | AuraFace v1 512D Vector | `ai_engine/pipeline/face_pipeline.py:263` & `tests/build_employee_templates.py` | **Implemented in AI Engine only**. Runs `auraface_v1_glintr100.onnx` inference. No online web endpoint exists for this. |
| **5. Backend Enrollment API** | `POST /employees/{id}/face-enrollments` | `server/app/api/v1/endpoints/face_enrollments.py` | **Working with contract mismatch**: Endpoint strictly accepts JSON `{ embedding: list[float] }`. It expects a pre-calculated 512D vector, not an image file. |
| **6. PostgreSQL Storage** | Insert into `employee_face_embeddings` | `server/app/services/face_enrollment_service.py` | **Fully Working**: Stores 512D array, validates L2 unit norm, enforces active template uniqueness, updates `enrollment_status`. |
| **7. Edge Recognition Sync** | Update template cache in running worker | `ai_engine/pipeline/face_pipeline.py:160` | **Missing Dynamic Sync**: Edge service loads templates on startup from disk/DB. There is no webhook, WebSocket, or message queue to notify the live worker when a new template is enrolled. |

---

## 6. Performance & Security Analysis for Live Video

### 1. Multi-Camera Scalability & Bandwidth
- **Bandwidth Consumption**: 1080p RTSP stream at 15 FPS consumes $\approx 2.5\text{ to }4.0\text{ Mbps}$ per camera (H.264). A 16-camera grid requires $40\text{ to }64\text{ Mbps}$ of sustained local network throughput.
- **Client Decoding Bottleneck**: Decoding 9 or 16 concurrent H.264 streams in a single browser window can overwhelm client GPU hardware decoders, leading to dropped frames and high CPU utilization.
- **Edge Inference Saturation**: YOLO11s + ByteTrack takes $\approx 18\text{ to }28\text{ ms}$ per frame on an NVIDIA RTX GPU. At 5 FPS sampling across 8 cameras (40 FPS total), GPU inference reaches $\approx 80-90\%$ capacity.

### 2. Stream Security & Credential Protection
- **RTSP Credential Exposure**: RTSP URLs often contain embedded credentials (`rtsp://admin:pass@192.168.1.10:554/stream`). The backend correctly hides these by storing only a `stream_secret_ref`. Direct browser RTSP streaming would require exposing these credentials or creating an unauthenticated proxy.
- **Stream Access Authorization**: Any live video endpoint must require JWT bearer authentication or short-lived signed tokens (`?token=...`) to prevent unauthorized viewing of sensitive camera feeds.

---

## 7. Required Architectural Changes Before Live Monitoring UI

To achieve genuine live camera feeds in the React frontend without fake mock players or broken RTSP links, the following architectural enhancements are required:

### Option Comparison for Video Delivery

| Streaming Protocol | Latency | Browser Compatibility | Server Overhead | Recommendation |
|---|---|---|---|---|
| **MJPEG (Motion JPEG)** | $100 - 300\text{ ms}$ | Native `<img>` tag across all browsers | High bandwidth, low CPU transcoding | **Best for Immediate Milestone (Phase 6B)**: Zero external dependencies; native in FastAPI/OpenCV. |
| **Low-Latency HLS (LL-HLS)** | $1.5 - 3.0\text{ s}$ | Requires `hls.js` library | High CPU/disk I/O (segments `.ts` chunks) | Good for recording playback, but latency is high for real-time security surveillance. |
| **WebRTC (WHEP / MediaMTX)** | $< 250\text{ ms}$ | Native browser HTML5 `<video>` | Requires dedicated media server (e.g. MediaMTX / go2rtc) | **Best for Production Scale**: Sub-second latency, hardware accelerated, low bandwidth. |

### Required Backend Changes (FastAPI)
1. **Camera Frame Snapshot Endpoint**:
   - `GET /api/v1/cameras/{id}/snapshot`
   - Returns a single JPEG frame with `Content-Type: image/jpeg` and caching headers.
   - Enables low-bandwidth periodic thumbnail refreshes across the camera grid.
2. **MJPEG Live Stream Endpoint**:
   - `GET /api/v1/cameras/{id}/stream`
   - Streams `multipart/x-mixed-replace; boundary=frame` directly to the browser.
3. **Camera Live Status Synchronization**:
   - `POST /api/v1/cameras/{id}/heartbeat` or an internal pub/sub channel for `RTSPStreamWorker` to update `cameras.connection_status` (`online`/`offline`/`degraded`) in real-time.
4. **Server-Side Portrait Face Enrollment**:
   - `POST /api/v1/employees/{id}/face-enrollments/upload`
   - Accepts `UploadFile` (multipart form), executes face alignment and AuraFace embedding extraction server-side, and persists the resulting template.

### Required Edge AI Changes
1. **Shared Frame Access Interface**:
   - Expose the latest decoded BGR frame from `BoundedFrameBuffer` via a lightweight local IPC (shared memory, Unix socket, or local HTTP sidecar on port 8001).
2. **Annotated Frame Generation**:
   - Provide an option to stream **annotated frames** (where OpenCV draws the YOLO bounding box, person label, and workstation polygon directly onto the video before encoding) vs **raw clean frames**.
3. **Dynamic Template Reload Hook**:
   - Implement a reload endpoint or listener in `EdgeIngestionService` (`/reload-templates`) to update the template cache without requiring a process restart.

---

## 8. Recommended Implementation Sequence

```mermaid
flowchart TD
    Step1["Step 1: Snapshot & Status Sync Backend Engine<br/>• Frame buffer IPC / local bridge<br/>• GET /api/v1/cameras/{id}/snapshot<br/>• Live connection_status heartbeat"]
    Step2["Step 2: MJPEG / Low-Latency Stream Endpoint<br/>• GET /api/v1/cameras/{id}/stream<br/>• StreamingResponse(multipart/x-mixed-replace)"]
    Step3["Step 3: Server-Side Face Enrollment Upload<br/>• POST /api/v1/employees/{id}/face-enrollments/upload<br/>• Server-side ONNX vector extraction"]
    Step4["Step 4: Phase 6B Live Monitoring Frontend<br/>• Multi-camera grid (1x1, 2x2, 3x3, 4x4)<br/>• Real camera stream feed with loading/offline fallbacks<br/>• Real-time detection event overlay sidebar<br/>• PTZ / Stream settings controls"]

    Step1 --> Step2 --> Step3 --> Step4
```

1. **Step 1 (Backend Core)**: Implement frame snapshot sharing and connection status heartbeat between `EdgeIngestionService` and FastAPI.
2. **Step 2 (Stream Server)**: Implement `GET /api/v1/cameras/{id}/stream` (MJPEG) as the immediate, reliable bridge to modern web browsers.
3. **Step 3 (Biometric Pipeline Completion)**: Implement `POST /api/v1/employees/{id}/face-enrollments/upload` to complete the full 7-stage face enrollment pipeline server-side.
4. **Step 4 (Phase 6B Frontend Implementation)**: Build the production Live Monitoring UI with camera grid layout selection (1x1, 2x2, 3x3, 4x4), camera card telemetry, genuine video stream rendering, and synchronized detection event sidebar.

---

## 9. Conclusion

The Camera Intelligence platform possesses an advanced, production-grade video decoding and deep learning pipeline at the edge (`YOLO11s`, `ByteTrack`, `RetinaFace`, `AuraFace ONNX`, `Farneback Flow`), but lacks the **video egress bridge** necessary to transmit decoded frames into a web browser.

Proceeding directly to a frontend Live Monitoring UI without implementing this video egress layer would force the frontend to display broken video streams or fabricate mock feeds. Following the recommended sequence above will ensure genuine, low-latency CCTV video streams and authentic bounding box visualization in the browser.
