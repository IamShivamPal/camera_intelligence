"""
AI Engine Global Configuration & Validated Thresholds
Camera Intelligence Platform
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
# Base directories
AI_ENGINE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = AI_ENGINE_DIR.parent

def _check_cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False

def _get_cuda_device_name() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0)
    except Exception:
        pass
    return "CPU"

# Model Paths
YOLO_MODEL_PATH = AI_ENGINE_DIR / "models" / "detection" / "yolo11s.pt"
RETINAFACE_MODEL_PATH = AI_ENGINE_DIR / "models" / "face" / "retinaface_r34.pth"
AURAFACE_MODEL_PATH = AI_ENGINE_DIR / "models" / "face" / "auraface_v1_glintr100.onnx"
RETINAFACE_THIRD_PARTY_DIR = AI_ENGINE_DIR / "third_party" / "retinaface-pytorch"
DEFAULT_TEMPLATE_PATH = PROJECT_ROOT / "runs" / "employee_enrollment" / "employee_templates.npz"

# Validated Detection & Recognition Thresholds (from docs/handover/AI_ENGINE_GUIDE.md)
PERSON_CONFIDENCE_THRESHOLD = 0.45
PERSON_CLASS_ID = 0  # COCO class 0: Person

FACE_CONFIDENCE_THRESHOLD = 0.60
FACE_NMS_THRESHOLD = 0.40
FACE_MIN_SIZE_PIXELS = 24  # Minimum width/height for face landmarking

# Biometric Verification Decision Boundaries
COSINE_MATCH_THRESHOLD = 0.60     # S >= 0.60: Genuine employee match
COSINE_AMBIGUOUS_THRESHOLD = 0.45 # 0.45 <= S < 0.60: Ambiguous / unverified
# S < 0.45: Unknown person

# Canonical ArcFace 112x112 5-point reference coordinates
REFERENCE_5PTS = [
    [38.2946, 51.6963],   # Left eye
    [73.5318, 51.5014],   # Right eye
    [56.0252, 71.7366],   # Nose tip
    [41.5493, 92.3655],   # Left mouth corner
    [70.7299, 92.2041],   # Right mouth corner
]

# Streaming & Buffer Defaults
DEFAULT_SAMPLING_FPS = 5.0
DEFAULT_FRAME_QUEUE_SIZE = 15
DEFAULT_READ_TIMEOUT_SECONDS = 5.0
DEFAULT_RECONNECT_INTERVAL_SECONDS = 3.0
DEFAULT_MAX_RECONNECT_ATTEMPTS = 0  # 0 = infinite retry with backoff

# Workstation Analytics & Inactivity Defaults
DEFAULT_INACTIVITY_THRESHOLD_SECONDS = 900.0  # Default 15 minutes matching WorkstationZone schema
DEFAULT_OCCLUSION_TOLERANCE_SECONDS = 5.0     # Tolerance window before declaring occupant absent
DEFAULT_CAMERA_DISCONNECT_GRACE_PERIOD_SECONDS = 10.0  # Reconnect grace period before camera disconnect reset
DEFAULT_MOTION_MAGNITUDE_THRESHOLD = 0.8      # Mean Farneback optical flow magnitude (pixels)
DEFAULT_DIFF_INTENSITY_THRESHOLD = 2.5        # Mean absolute pixel intensity change [0..255]

# Backend API Defaults
DEFAULT_BACKEND_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
API_EVENTS_ENDPOINT = f"{DEFAULT_BACKEND_URL}/api/v1/events"


@dataclass
class EngineConfig:
    """Runtime engine hardware and inference configuration."""
    use_cuda: bool = field(default_factory=_check_cuda_available)
    device_name: str = field(default_factory=_get_cuda_device_name)
    device_id: int = 0
    yolo_model_path: Path = YOLO_MODEL_PATH
    retinaface_model_path: Path = RETINAFACE_MODEL_PATH
    auraface_model_path: Path = AURAFACE_MODEL_PATH
    person_confidence: float = PERSON_CONFIDENCE_THRESHOLD
    face_confidence: float = FACE_CONFIDENCE_THRESHOLD
    cosine_match_threshold: float = COSINE_MATCH_THRESHOLD
    cosine_ambiguous_threshold: float = COSINE_AMBIGUOUS_THRESHOLD
    sampling_fps: float = DEFAULT_SAMPLING_FPS
    queue_size: int = DEFAULT_FRAME_QUEUE_SIZE
    read_timeout_seconds: float = DEFAULT_READ_TIMEOUT_SECONDS
    reconnect_interval_seconds: float = DEFAULT_RECONNECT_INTERVAL_SECONDS
