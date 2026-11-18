"""
Person Detection & Stream Tracking with Ultralytics YOLO11s & ByteTrack
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import numpy as np
import torch
from ultralytics import YOLO

from ai_engine.config import YOLO_MODEL_PATH, PERSON_CONFIDENCE_THRESHOLD, PERSON_CLASS_ID

logger = logging.getLogger(__name__)


@dataclass
class TrackedPerson:
    """Detection box, confidence, and tracking metadata for a detected person."""
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    tracker_id: int | None = None
    class_id: int = PERSON_CLASS_ID
    recognized_employee_id: int | None = None

    @property
    def box_xyxy(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def bottom_center(self) -> tuple[float, float]:
        """Base contact point (feet location) for spatial polygon containment."""
        return ((self.x1 + self.x2) / 2.0, self.y2)

    def extract_crop(self, frame: np.ndarray) -> np.ndarray:
        """Extract person bounding box crop from the source frame safely."""
        h, w = frame.shape[:2]
        ix1 = max(0, min(int(self.x1), w - 1))
        iy1 = max(0, min(int(self.y1), h - 1))
        ix2 = max(ix1 + 1, min(int(self.x2), w))
        iy2 = max(iy1 + 1, min(int(self.y2), h))
        return frame[iy1:iy2, ix1:ix2]


class PersonDetector:
    """
    YOLO11s Person Detector and ByteTrack Tracker.
    Optimized for streaming GPU inference with automatic device selection.
    """

    def __init__(
        self,
        model_path: str | Path = YOLO_MODEL_PATH,
        conf_threshold: float = PERSON_CONFIDENCE_THRESHOLD,
        device: str | int | None = None,
        tracker_config: str = "bytetrack.yaml",
    ):
        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold
        self.tracker_config = tracker_config

        if not self.model_path.exists():
            raise FileNotFoundError(f"YOLO11s model weights not found at: {self.model_path}")

        # Device determination
        if device is not None:
            self.device = device
        elif torch.cuda.is_available():
            self.device = 0
        else:
            self.device = "cpu"

        logger.info("Loading YOLO11s from %s on device=%s", self.model_path, self.device)
        self.model = YOLO(str(self.model_path))
        self._last_latency_ms: float = 0.0

    @property
    def last_latency_ms(self) -> float:
        return self._last_latency_ms

    def detect_and_track(
        self,
        frame: np.ndarray,
        persist: bool = True,
    ) -> list[TrackedPerson]:
        """
        Run YOLO11s detection + ByteTrack tracking on a single video frame.
        Streaming mode: Processes only the given frame incrementally without buffering.
        Filters strictly for class_id = 0 (person) and confidence >= conf_threshold.
        """
        if frame is None or frame.size == 0:
            return []

        start_time = time.perf_counter()

        try:
            results = self.model.track(
                source=frame,
                stream=False,
                persist=persist,
                tracker=self.tracker_config,
                classes=[PERSON_CLASS_ID],
                device=self.device,
                conf=self.conf_threshold,
                verbose=False,
            )
        except Exception as e:
            logger.error("YOLO track error on frame: %s", e)
            return []
        finally:
            self._last_latency_ms = (time.perf_counter() - start_time) * 1000.0

        if not results:
            return []

        res = results[0]
        if res.boxes is None or len(res.boxes) == 0:
            return []

        boxes = res.boxes.xyxy.cpu().numpy()
        confs = res.boxes.conf.cpu().numpy()

        track_ids = None
        if res.boxes.id is not None:
            track_ids = res.boxes.id.int().cpu().numpy()

        persons: list[TrackedPerson] = []
        for i in range(len(boxes)):
            tid = int(track_ids[i]) if track_ids is not None else None
            persons.append(
                TrackedPerson(
                    x1=float(boxes[i][0]),
                    y1=float(boxes[i][1]),
                    x2=float(boxes[i][2]),
                    y2=float(boxes[i][3]),
                    confidence=float(confs[i]),
                    tracker_id=tid,
                )
            )

        return persons
