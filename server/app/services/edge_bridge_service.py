"""
Edge Bridge Service
Facilitates secure communication between FastAPI backend and Edge Frame Access Bridge microservice.
Proxies JPEG snapshots and MJPEG streaming chunks without opening duplicate RTSP connections.
"""

import logging
from typing import AsyncIterator, Any
import httpx
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)


class EdgeBridgeService:
    """
    Bridge service for routing live video requests to the Edge Frame Server (127.0.0.1:8001).
    Ensures zero frame accumulation, graceful disconnects, and accurate error reporting.
    """

    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or settings.EDGE_FRAME_SERVER_URL).rstrip("/")
        self.timeout = timeout or settings.EDGE_FRAME_TIMEOUT_SECONDS

    async def get_snapshot(
        self,
        camera_id: int,
        quality: int = 80,
        max_age: float = 5.0,
    ) -> tuple[bytes, dict[str, str]]:
        """
        Fetch a single decoded JPEG snapshot from the edge server.
        Returns: (raw_jpeg_bytes, response_headers)
        """
        url = f"{self.base_url}/internal/cameras/{camera_id}/snapshot"
        params = {"quality": quality, "max_age": max_age}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params)

                if resp.status_code == 200:
                    headers = {
                        "Content-Type": "image/jpeg",
                        "Cache-Control": resp.headers.get("Cache-Control", "no-cache, no-store, must-revalidate"),
                        "Pragma": "no-cache",
                    }
                    for h in ("X-Camera-ID", "X-Camera-Code", "X-Frame-Timestamp", "X-Camera-Status", "X-Frame-Age-Ms"):
                        if h in resp.headers:
                            headers[h] = resp.headers[h]
                    return resp.content, headers

                elif resp.status_code == 404:
                    detail = resp.json().get("detail", f"Camera ID {camera_id} is not registered on Edge service.")
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

                elif resp.status_code == 503:
                    detail = resp.json().get("detail", f"Camera ID {camera_id} stream is currently unavailable.")
                    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)

                elif resp.status_code == 429:
                    detail = resp.json().get("detail", "Viewer limit exceeded for this camera stream.")
                    raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)

                else:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Edge frame server returned unexpected status code: {resp.status_code}",
                    )

        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            logger.warning("Failed to connect to edge frame server at %s: %s", self.base_url, e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Edge Ingestion Service is currently offline or unreachable. Please verify edge worker is running.",
            )
        except httpx.TimeoutException as e:
            logger.warning("Timeout waiting for snapshot from edge frame server: %s", e)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Timeout waiting for frame from Edge Ingestion Service.",
            )

    async def stream_mjpeg(
        self,
        camera_id: int,
        fps: int = 15,
        quality: int = 75,
        max_frames: int | None = None,
    ) -> AsyncIterator[bytes]:
        """
        Asynchronously proxy an MJPEG multipart video stream from the edge server.
        Decrements active viewers automatically when client disconnects.
        """
        url = f"{self.base_url}/internal/cameras/{camera_id}/stream"
        params: dict[str, Any] = {"fps": fps, "quality": quality}
        if max_frames is not None:
            params["max_frames"] = max_frames

        # Use no read timeout for persistent streaming connection
        client_timeout = httpx.Timeout(connect=self.timeout, read=None, write=self.timeout, pool=self.timeout)

        try:
            async with httpx.AsyncClient(timeout=client_timeout) as client:
                async with client.stream("GET", url, params=params) as response:
                    if response.status_code == 404:
                        detail = (await response.aread()).decode()
                        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail or "Camera not found on edge service.")

                    if response.status_code == 503:
                        detail = (await response.aread()).decode()
                        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail or "Camera stream is offline.")

                    if response.status_code == 429:
                        detail = (await response.aread()).decode()
                        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail or "Maximum concurrent viewers reached.")

                    if response.status_code != 200:
                        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Edge stream returned status {response.status_code}")

                    async for chunk in response.aiter_bytes():
                        yield chunk

        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            logger.warning("Cannot connect to edge frame server for MJPEG stream (camera %d): %s", camera_id, e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Edge Ingestion Service is currently offline or unreachable.",
            )
        except Exception as e:
            logger.debug("MJPEG stream client disconnected for camera %d: %s", camera_id, e)

    async def get_edge_health(self) -> dict[str, Any]:
        """Query telemetry and active viewer counts from edge frame server."""
        url = f"{self.base_url}/internal/health"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.json()
                return {"status": "degraded", "edge_status_code": resp.status_code}
        except Exception as e:
            logger.debug("Edge health query failed: %s", e)
            return {"status": "unreachable", "error": str(e)}


# Global instance
edge_bridge_service = EdgeBridgeService()
