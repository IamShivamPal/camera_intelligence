"""
Security & Data Sanitization Utilities
Ensures credentials and sensitive biometric/frame data are protected.
"""

import re
from typing import Any

# Forbidden payload keys that must never be transmitted or written to telemetry logs/queues
FORBIDDEN_PAYLOAD_KEYS = {
    "embedding",
    "embeddings",
    "feature_vector",
    "face_vector",
    "biometric_vector",
    "raw_frame",
    "raw_image",
    "frame_bgr",
    "crop",
    "crop_image",
    "face_crop",
    "image_bytes",
    "frame_bytes",
}


def sanitize_stream_uri(uri: str | None) -> str:
    """
    Mask credentials embedded in stream URIs (e.g. RTSP, HTTP).
    Example:
      'rtsp://admin:SecretPass123@192.168.1.50:554/stream1'
      -> 'rtsp://admin:***@192.168.1.50:554/stream1'
      'http://10.0.0.1/live?access_token=Secret'
      -> 'http://10.0.0.1/live?access_token=***'
    """
    if not uri or not isinstance(uri, str):
        return ""
    # Mask user:password@
    sanitized = re.sub(r"://([^:/@]+):([^@]+)@", r"://\1:***@", uri)
    # Mask single-token user@
    sanitized = re.sub(r"://([^:/@?#]+)@", r"://***@", sanitized)
    # Mask sensitive query params (token, key, secret, password)
    sanitized = re.sub(
        r"([?&](?:token|access_token|api_key|key|secret|password)=)[^&#]+",
        r"\1***",
        sanitized,
        flags=re.IGNORECASE,
    )
    return sanitized


def scrub_biometrics_and_frames(data: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively scrub any raw video frames, crops, or raw biometric embedding vectors
    from a dictionary before telemetry persistence or network transmission.
    """
    if not isinstance(data, dict):
        return data

    cleaned: dict[str, Any] = {}
    for key, value in data.items():
        k_lower = key.lower().strip()
        if k_lower in FORBIDDEN_PAYLOAD_KEYS:
            continue

        if isinstance(value, dict):
            cleaned[key] = scrub_biometrics_and_frames(value)
        elif isinstance(value, list):
            # Check for large raw numeric vectors (e.g. 512D embeddings) mistakenly placed in lists
            if k_lower in ("vectors", "embeddings", "crops"):
                continue
            cleaned[key] = [
                scrub_biometrics_and_frames(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            cleaned[key] = value

    return cleaned
