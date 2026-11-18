"""
Live Detection & Streaming Inference Worker
Orchestrates Person Detection, ByteTrack Tracking, Face Biometrics, and Event Dispatching.
"""

import logging
import threading
import time
from typing import Any

from ai_engine.stream.stream_manager import CameraStreamManager
from ai_engine.stream.frame_buffer import FrameItem
from ai_engine.pipeline.detector import PersonDetector, TrackedPerson
from ai_engine.pipeline.tracker import StreamTrackerManager
from ai_engine.pipeline.face_pipeline import FaceProcessingPipeline, FaceRecognitionResult
from ai_engine.client.event_client import BackendEventClient, DetectionPayload
from ai_engine.analytics.occupancy_tracker import MultiZoneManager

logger = logging.getLogger(__name__)


class LivePipelineWorker:
    """
    Decoupled processing worker running inference over frames received from CameraStreamManager.
    Decoupled from camera I/O: Slow inference or frame dropping will never block or stall camera decoding.
    """

    def __init__(
        self,
        stream_manager: CameraStreamManager,
        detector: PersonDetector,
        face_pipeline: FaceProcessingPipeline | None = None,
        event_client: BackendEventClient | None = None,
        zone_manager: MultiZoneManager | None = None,
        enable_face_recognition: bool = True,
    ):
        self.stream_manager = stream_manager
        self.detector = detector
        self.face_pipeline = face_pipeline
        self.event_client = event_client or BackendEventClient()
        self.zone_manager = zone_manager
        self.enable_face_recognition = enable_face_recognition and (face_pipeline is not None)

        self._trackers: dict[int, StreamTrackerManager] = {}
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # Telemetry & Performance Counters
        self.total_frames_processed = 0
        self.total_persons_detected = 0
        self.total_events_generated = 0
        self.avg_inference_latency_ms = 0.0

    def _get_tracker(self, camera_id: int) -> StreamTrackerManager:
        if camera_id not in self._trackers:
            self._trackers[camera_id] = StreamTrackerManager(camera_id=camera_id)
        return self._trackers[camera_id]

    def start(self):
        """Start the live inference pipeline thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._inference_loop,
            name="LivePipelineWorker",
            daemon=True,
        )
        self._thread.start()
        logger.info("LivePipelineWorker started.")

    def stop(self, timeout: float = 3.0):
        """Stop the inference pipeline thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        logger.info("LivePipelineWorker stopped.")

    def process_frame(self, frame_item: FrameItem) -> list[DetectionPayload]:
        """
        Process a single sampled frame incrementally:
        1. YOLO11s Person Detection & ByteTrack tracking
        2. RetinaFace landmark extraction on person crops (if enabled)
        3. AuraFace 512D embedding & cosine verification (if enabled)
        4. Event generation & dispatching
        """
        start_t = time.perf_counter()

        persons: list[TrackedPerson] = self.detector.detect_and_track(
            frame_item.frame,
            persist=True,
        )

        latency = (time.perf_counter() - start_t) * 1000.0
        # Rolling average latency
        self.avg_inference_latency_ms = (
            0.9 * self.avg_inference_latency_ms + 0.1 * latency
            if self.avg_inference_latency_ms > 0
            else latency
        )
        self.total_frames_processed += 1
        self.total_persons_detected += len(persons)

        tracker_mgr = self._get_tracker(frame_item.camera_id)
        generated_events: list[DetectionPayload] = []

        for person in persons:
            ephemeral_tracker_id = tracker_mgr.format_ephemeral_id(person.tracker_id)
            tracker_mgr.update_track(person.tracker_id, timestamp=frame_item.timestamp)

            event_type = "unknown_person"
            emp_id = None
            metadata: dict[str, Any] = {
                "bbox": [round(c, 1) for c in person.box_xyxy],
                "detector_conf": round(person.confidence, 4),
            }

            # Optional Face Processing Boundary
            if self.enable_face_recognition and self.face_pipeline:
                crop = person.extract_crop(frame_item.frame)
                if crop.size > 0 and crop.shape[0] >= 30 and crop.shape[1] >= 30:
                    face_res: FaceRecognitionResult = self.face_pipeline.process_person_crop(crop)
                    if face_res.face_detected:
                        metadata["face_conf"] = round(face_res.face_confidence, 4)
                        metadata["face_sim"] = round(face_res.max_similarity, 4)
                        if face_res.classification == "recognized" and face_res.matched_employee_id:
                            event_type = "employee_recognized"
                            try:
                                emp_id = int(face_res.matched_employee_id)
                                person.recognized_employee_id = emp_id
                            except ValueError:
                                emp_id = None
                        elif face_res.classification == "unknown":
                            event_type = "unknown_person"

            payload = DetectionPayload(
                camera_id=frame_item.camera_id,
                location_id=frame_item.location_id,
                event_type=event_type,
                confidence=person.confidence,
                employee_id=emp_id,
                tracker_id=ephemeral_tracker_id,
                metadata_json=metadata,
            )
            generated_events.append(payload)

            if self.event_client:
                self.event_client.dispatch_event(payload)

        # 5. Workstation Zone Occupancy & Inactivity Analysis
        if self.zone_manager:
            zone_events = self.zone_manager.process_frame(
                camera_id=frame_item.camera_id,
                frame_bgr=frame_item.frame,
                persons=persons,
                timestamp=frame_item.timestamp,
            )
            for ze in zone_events:
                generated_events.append(ze)
                if self.event_client:
                    self.event_client.dispatch_event(ze)

        self.total_events_generated += len(generated_events)
        return generated_events

    def _inference_loop(self):
        """Worker loop continuously pulling frames from camera buffers."""
        while not self._stop_event.is_set():
            frame_item = self.stream_manager.get_any_frame(timeout=0.1)
            if frame_item is None:
                continue

            try:
                self.process_frame(frame_item)
            except Exception as e:
                logger.error("Error processing frame from camera %d: %s", frame_item.camera_id, e)
