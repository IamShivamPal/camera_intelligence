"""
Thread-safe Bounded Frame Buffer with FIFO Dropping for Real-time Streaming
"""

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any
import numpy as np


@dataclass
class FrameItem:
    """Metadata-wrapped video frame passed across pipeline stages."""
    frame: np.ndarray
    frame_id: int
    timestamp: float
    camera_id: int
    camera_code: str
    location_id: int
    camera_role: str = "general"
    metadata: dict[str, Any] | None = None

    @property
    def shape(self) -> tuple[int, ...]:
        return self.frame.shape

    @property
    def height(self) -> int:
        return self.frame.shape[0]

    @property
    def width(self) -> int:
        return self.frame.shape[1]


class BoundedFrameBuffer:
    """
    Thread-safe, bounded frame queue.
    If full when a new frame is inserted, the oldest frame is dropped.
    This guarantees:
      1. Bounded memory consumption (fixed max buffer size).
      2. Minimal streaming latency (inference always gets the most recent frames).
      3. No pipeline stall or blocking on frame ingestion.
    """

    def __init__(self, maxsize: int = 15):
        if maxsize <= 0:
            raise ValueError("Buffer maxsize must be greater than 0")
        self.maxsize = maxsize
        self._deque: deque[FrameItem] = deque(maxlen=maxsize)
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._dropped_count = 0
        self._total_pushed = 0
        self._closed = False

    @property
    def dropped_count(self) -> int:
        with self._lock:
            return self._dropped_count

    @property
    def total_pushed(self) -> int:
        with self._lock:
            return self._total_pushed

    def put(self, item: FrameItem) -> bool:
        """
        Push a frame into the buffer.
        If at capacity, the oldest frame is dropped automatically.
        Returns True if accepted without drop, False if dropped oldest.
        """
        with self._lock:
            if self._closed:
                return False

            self._total_pushed += 1
            dropped = False
            if len(self._deque) >= self.maxsize:
                self._deque.popleft()
                self._dropped_count += 1
                dropped = True

            self._deque.append(item)
            self._not_empty.notify()
            return not dropped

    def get(self, timeout: float | None = 1.0) -> FrameItem | None:
        """
        Retrieve the next available frame, waiting up to `timeout` seconds.
        Returns None if timed out or buffer is closed.
        """
        with self._not_empty:
            end_time = time.time() + (timeout if timeout is not None else 0.0)
            while len(self._deque) == 0:
                if self._closed:
                    return None
                if timeout is None:
                    self._not_empty.wait()
                else:
                    remaining = end_time - time.time()
                    if remaining <= 0:
                        return None
                    self._not_empty.wait(remaining)

            return self._deque.popleft()

    def qsize(self) -> int:
        with self._lock:
            return len(self._deque)

    def is_empty(self) -> bool:
        with self._lock:
            return len(self._deque) == 0

    def clear(self):
        with self._lock:
            self._deque.clear()

    def close(self):
        with self._lock:
            self._closed = True
            self._deque.clear()
            self._not_empty.notify_all()
