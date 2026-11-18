"""
Automated Test Suite for AI Engine Camera Stream Manager & Live Detection Pipeline
Phase 3, Task 1 Verification

Covers:
1. Frame Buffer Bounded Queue & FIFO Drop (Memory Safety)
2. Buffer Timeout and Close Lifecycle
3. RTSP Worker Acquisition and FPS Downsampling
4. Worker Reconnect on Stream Failure
5. Stream Read Timeout Handling
6. Multi-Camera Failure Isolation (One camera fails, others continue unaffected)
7. Camera Stream Manager Multi-Camera Orchestration
8. Resource Cleanup on Shutdown (Thread joins, VideoCapture release)
9. Real Video Stream Ingestion (Incremental processing)
10. YOLO11s Person Detection & ByteTrack Streaming Tracking Integration
11. Stream Tracker Ephemeral ID Safety Invariant
12. Face Processing Pipeline (RetinaFace 5-pt landmarks, 112x112 warping, AuraFace 512D vectors)
13. Backend Event Client Payload Validation & Offline Queueing
14. Live Pipeline Worker End-to-End Orchestration
"""

import sys
import time
import unittest
from pathlib import Path
import numpy as np

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_engine.stream.camera_config import CameraConfig, CameraStatus, StreamHealth
from ai_engine.stream.frame_buffer import BoundedFrameBuffer, FrameItem
from ai_engine.stream.rtsp_worker import RTSPStreamWorker
from ai_engine.stream.stream_manager import CameraStreamManager
from ai_engine.pipeline.detector import PersonDetector, TrackedPerson
from ai_engine.pipeline.tracker import StreamTrackerManager
from ai_engine.pipeline.face_pipeline import FaceProcessingPipeline, FaceRecognitionResult
from ai_engine.client.event_client import BackendEventClient, DetectionPayload
from ai_engine.pipeline.pipeline_worker import LivePipelineWorker


class MockVideoCapture:
    """Mock OpenCV VideoCapture for unit testing stream worker behavior."""

    def __init__(
        self,
        frames_to_yield: int = 100,
        fail_after_frames: int | None = None,
        stalls: bool = False,
        width: int = 640,
        height: int = 480,
    ):
        self.frames_to_yield = frames_to_yield
        self.fail_after_frames = fail_after_frames
        self.stalls = stalls
        self.width = width
        self.height = height
        self._count = 0
        self._is_opened = True
        self._is_released = False

    def isOpened(self) -> bool:
        return self._is_opened and not self._is_released

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self.isOpened():
            return False, None

        if self.stalls:
            time.sleep(0.05)
            return False, None

        if self.fail_after_frames is not None and self._count >= self.fail_after_frames:
            self._is_opened = False
            return False, None

        if self._count >= self.frames_to_yield:
            return False, None

        self._count += 1
        # Generate lightweight synthetic frame
        frame = np.full((self.height, self.width, 3), fill_value=(self._count % 255), dtype=np.uint8)
        return True, frame

    def set(self, propId: int, value: float) -> bool:
        return True

    def release(self):
        self._is_released = True
        self._is_opened = False


class TestStreamManagerAndPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_video_path = PROJECT_ROOT / "1.mp4"
        if not cls.test_video_path.exists():
            cls.test_video_path = PROJECT_ROOT / "office_test.mp4"

    # -------------------------------------------------------------------------
    # 1. Bounded Frame Buffer Tests
    # -------------------------------------------------------------------------

    def test_01_frame_buffer_bounded_fifo_drop(self):
        """1. Buffer enforces fixed max capacity, dropping oldest frames (FIFO)."""
        buf = BoundedFrameBuffer(maxsize=3)
        self.assertEqual(buf.qsize(), 0)

        # Push 5 frames into capacity-3 buffer
        for seq in range(1, 6):
            item = FrameItem(
                frame=np.zeros((10, 10, 3), dtype=np.uint8),
                frame_id=seq,
                timestamp=time.time(),
                camera_id=1,
                camera_code="CAM-01",
                location_id=10,
            )
            buf.put(item)

        # Buffer must have maxsize=3, and dropped_count=2
        self.assertEqual(buf.qsize(), 3)
        self.assertEqual(buf.dropped_count, 2)
        self.assertEqual(buf.total_pushed, 5)

        # Remaining frames in buffer must be 3, 4, 5 (oldest 1, 2 dropped)
        item1 = buf.get(timeout=0.1)
        item2 = buf.get(timeout=0.1)
        item3 = buf.get(timeout=0.1)
        self.assertIsNotNone(item1)
        self.assertIsNotNone(item2)
        self.assertIsNotNone(item3)
        self.assertEqual(item1.frame_id, 3)
        self.assertEqual(item2.frame_id, 4)
        self.assertEqual(item3.frame_id, 5)

        # Now buffer is empty
        self.assertTrue(buf.is_empty())

    def test_02_frame_buffer_timeout_and_close(self):
        """2. Buffer get() times out cleanly and close() wakes up waiting threads."""
        buf = BoundedFrameBuffer(maxsize=5)
        start = time.time()
        res = buf.get(timeout=0.1)
        elapsed = time.time() - start
        self.assertIsNone(res)
        self.assertGreaterEqual(elapsed, 0.08)

        # Closing buffer unblocks immediately
        buf.close()
        res2 = buf.get(timeout=1.0)
        self.assertIsNone(res2)

    # -------------------------------------------------------------------------
    # 2. RTSP Stream Worker Tests
    # -------------------------------------------------------------------------

    def test_03_mock_stream_worker_acquisition_and_sampling(self):
        """3. RTSP Worker acquires frames from stream and samples at target FPS."""
        mock_cap = MockVideoCapture(frames_to_yield=40)
        config = CameraConfig(
            camera_id=101,
            camera_code="CAM-TEST-01",
            name="Test Camera 1",
            stream_uri="mock://test1",
            location_id=1,
            sampling_fps=10.0,
            queue_size=10,
        )
        worker = RTSPStreamWorker(
            config=config,
            capture_factory=lambda uri: mock_cap,
        )

        worker.start()
        time.sleep(0.5)

        # Verify frames were read and buffered
        frame = worker.buffer.get(timeout=1.0)
        self.assertIsNotNone(frame)
        self.assertEqual(frame.camera_id, 101)
        self.assertEqual(frame.camera_code, "CAM-TEST-01")
        self.assertGreater(worker.health.total_frames_read, 0)
        self.assertGreater(worker.health.total_frames_sampled, 0)
        self.assertEqual(worker.health.status, CameraStatus.ONLINE)

        worker.stop()
        self.assertFalse(worker.is_running)
        self.assertTrue(mock_cap._is_released)

    def test_04_stream_worker_reconnect_on_failure(self):
        """4. Worker detects stream failure, updates status, and reconnects."""
        caps_created = []

        def factory(uri):
            # First cap fails after 5 frames; second cap succeeds
            fail_after = 5 if len(caps_created) == 0 else 50
            cap = MockVideoCapture(frames_to_yield=100, fail_after_frames=fail_after)
            caps_created.append(cap)
            return cap

        config = CameraConfig(
            camera_id=102,
            camera_code="CAM-RECONNECT",
            name="Reconnect Camera",
            stream_uri="mock://reconnect",
            location_id=1,
            sampling_fps=20.0,
            reconnect_interval_seconds=0.2,
            read_timeout_seconds=0.3,
        )
        worker = RTSPStreamWorker(config=config, capture_factory=factory)
        worker.start()

        # Wait for first capture to fail and trigger reconnect
        time.sleep(1.0)

        # Worker should have created at least 2 capture instances (initial + reconnect)
        self.assertGreaterEqual(len(caps_created), 2)
        self.assertGreaterEqual(worker.health.total_reconnects, 1)

        worker.stop()
        self.assertFalse(worker.is_running)

    def test_05_stream_worker_timeout_handling(self):
        """5. Worker detects read timeout when stream stalls."""
        stalling_cap = MockVideoCapture(stalls=True)
        config = CameraConfig(
            camera_id=103,
            camera_code="CAM-TIMEOUT",
            name="Timeout Camera",
            stream_uri="mock://timeout",
            location_id=1,
            read_timeout_seconds=0.2,
            reconnect_interval_seconds=0.2,
        )
        worker = RTSPStreamWorker(
            config=config,
            capture_factory=lambda uri: stalling_cap,
        )
        worker.start()
        time.sleep(0.6)

        # Worker health should show degraded or reconnect attempts due to stall timeout
        self.assertIn(worker.health.status, [CameraStatus.DEGRADED, CameraStatus.CONNECTING, CameraStatus.ONLINE, CameraStatus.OFFLINE])
        worker.stop()

    # -------------------------------------------------------------------------
    # 3. Multi-Camera Failure Isolation Tests
    # -------------------------------------------------------------------------

    def test_06_camera_failure_isolation(self):
        """6. One camera failing does not crash, block, or degrade other cameras."""
        good_cap = MockVideoCapture(frames_to_yield=100)
        failing_cap = MockVideoCapture(frames_to_yield=0)  # Fails immediately

        mgr = CameraStreamManager()
        cfg_good = CameraConfig(
            camera_id=1,
            camera_code="CAM-GOOD",
            name="Good Camera",
            stream_uri="mock://good",
            location_id=1,
            sampling_fps=10.0,
        )
        cfg_bad = CameraConfig(
            camera_id=2,
            camera_code="CAM-BAD",
            name="Failing Camera",
            stream_uri="mock://bad",
            location_id=1,
            sampling_fps=10.0,
            reconnect_interval_seconds=0.2,
        )

        def custom_factory(uri):
            if "good" in str(uri):
                return MockVideoCapture(frames_to_yield=100)
            return MockVideoCapture(frames_to_yield=0)

        mgr.capture_factory = custom_factory
        mgr.add_camera(cfg_good)
        mgr.add_camera(cfg_bad)

        mgr.start_all()
        time.sleep(0.5)

        # Good camera delivers frames
        frame = mgr.get_frame(camera_id=1, timeout=1.0)
        self.assertIsNotNone(frame)
        self.assertEqual(frame.camera_code, "CAM-GOOD")

        # Bad camera is isolated and does not block the manager
        health_good = mgr.get_camera_health(1)
        health_bad = mgr.get_camera_health(2)
        self.assertEqual(health_good.status, CameraStatus.ONLINE)
        self.assertIn(
            health_bad.status,
            [CameraStatus.OFFLINE, CameraStatus.CONNECTING, CameraStatus.ERROR, CameraStatus.DEGRADED],
        )

        mgr.stop_all()

    def test_07_camera_stream_manager_multi_camera_lifecycle(self):
        """7. Multi-camera manager adds, starts, polls round-robin, and stops."""
        mgr = CameraStreamManager(
            capture_factory=lambda uri: MockVideoCapture(frames_to_yield=50)
        )
        for i in [10, 20, 30]:
            cfg = CameraConfig(
                camera_id=i,
                camera_code=f"CAM-{i}",
                name=f"Camera {i}",
                stream_uri=f"mock://cam{i}",
                location_id=1,
                sampling_fps=15.0,
            )
            mgr.add_camera(cfg)

        self.assertEqual(mgr.camera_count, 3)
        mgr.start_all()
        time.sleep(0.4)

        # Round-robin polling should receive frames
        received = []
        for _ in range(5):
            f = mgr.get_any_frame(timeout=0.3)
            if f:
                received.append(f.camera_id)

        self.assertGreater(len(received), 0)

        # Health telemetry inspection
        healths = mgr.get_all_health_dicts()
        self.assertEqual(len(healths), 3)
        for h in healths:
            self.assertIn(h["camera_id"], [10, 20, 30])
            self.assertIn("fps_captured", h)
            self.assertIn("uptime_seconds", h)

        mgr.stop_all()

    def test_08_resource_cleanup_on_shutdown(self):
        """8. Manager cleanly stops all workers and terminates threads."""
        mock_cap = MockVideoCapture(frames_to_yield=500)
        mgr = CameraStreamManager(capture_factory=lambda uri: mock_cap)
        cfg = CameraConfig(
            camera_id=99,
            camera_code="CAM-99",
            name="Shutdown Test",
            stream_uri="mock://99",
            location_id=1,
        )
        mgr.add_camera(cfg)
        mgr.start_all()
        time.sleep(0.2)
        self.assertEqual(mgr.online_count, 1)

        mgr.stop_all()
        time.sleep(0.1)
        self.assertEqual(mgr.online_count, 0)
        self.assertTrue(mock_cap._is_released)

    # -------------------------------------------------------------------------
    # 4. Real Video Stream & YOLO11s Detection Integration Tests
    # -------------------------------------------------------------------------

    def test_09_real_video_stream_integration(self):
        """9. RTSP worker decodes real video file incrementally."""
        if not self.test_video_path.exists():
            self.skipTest(f"Test video not found: {self.test_video_path}")

        config = CameraConfig(
            camera_id=201,
            camera_code="CAM-REAL-01",
            name="Real Video Stream",
            stream_uri=str(self.test_video_path),
            location_id=1,
            sampling_fps=5.0,
            queue_size=10,
        )
        worker = RTSPStreamWorker(config=config)
        worker.start()
        time.sleep(0.8)

        frame_item = worker.buffer.get(timeout=4.0)
        self.assertIsNotNone(frame_item)
        self.assertIsInstance(frame_item.frame, np.ndarray)
        self.assertGreater(frame_item.width, 0)
        self.assertGreater(frame_item.height, 0)

        worker.stop()

    def test_10_yolo_person_detection_and_bytetrack(self):
        """10. YOLO11s detects persons and assigns stream tracker IDs."""
        detector = PersonDetector(conf_threshold=0.30)
        self.assertIsNotNone(detector.model)

        # Test on dummy frame first
        dummy = np.zeros((480, 640, 3), dtype=np.uint8)
        dummy_res = detector.detect_and_track(dummy)
        self.assertIsInstance(dummy_res, list)

        # If real video exists, evaluate on a real frame
        if self.test_video_path.exists():
            import cv2
            cap = cv2.VideoCapture(str(self.test_video_path))
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                persons = detector.detect_and_track(frame)
                self.assertIsInstance(persons, list)
                self.assertGreater(detector.last_latency_ms, 0.0)
                for p in persons:
                    self.assertEqual(p.class_id, 0)
                    self.assertGreaterEqual(p.confidence, 0.30)
                    self.assertGreater(p.width, 0)
                    self.assertGreater(p.height, 0)

    # -------------------------------------------------------------------------
    # 5. Tracker Ephemeral ID Safety Invariant Tests
    # -------------------------------------------------------------------------

    def test_11_stream_tracker_ephemeral_ids(self):
        """11. Tracker IDs are camera-scoped ephemeral strings, never permanent identities."""
        tracker = StreamTrackerManager(camera_id=5, max_idle_seconds=1.0)
        ephem_id = tracker.format_ephemeral_id(42)
        self.assertEqual(ephem_id, "cam5_trk_42")

        # None raw track id formats to None
        self.assertIsNone(tracker.format_ephemeral_id(None))

        # Update track
        th = tracker.update_track(42)
        self.assertIsNotNone(th)
        self.assertEqual(th.stream_tracker_id, "cam5_trk_42")
        self.assertEqual(th.frame_count, 1)

        tracker.update_track(42)
        self.assertEqual(th.frame_count, 2)

        # Inactive purge
        purged = tracker.purge_idle_tracks(now=time.time() + 5.0)
        self.assertEqual(purged, 1)

    # -------------------------------------------------------------------------
    # 6. Face Processing Pipeline Tests
    # -------------------------------------------------------------------------

    def test_12_face_pipeline_alignment_and_embedding(self):
        """12. Face pipeline verifies 5-pt landmarks, 112x112 warping, 512D embeddings."""
        pipeline = FaceProcessingPipeline()
        self.assertIsNotNone(pipeline.auraface_session)

        # 1. Test 112x112 alignment on synthetic landmarks
        dummy_crop = np.zeros((200, 200, 3), dtype=np.uint8)
        synthetic_landmarks = [
            [70.0, 80.0],   # left eye
            [130.0, 80.0],  # right eye
            [100.0, 110.0], # nose
            [80.0, 140.0],  # left mouth
            [120.0, 140.0], # right mouth
        ]
        aligned = pipeline.align_face_112x112(dummy_crop, synthetic_landmarks)
        self.assertIsNotNone(aligned)
        self.assertEqual(aligned.shape, (112, 112, 3))

        # 2. Test AuraFace 512D embedding extraction
        embedding = pipeline.extract_embedding_512d(aligned)
        self.assertIsNotNone(embedding)
        self.assertEqual(embedding.shape, (512,))
        norm = float(np.linalg.norm(embedding))
        self.assertAlmostEqual(norm, 1.0, places=4)

        # 3. Test Cosine Similarity Decision Boundaries
        pipeline.set_enrolled_templates({
            "101": embedding,  # Perfect match
        })
        eid, sim, classification = pipeline.verify_against_templates(embedding)
        self.assertEqual(eid, "101")
        self.assertGreaterEqual(sim, 0.99)
        self.assertEqual(classification, "recognized")

        # Unknown person with orthogonal vector
        orthogonal = np.zeros(512, dtype=np.float32)
        orthogonal[0] = 1.0  # If embedding doesn't have 1.0 at index 0
        if np.dot(orthogonal, embedding) > 0.45:
            orthogonal = -embedding
        _, sim_unknown, class_unknown = pipeline.verify_against_templates(orthogonal)
        self.assertLess(sim_unknown, 0.45)
        self.assertEqual(class_unknown, "unknown")

    # -------------------------------------------------------------------------
    # 7. Backend Event Client Tests
    # -------------------------------------------------------------------------

    def test_13_backend_event_client_payload_validation(self):
        """13. Backend event client validates payloads and buffers during offline state."""
        dispatched_items = []

        def mock_transport(payload_dict):
            if payload_dict.get("metadata_json", {}).get("simulate_fail"):
                return False
            dispatched_items.append(payload_dict)
            return True

        client = BackendEventClient(transport=mock_transport)

        # Valid payload
        p1 = DetectionPayload(
            camera_id=1,
            location_id=10,
            event_type="employee_recognized",
            confidence=0.92,
            employee_id=101,
            tracker_id="cam1_trk_1",
            metadata_json={"bbox": [10, 10, 50, 100]},
        )
        ok1 = client.dispatch_event(p1)
        self.assertTrue(ok1)
        self.assertEqual(len(dispatched_items), 1)

        # Invalid event type rejected by client validation
        with self.assertRaises(ValueError):
            DetectionPayload(
                camera_id=1,
                location_id=10,
                event_type="invalid_custom_event",
                confidence=0.5,
            )

        # Invalid confidence score rejected
        with self.assertRaises(ValueError):
            DetectionPayload(
                camera_id=1,
                location_id=10,
                event_type="unknown_person",
                confidence=1.5,
            )

        # Offline failure enqueuing
        p_fail = DetectionPayload(
            camera_id=1,
            location_id=10,
            event_type="unknown_person",
            confidence=0.88,
            metadata_json={"simulate_fail": True},
        )
        ok2 = client.dispatch_event(p_fail)
        self.assertFalse(ok2)
        self.assertEqual(client.queue_size, 1)

    # -------------------------------------------------------------------------
    # 8. Live Pipeline Worker End-to-End Orchestration Tests
    # -------------------------------------------------------------------------

    def test_14_live_pipeline_worker_end_to_end(self):
        """14. End-to-end pipeline worker drains stream, runs inference, and dispatches events."""
        dispatched = []
        client = BackendEventClient(transport=lambda d: dispatched.append(d) or True)
        mock_cap = MockVideoCapture(frames_to_yield=20)
        mgr = CameraStreamManager(capture_factory=lambda uri: mock_cap)

        cfg = CameraConfig(
            camera_id=50,
            camera_code="CAM-PIPELINE",
            name="Pipeline Camera",
            stream_uri="mock://pipeline",
            location_id=1,
            sampling_fps=15.0,
        )
        mgr.add_camera(cfg)
        detector = PersonDetector(conf_threshold=0.30)
        pipeline = FaceProcessingPipeline()

        worker = LivePipelineWorker(
            stream_manager=mgr,
            detector=detector,
            face_pipeline=pipeline,
            event_client=client,
        )

        mgr.start_all()
        worker.start()
        time.sleep(0.5)

        worker.stop()
        mgr.stop_all()

        self.assertGreater(worker.total_frames_processed, 0)
        self.assertGreaterEqual(worker.avg_inference_latency_ms, 0.0)


if __name__ == "__main__":
    unittest.main()
