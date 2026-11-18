"""
Persistent Telemetry Dispatcher
Crash-resilient, bounded, local SQLite-backed event dispatcher with exponential backoff retries,
duplicate prevention, and guaranteed biometric/frame scrubbing.
"""

import json
import logging
import os
import random
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable
import requests

from ai_engine.client.event_client import DetectionPayload
from ai_engine.config import API_EVENTS_ENDPOINT
from ai_engine.utils.security import scrub_biometrics_and_frames

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_DB_PATH = Path("runs/telemetry_queue.db")
DEFAULT_MAX_QUEUE_ITEMS = 5000
DEFAULT_BASE_BACKOFF = 1.0
DEFAULT_MAX_BACKOFF = 60.0
DEFAULT_BACKOFF_MULTIPLIER = 2.0


class PersistentTelemetryDispatcher:
    """
    Robust local-first telemetry dispatcher.
    Features:
      - Bounded local SQLite queue (WAL mode): survives backend crashes, reboots, and network drops.
      - Confirmed deletion: rows are removed only after verified HTTP 200/201 response.
      - Exponential backoff with random jitter to prevent retry storms.
      - Idempotent tracking: attaches a client_event_id to eliminate duplicates.
      - Preserves FIFO ordering of detection events where practical.
      - Strict scrubbing: never persists or transmits raw video frames or 512D biometric vectors.
    """

    def __init__(
        self,
        endpoint_url: str = API_EVENTS_ENDPOINT,
        auth_token: str | None = None,
        db_path: str | Path | None = None,
        max_queue_items: int = DEFAULT_MAX_QUEUE_ITEMS,
        base_backoff_seconds: float = DEFAULT_BASE_BACKOFF,
        max_backoff_seconds: float = DEFAULT_MAX_BACKOFF,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
        timeout: float = 3.0,
        transport: Callable[[dict[str, Any]], bool] | None = None,
        auto_start: bool = True,
    ):
        self.endpoint_url = endpoint_url
        self.auth_token = auth_token
        self.max_queue_items = max_queue_items
        self.base_backoff_seconds = base_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.backoff_multiplier = backoff_multiplier
        self.timeout = timeout
        self.transport = transport

        # Database setup
        raw_db_path = db_path or os.getenv("TELEMETRY_QUEUE_PATH", str(DEFAULT_QUEUE_DB_PATH))
        self.is_memory_db = str(raw_db_path) == ":memory:"
        if not self.is_memory_db:
            self.db_path = Path(raw_db_path).resolve()
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db_conn_str = str(self.db_path)
        else:
            self._db_conn_str = ":memory:"

        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            self._db_conn_str,
            check_same_thread=False,
            timeout=15.0,
        )
        self._init_db()

        # Telemetry & Operational Metrics
        self.total_enqueued = 0
        self.total_dispatched = 0
        self.total_retried = 0
        self.total_dropped = 0
        self.consecutive_failures = 0

        # Background worker thread
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._worker_thread: threading.Thread | None = None

        if auto_start:
            self.start()

    def _init_db(self):
        """Initialize database schema with WAL mode and indices."""
        with self._lock:
            cur = self._conn.cursor()
            if not self.is_memory_db:
                cur.execute("PRAGMA journal_mode = WAL;")
                cur.execute("PRAGMA synchronous = NORMAL;")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_event_id TEXT UNIQUE NOT NULL,
                    camera_id INTEGER NOT NULL,
                    location_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    retry_count INTEGER DEFAULT 0,
                    next_retry_at REAL DEFAULT 0.0,
                    created_at REAL NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_pending_retry 
                ON pending_events(next_retry_at, id);
                """
            )
            self._conn.commit()

    def start(self):
        """Start the background dispatch worker thread."""
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._dispatch_loop,
            name="PersistentTelemetryDispatcher",
            daemon=True,
        )
        self._worker_thread.start()
        logger.info("PersistentTelemetryDispatcher started (queue=%s).", self._db_conn_str)

    def stop(self, timeout: float = 3.0):
        """Gracefully stop the background worker thread."""
        self._stop_event.set()
        self._wake_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
        logger.info("PersistentTelemetryDispatcher stopped.")

    def close(self):
        """Stop worker and release database resources."""
        self.stop()
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass

    def enqueue(self, payload: DetectionPayload) -> str:
        """
        Persist a detection event to the local queue.
        Guarantees:
          - Assigns an idempotent client_event_id.
          - Scrubs all raw video frames and biometric vectors.
          - Enforces queue bounding by dropping oldest events if queue is full.
        Returns the client_event_id.
        """
        payload_dict = payload.to_dict()

        # 1. Strict Biometric & Frame Scrubbing
        scrubbed = scrub_biometrics_and_frames(payload_dict)

        # 2. Idempotency Key
        meta = scrubbed.get("metadata_json") or {}
        client_event_id = meta.get("client_event_id") or str(uuid.uuid4())
        meta["client_event_id"] = client_event_id
        scrubbed["metadata_json"] = meta

        now = time.time()
        payload_str = json.dumps(scrubbed)

        with self._lock:
            cur = self._conn.cursor()

            # 3. Enforce Bounded Queue Capacity
            cur.execute("SELECT COUNT(*) FROM pending_events")
            current_count = cur.fetchone()[0]

            if current_count >= self.max_queue_items:
                overflow = (current_count - self.max_queue_items) + 1
                cur.execute(
                    """
                    DELETE FROM pending_events 
                    WHERE id IN (
                        SELECT id FROM pending_events ORDER BY id ASC LIMIT ?
                    )
                    """,
                    (overflow,),
                )
                self.total_dropped += overflow
                logger.warning(
                    "Telemetry queue reached max limit (%d). Dropped %d oldest events.",
                    self.max_queue_items,
                    overflow,
                )

            # 4. Insert Event
            try:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO pending_events (
                        client_event_id, camera_id, location_id, event_type, 
                        occurred_at, payload_json, retry_count, next_retry_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 0, 0.0, ?)
                    """,
                    (
                        client_event_id,
                        payload.camera_id,
                        payload.location_id,
                        payload.event_type,
                        payload.occurred_at or "",
                        payload_str,
                        now,
                    ),
                )
                self._conn.commit()
                self.total_enqueued += 1
            except Exception as e:
                logger.error("Failed to enqueue telemetry event to SQLite: %s", e)

        # Wake worker for immediate processing
        self._wake_event.set()
        return client_event_id

    def dispatch_event(self, payload: DetectionPayload) -> bool:
        """
        LivePipelineWorker compatibility interface:
        Enqueues the event durably to local SQLite and returns True.
        """
        self.enqueue(payload)
        return True

    def flush(self, max_items: int = 100) -> int:
        """
        Synchronously dispatch pending items that are ready.
        Useful during testing or before shutdown.
        Returns the number of successfully delivered events.
        """
        delivered = 0
        now = time.time()

        while delivered < max_items:
            with self._lock:
                cur = self._conn.cursor()
                cur.execute(
                    """
                    SELECT id, client_event_id, payload_json, retry_count 
                    FROM pending_events 
                    WHERE next_retry_at <= ? 
                    ORDER BY id ASC 
                    LIMIT 1
                    """,
                    (now,),
                )
                row = cur.fetchone()

            if not row:
                break

            event_id, client_event_id, payload_json, retry_count = row
            success = self._send_single_event(event_id, client_event_id, payload_json, retry_count)
            if success:
                delivered += 1
            else:
                break

        return delivered

    def _send_single_event(
        self,
        event_id: int,
        client_event_id: str,
        payload_json: str,
        retry_count: int,
    ) -> bool:
        """
        Attempt network delivery of a single queued event.
        Returns True if confirmed accepted by backend, False otherwise.
        """
        payload_dict = json.loads(payload_json)

        # 1. Custom Transport (e.g. Test Mock)
        if self.transport is not None:
            try:
                success = self.transport(payload_dict)
                if success:
                    self._delete_event(event_id)
                    self.total_dispatched += 1
                    self.consecutive_failures = 0
                    return True
                else:
                    self._record_failure(event_id, retry_count)
                    return False
            except Exception as e:
                logger.debug("Mock transport failed: %s", e)
                self._record_failure(event_id, retry_count)
                return False

        # 2. HTTP POST to Backend API
        headers = {
            "Content-Type": "application/json",
            "X-Client-Event-ID": client_event_id,
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        try:
            resp = requests.post(
                self.endpoint_url,
                json=payload_dict,
                headers=headers,
                timeout=self.timeout,
            )

            # Confirmed acceptance (HTTP 200 / 201)
            if resp.status_code in (200, 201):
                self._delete_event(event_id)
                self.total_dispatched += 1
                self.consecutive_failures = 0
                logger.debug(
                    "Dispatched event %s (id=%d) successfully.",
                    client_event_id,
                    event_id,
                )
                return True

            # Client validation error (HTTP 4xx) -> Permanent defect, do not poison queue indefinitely
            elif 400 <= resp.status_code < 500:
                logger.error(
                    "Backend rejected event %s with HTTP %d: %s. Dropping permanently.",
                    client_event_id,
                    resp.status_code,
                    resp.text,
                )
                self._delete_event(event_id)
                self.total_dropped += 1
                return True

            # Server error (HTTP 5xx) -> Temporary outage, apply backoff
            else:
                logger.warning(
                    "Backend returned server error HTTP %d for event %s. Retrying...",
                    resp.status_code,
                    client_event_id,
                )
                self._record_failure(event_id, retry_count)
                return False

        except Exception as e:
            logger.debug(
                "Network exception dispatching event %s: %s. Retrying with backoff.",
                client_event_id,
                e,
            )
            self._record_failure(event_id, retry_count)
            return False

    def _delete_event(self, event_id: int):
        """Remove confirmed event from local SQLite queue."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM pending_events WHERE id = ?", (event_id,))
            self._conn.commit()

    def _record_failure(self, event_id: int, current_retries: int):
        """Update retry count and calculate exponential backoff with jitter."""
        self.total_retried += 1
        self.consecutive_failures += 1

        new_retry_count = current_retries + 1
        # Exponential backoff: base * (multiplier ^ (retry_count - 1))
        exponent = max(0, min(new_retry_count - 1, 10))
        delay = self.base_backoff_seconds * (self.backoff_multiplier ** exponent)
        delay = min(delay, self.max_backoff_seconds)
        # Random jitter: +/- 10%
        jitter = delay * 0.1 * (random.random() * 2 - 1)
        next_retry_at = time.time() + max(0.5, delay + jitter)

        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                UPDATE pending_events 
                SET retry_count = ?, next_retry_at = ? 
                WHERE id = ?
                """,
                (new_retry_count, next_retry_at, event_id),
            )
            self._conn.commit()

    def _dispatch_loop(self):
        """Main dispatcher loop continuously draining the queue."""
        while not self._stop_event.is_set():
            now = time.time()

            with self._lock:
                cur = self._conn.cursor()
                cur.execute(
                    """
                    SELECT id, client_event_id, payload_json, retry_count, next_retry_at 
                    FROM pending_events 
                    ORDER BY next_retry_at ASC, id ASC 
                    LIMIT 1
                    """
                )
                row = cur.fetchone()

            if not row:
                # No events at all -> sleep until woken
                self._wake_event.wait(timeout=1.0)
                self._wake_event.clear()
                continue

            event_id, client_event_id, payload_json, retry_count, next_retry_at = row

            # If the next event's backoff timestamp is in the future
            if next_retry_at > now:
                wait_sec = min(next_retry_at - now, 2.0)
                self._wake_event.wait(timeout=wait_sec)
                self._wake_event.clear()
                continue

            # Attempt delivery
            success = self._send_single_event(event_id, client_event_id, payload_json, retry_count)
            if not success:
                # On failure, wait brief interval before retrying next loop
                time.sleep(min(self.base_backoff_seconds, 1.0))

    @property
    def queue_size(self) -> int:
        """Total number of pending un-dispatched events in local SQLite."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT COUNT(*) FROM pending_events")
            return cur.fetchone()[0]

    def get_metrics(self) -> dict[str, Any]:
        """Telemetry diagnostics for operational monitoring."""
        return {
            "queue_size": self.queue_size,
            "total_enqueued": self.total_enqueued,
            "total_dispatched": self.total_dispatched,
            "total_retried": self.total_retried,
            "total_dropped": self.total_dropped,
            "consecutive_failures": self.consecutive_failures,
            "is_connected": self.consecutive_failures == 0,
            "queue_db_path": str(self._db_conn_str),
        }
