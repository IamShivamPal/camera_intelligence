"""
Stream Tracking & Ephemeral Identifier Management
"""

import time
from dataclasses import dataclass, field


@dataclass
class TrackHistory:
    """Ephemeral temporal history of a single tracker ID in a camera stream."""
    stream_tracker_id: str
    camera_id: int
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    frame_count: int = 1
    recognized_employee_id: int | None = None
    recognition_confidence: float | None = None

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.last_seen - self.first_seen)

    def update(self, timestamp: float | None = None):
        self.last_seen = timestamp or time.time()
        self.frame_count += 1


class StreamTrackerManager:
    """
    Manages stream-scoped tracker identifiers.
    
    SAFETY INVARIANT:
    Tracker IDs (e.g. from ByteTrack) are strictly temporary per-stream metadata.
    They MUST NEVER be used as a persistent employee identity.
    """

    def __init__(self, camera_id: int, max_idle_seconds: float = 30.0):
        self.camera_id = camera_id
        self.max_idle_seconds = max_idle_seconds
        self._tracks: dict[int, TrackHistory] = {}

    def format_ephemeral_id(self, raw_track_id: int | None) -> str | None:
        """Create a stream-prefixed ephemeral tracker string."""
        if raw_track_id is None:
            return None
        return f"cam{self.camera_id}_trk_{raw_track_id}"

    def update_track(
        self,
        raw_track_id: int | None,
        timestamp: float | None = None,
    ) -> TrackHistory | None:
        if raw_track_id is None:
            return None

        now = timestamp or time.time()
        track = self._tracks.get(raw_track_id)
        if track is None:
            track = TrackHistory(
                stream_tracker_id=self.format_ephemeral_id(raw_track_id),
                camera_id=self.camera_id,
                first_seen=now,
                last_seen=now,
            )
            self._tracks[raw_track_id] = track
        else:
            track.update(now)

        return track

    def purge_idle_tracks(self, now: float | None = None) -> int:
        """Remove tracks that have left the stream view beyond idle threshold."""
        current_time = now or time.time()
        to_delete = [
            tid
            for tid, track in self._tracks.items()
            if (current_time - track.last_seen) > self.max_idle_seconds
        ]
        for tid in to_delete:
            del self._tracks[tid]
        return len(to_delete)

    def clear(self):
        self._tracks.clear()
