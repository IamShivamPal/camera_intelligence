"""
Workstation Polygon Containment & Coordinate Mapping
Implements Ray-Casting Point-in-Polygon and Normalized-to-Pixel Coordinate Conversion.
"""

import math
from dataclasses import dataclass, field
from typing import Any
import numpy as np
import cv2

from ai_engine.config import DEFAULT_INACTIVITY_THRESHOLD_SECONDS


def ray_casting_contains_point(
    point: tuple[float, float],
    polygon: list[tuple[float, float]],
    boundary_inclusive: bool = True,
    epsilon: float = 1e-6,
) -> bool:
    """
    Ray-Casting Algorithm for 2D Point-in-Polygon test.
    Casts a horizontal ray from point (px, py) towards positive X infinity.
    Counts the number of edge intersections:
      - Odd count  -> Inside
      - Even count -> Outside
    If point lies directly on an edge and boundary_inclusive=True, returns True.
    """
    px, py = point
    n = len(polygon)
    if n < 3:
        return False

    inside = False

    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]

        # Check if point lies directly on segment (x1, y1) - (x2, y2)
        # Cross product to check collinearity + bounding box check
        dx = x2 - x1
        dy = y2 - y1
        cross = (px - x1) * dy - (py - y1) * dx

        if abs(cross) < epsilon:
            # Collinear, check if within bounding box of segment
            if min(x1, x2) - epsilon <= px <= max(x1, x2) + epsilon and \
               min(y1, y2) - epsilon <= py <= max(y1, y2) + epsilon:
                return boundary_inclusive

        # Ray-casting edge crossing condition:
        # One vertex must be strictly below, and one vertex at or above the horizontal ray
        if (y1 > py) != (y2 > py):
            # Calculate exact x-intersection of edge with horizontal line Y = py
            x_intersect = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if px < x_intersect:
                inside = not inside

    return inside


@dataclass
class PolygonZone:
    """
    Spatial workstation polygon zone.
    Stores coordinates in normalized [0.0, 1.0] space and maps them to frame pixels.
    """
    zone_id: int
    zone_code: str
    name: str
    camera_id: int
    location_id: int
    polygon_points: list[tuple[float, float]]  # [(x0, y0), (x1, y1), ...] in [0.0, 1.0]
    assigned_employee_id: int | None = None
    department_id: int | None = None
    inactivity_threshold_seconds: float = DEFAULT_INACTIVITY_THRESHOLD_SECONDS
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if len(self.polygon_points) < 3:
            raise ValueError(f"Polygon zone '{self.zone_code}' must have at least 3 vertices.")
        for idx, pt in enumerate(self.polygon_points):
            x, y = pt
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise ValueError(
                    f"Vertex {idx} ({x}, {y}) in zone '{self.zone_code}' is outside normalized bounds [0.0, 1.0]."
                )
        if self.inactivity_threshold_seconds <= 0:
            raise ValueError(f"inactivity_threshold_seconds must be positive, got {self.inactivity_threshold_seconds}")

    def to_pixel_points(self, frame_width: int, frame_height: int) -> list[tuple[float, float]]:
        """Convert normalized vertices into pixel coordinates (float)."""
        return [
            (x * frame_width, y * frame_height)
            for x, y in self.polygon_points
        ]

    def to_cv2_points(self, frame_width: int, frame_height: int) -> np.ndarray:
        """Convert vertices to int32 numpy array of shape (N, 1, 2) for OpenCV functions."""
        pts = np.array(
            [[round(x * frame_width), round(y * frame_height)] for x, y in self.polygon_points],
            dtype=np.int32,
        )
        return pts.reshape((-1, 1, 2))

    def contains_pixel_point(
        self,
        px: float,
        py: float,
        frame_width: int,
        frame_height: int,
        boundary_inclusive: bool = True,
    ) -> bool:
        """Test if a pixel coordinate lies within this zone polygon."""
        poly_pixels = self.to_pixel_points(frame_width, frame_height)
        return ray_casting_contains_point(
            point=(px, py),
            polygon=poly_pixels,
            boundary_inclusive=boundary_inclusive,
            epsilon=1.0,  # 1 pixel tolerance for boundary edges
        )

    def contains_normalized_point(
        self,
        nx: float,
        ny: float,
        boundary_inclusive: bool = True,
    ) -> bool:
        """Test if a normalized [0.0, 1.0] coordinate lies within the polygon."""
        return ray_casting_contains_point(
            point=(nx, ny),
            polygon=self.polygon_points,
            boundary_inclusive=boundary_inclusive,
            epsilon=1e-5,
        )

    def contains_person_base(
        self,
        box_xyxy: tuple[float, float, float, float],
        frame_width: int,
        frame_height: int,
        boundary_inclusive: bool = True,
    ) -> bool:
        """
        Test if person's bottom-center contact point is inside the workstation polygon.
        Bottom-center point: ((x1 + x2) / 2.0, y2).
        """
        x1, y1, x2, y2 = box_xyxy
        base_x = (x1 + x2) / 2.0
        base_y = y2
        return self.contains_pixel_point(
            px=base_x,
            py=base_y,
            frame_width=frame_width,
            frame_height=frame_height,
            boundary_inclusive=boundary_inclusive,
        )

    def get_pixel_bounding_box(self, frame_width: int, frame_height: int) -> tuple[int, int, int, int]:
        """
        Return the axis-aligned bounding box (x1, y1, x2, y2) in pixels encompassing the zone.
        Clamped to [0, width] and [0, height].
        """
        pts = self.to_pixel_points(frame_width, frame_height)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x1 = max(0, int(math.floor(min(xs))))
        y1 = max(0, int(math.floor(min(ys))))
        x2 = min(frame_width, int(math.ceil(max(xs))))
        y2 = min(frame_height, int(math.ceil(max(ys))))
        return (x1, y1, x2, y2)

    def extract_zone_mask(self, frame_width: int, frame_height: int) -> np.ndarray:
        """Create a binary uint8 mask of the polygon on the full frame."""
        mask = np.zeros((frame_height, frame_width), dtype=np.uint8)
        cv_pts = self.to_cv2_points(frame_width, frame_height)
        cv2.fillPoly(mask, [cv_pts], 255)
        return mask
