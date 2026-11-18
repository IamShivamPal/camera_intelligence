"""
Inactivity & Optical Flow Motion Energy Detector
Measures pixel displacement and frame intensity changes to distinguish
meaningful employee workstation movement from static inactivity and sensor noise.
"""

import logging
import time
from typing import Any
import cv2
import numpy as np

from ai_engine.config import (
    DEFAULT_MOTION_MAGNITUDE_THRESHOLD,
    DEFAULT_DIFF_INTENSITY_THRESHOLD,
)

logger = logging.getLogger(__name__)

# Standardized ROI resolution for scale-invariant optical flow calculation
STANDARDIZED_ROI_SHAPE = (128, 128)


class InactivityDetector:
    """
    Computes movement energy within a designated ROI (person bounding box or workstation polygon)
    using Farneback Dense Optical Flow and Temporal Frame Differencing.
    
    Rationale:
      - Camera sensor noise and global lighting flicker produce micro-displacements (< 0.4 px).
      - Micro-movements like typing, mouse movement, and posture adjustments produce
        localized optical flow vectors with average magnitude >= 0.8 px and intensity diff >= 2.5.
    """

    def __init__(
        self,
        motion_threshold: float = DEFAULT_MOTION_MAGNITUDE_THRESHOLD,
        diff_threshold: float = DEFAULT_DIFF_INTENSITY_THRESHOLD,
    ):
        self.motion_threshold = motion_threshold
        self.diff_threshold = diff_threshold

        self._prev_gray: np.ndarray | None = None
        self._last_timestamp: float | None = None
        self._last_active_timestamp: float | None = None
        self._accumulated_idle_seconds: float = 0.0

    @property
    def accumulated_idle_seconds(self) -> float:
        return self._accumulated_idle_seconds

    @property
    def last_active_timestamp(self) -> float | None:
        return self._last_active_timestamp

    @staticmethod
    def compute_motion_energy(
        prev_gray: np.ndarray,
        curr_gray: np.ndarray,
        motion_threshold: float = DEFAULT_MOTION_MAGNITUDE_THRESHOLD,
        diff_threshold: float = DEFAULT_DIFF_INTENSITY_THRESHOLD,
    ) -> tuple[float, float, bool]:
        """
        Compute optical flow magnitude and absolute difference intensity between two grayscale images.
        Returns: (mean_optical_flow_magnitude, mean_intensity_difference, is_active)
        """
        if prev_gray is None or curr_gray is None or prev_gray.size == 0 or curr_gray.size == 0:
            return 0.0, 0.0, False

        # Resize to standardized shape for scale-invariant motion measurement
        prev_std = cv2.resize(prev_gray, STANDARDIZED_ROI_SHAPE, interpolation=cv2.INTER_AREA)
        curr_std = cv2.resize(curr_gray, STANDARDIZED_ROI_SHAPE, interpolation=cv2.INTER_AREA)

        # Global illumination compensation (rejects lighting flicker and auto-exposure shifts)
        shift = np.mean(curr_std.astype(np.float32) - prev_std.astype(np.float32))
        curr_adj = np.clip(curr_std.astype(np.float32) - shift, 0, 255).astype(np.uint8)

        # 1. Temporal Frame Differencing (localized pixel luminance changes)
        abs_diff = cv2.absdiff(prev_std, curr_adj)
        mean_diff = float(np.mean(abs_diff))

        # 2. Farneback Dense Optical Flow (velocity vectors u, v)
        flow = cv2.calcOpticalFlowFarneback(
            prev=prev_std,
            next=curr_std,
            flow=None,
            pyr_scale=0.5,
            levels=2,
            winsize=11,
            iterations=2,
            poly_n=5,
            poly_sigma=1.1,
            flags=0,
        )
        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        mean_mag = float(np.mean(mag))

        # Motion decision: Significant if either vector velocity or localized pixel difference crosses threshold
        is_active = (mean_mag >= motion_threshold) or (mean_diff >= diff_threshold)
        return mean_mag, mean_diff, is_active

    def update(
        self,
        roi_bgr: np.ndarray,
        timestamp: float | None = None,
    ) -> tuple[bool, float, float]:
        """
        Ingest the next ROI frame and update inactivity accumulation.
        Returns:
          - is_active (bool): True if meaningful movement was detected
          - motion_magnitude (float): Mean optical flow vector length in pixels
          - accumulated_idle_seconds (float): Duration of continuous inactivity
        """
        now = timestamp or time.time()

        if roi_bgr is None or roi_bgr.size == 0:
            return False, 0.0, self._accumulated_idle_seconds

        # Convert to single-channel 8-bit grayscale
        if roi_bgr.ndim == 3:
            curr_gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
        else:
            curr_gray = roi_bgr.copy()

        # Initial frame in sequence
        if self._prev_gray is None or self._last_timestamp is None:
            self._prev_gray = curr_gray
            self._last_timestamp = now
            self._last_active_timestamp = now
            self._accumulated_idle_seconds = 0.0
            return True, 0.0, 0.0

        # Calculate delta time between consecutive updates
        dt = max(0.0, now - self._last_timestamp)
        self._last_timestamp = now

        mean_mag, mean_diff, is_active = self.compute_motion_energy(
            prev_gray=self._prev_gray,
            curr_gray=curr_gray,
            motion_threshold=self.motion_threshold,
            diff_threshold=self.diff_threshold,
        )
        self._prev_gray = curr_gray

        if is_active:
            # Meaningful movement detected -> reset inactivity counter
            self._last_active_timestamp = now
            self._accumulated_idle_seconds = 0.0
        else:
            # Below movement threshold -> accumulate inactive duration
            self._accumulated_idle_seconds += dt

        return is_active, mean_mag, self._accumulated_idle_seconds

    def reset(self):
        """Reset internal history and inactivity counters."""
        self._prev_gray = None
        self._last_timestamp = None
        self._last_active_timestamp = None
        self._accumulated_idle_seconds = 0.0
