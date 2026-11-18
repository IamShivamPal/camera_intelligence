"""
Edge Frame Access Bridge & Internal Streaming Microservice
Serves low-latency camera snapshots and MJPEG video streams over loopback interface (127.0.0.1).
Reuses existing RTSP stream workers without duplicating camera connections.
"""

import asyncio
import logging
import threading
import time
from typing import Any
import cv2
from fastapi import FastAPI, HTTPException, Query, Response, Request, status
from fastapi.responses import StreamingResponse
import uvicorn

from ai_engine.stream.stream_manager import CameraStreamManager
from ai_engine.stream.camera_config import CameraStatus

logger = logging.getLogger(__name__)


def create_edge_frame_app(
    stream_manager: CameraStreamManager,
    max_viewers_per_camera: int = 10,
    sync_handler: Any = None,
) -> FastAPI:
    """Factory to create the internal loopback frame bridge ASGI application."""
    app = FastAPI(
        title="Edge Frame Access Bridge",
        description="Internal loopback video frame delivery microservice",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
    )

    # Active viewer counters per camera ID: {camera_id: count}
    active_viewers: dict[int, int] = {}
    viewer_lock = threading.Lock()

    @app.get("/internal/health")
    def get_internal_health():
        """Return live health metrics and viewer telemetry for all camera streams."""
        with viewer_lock:
            viewers_snapshot = dict(active_viewers)
        return {
            "status": "healthy",
            "camera_count": stream_manager.camera_count,
            "online_count": stream_manager.online_count,
            "active_viewers": viewers_snapshot,
            "cameras": stream_manager.get_all_health_dicts(),
        }

    @app.get("/internal/cameras/{camera_id}/snapshot")
    def get_snapshot(
        camera_id: int,
        quality: int = Query(default=80, ge=30, le=100, description="JPEG compression quality"),
        max_age: float = Query(default=5.0, ge=0.5, le=30.0, description="Max frame age in seconds"),
    ):
        """
        Retrieve a single fresh JPEG frame from the existing RTSP worker buffer.
        Never opens a new RTSP connection.
        """
        with stream_manager._lock:
            worker = stream_manager._workers.get(camera_id)

        if not worker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Camera ID {camera_id} is not registered in Edge Ingestion Service.",
            )

        if worker.health.status not in (CameraStatus.ONLINE, CameraStatus.DEGRADED):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Camera '{worker.config.camera_code}' is currently {worker.health.status.value.upper()}.",
            )

        frame_item = stream_manager.get_latest_frame(camera_id, max_age_seconds=max_age)
        if frame_item is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"No fresh frame available for camera '{worker.config.camera_code}' (older than {max_age}s or offline).",
            )

        # Encode frame to JPEG
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        ret, jpeg_buffer = cv2.imencode(".jpg", frame_item.frame, encode_params)
        if not ret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to encode frame into JPEG format.",
            )

        age_ms = round((time.time() - frame_item.timestamp) * 1000.0, 1)

        headers = {
            "Content-Type": "image/jpeg",
            "X-Camera-ID": str(camera_id),
            "X-Camera-Code": worker.config.camera_code,
            "X-Frame-ID": str(frame_item.frame_id),
            "X-Frame-Timestamp": str(frame_item.timestamp),
            "X-Frame-Age-Ms": str(age_ms),
            "X-Camera-Status": worker.health.status.value,
            "Cache-Control": "no-cache, no-store, must-revalidate",
        }

        return Response(content=jpeg_buffer.tobytes(), media_type="image/jpeg", headers=headers)

    @app.get("/internal/cameras/{camera_id}/stream")
    async def get_mjpeg_stream(
        request: Request,
        camera_id: int,
        fps: float = Query(default=5.0, ge=0.5, le=30.0, description="Streaming frame rate limit"),
        quality: int = Query(default=75, ge=30, le=100, description="JPEG quality"),
        max_age: float = Query(default=5.0, ge=1.0, le=30.0, description="Max frame staleness"),
        max_frames: int | None = Query(default=None, ge=1, description="Optional maximum frames limit"),
    ):
        """
        Stream live multipart/x-mixed-replace MJPEG video from the existing frame buffer.
        Enforces concurrent viewer limits and performs zero redundant JPEG encoding.
        """
        with stream_manager._lock:
            worker = stream_manager._workers.get(camera_id)

        if not worker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Camera ID {camera_id} is not registered in Edge Ingestion Service.",
            )

        if worker.health.status not in (CameraStatus.ONLINE, CameraStatus.DEGRADED):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Camera '{worker.config.camera_code}' is currently {worker.health.status.value.upper()}.",
            )

        # Enforce viewer limit
        with viewer_lock:
            current_viewers = active_viewers.get(camera_id, 0)
            if current_viewers >= max_viewers_per_camera:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Maximum concurrent viewers limit ({max_viewers_per_camera}) reached for camera {worker.config.camera_code}.",
                )
            active_viewers[camera_id] = current_viewers + 1

        logger.info(
            "New MJPEG viewer connected to camera %s (Active viewers: %d/%d)",
            worker.config.camera_code,
            active_viewers[camera_id],
            max_viewers_per_camera,
        )

        interval = 1.0 / max(0.5, min(fps, 30.0))
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]

        async def mjpeg_frame_generator():
            last_timestamp = 0.0
            frames_yielded = 0
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    if max_frames is not None and frames_yielded >= max_frames:
                        break

                    frame_item = stream_manager.get_latest_frame(camera_id, max_age_seconds=max_age)

                    if frame_item is not None and frame_item.timestamp != last_timestamp:
                        last_timestamp = frame_item.timestamp

                        # Encode to JPEG
                        ret, buffer = cv2.imencode(".jpg", frame_item.frame, encode_params)
                        if ret:
                            jpeg_bytes = buffer.tobytes()
                            boundary_part = (
                                b"--frame\r\n"
                                b"Content-Type: image/jpeg\r\n"
                                b"Content-Length: " + str(len(jpeg_bytes)).encode() + b"\r\n"
                                b"X-Timestamp: " + str(frame_item.timestamp).encode() + b"\r\n\r\n"
                                + jpeg_bytes + b"\r\n"
                            )
                            yield boundary_part
                            frames_yielded += 1

                    await asyncio.sleep(interval)
            except (asyncio.CancelledError, GeneratorExit):
                logger.debug("Client disconnected from camera %s MJPEG stream.", worker.config.camera_code)
            finally:
                with viewer_lock:
                    if camera_id in active_viewers:
                        active_viewers[camera_id] = max(0, active_viewers[camera_id] - 1)
                        logger.info(
                            "MJPEG viewer disconnected from camera %s (Remaining: %d)",
                            worker.config.camera_code,
                            active_viewers[camera_id],
                        )

        return StreamingResponse(
            mjpeg_frame_generator(),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "X-Camera-ID": str(camera_id),
                "X-Camera-Code": worker.config.camera_code,
            },
        )

    @app.post("/internal/sync")
    def trigger_sync():
        """Trigger immediate configuration sync."""
        if sync_handler:
            res = sync_handler()
            return {"status": "sync_triggered", "result": res}
        return {"status": "no_sync_handler"}

    return app


class EdgeFrameServer:
    """
    Manager for the background loopback frame server.
    Spins up uvicorn in a dedicated daemon thread.
    """

    def __init__(
        self,
        stream_manager: CameraStreamManager,
        host: str = "127.0.0.1",
        port: int = 8001,
        max_viewers_per_camera: int = 10,
        sync_handler: Any = None,
    ):
        self.host = host
        self.port = port
        self.stream_manager = stream_manager
        self.app = create_edge_frame_app(
            stream_manager=stream_manager,
            max_viewers_per_camera=max_viewers_per_camera,
            sync_handler=sync_handler,
        )
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    def start(self):
        """Start the internal frame server on localhost."""
        if self._thread and self._thread.is_alive():
            return

        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)

        self._thread = threading.Thread(
            target=self._server.run,
            name="EdgeFrameServer",
            daemon=True,
        )
        self._thread.start()
        logger.info("Started Edge Frame Access Server on http://%s:%d", self.host, self.port)

    def stop(self):
        """Gracefully terminate the internal frame server."""
        if self._server:
            self._server.should_exit = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("Edge Frame Access Server stopped.")
