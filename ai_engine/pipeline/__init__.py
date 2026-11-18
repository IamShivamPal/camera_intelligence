"""
AI Detection, Tracking, and Recognition Pipeline.
"""

from ai_engine.pipeline.detector import PersonDetector, TrackedPerson
from ai_engine.pipeline.tracker import StreamTrackerManager, TrackHistory
from ai_engine.pipeline.face_pipeline import FaceProcessingPipeline, FaceRecognitionResult
from ai_engine.pipeline.pipeline_worker import LivePipelineWorker

__all__ = [
    "PersonDetector",
    "TrackedPerson",
    "StreamTrackerManager",
    "TrackHistory",
    "FaceProcessingPipeline",
    "FaceRecognitionResult",
    "LivePipelineWorker",
]
