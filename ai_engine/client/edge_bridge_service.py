"""
Edge Bridge Client for AI Engine Client Library
Provides an HTTP client for interacting with the Edge Frame Access Bridge microservice (127.0.0.1:8001).
Can be utilized by external tools, test harnesses, and FastAPI bridge services.
"""

import logging
from typing import AsyncIterator, Any
import httpx

logger = logging.getLogger(__name__)

DEFAULT_EDGE_FRAME_URL = "http://127.0.0.1:8001"


class EdgeBridgeService:
    """
    Client for querying the loopback Edge Frame Server.
    Provides snapshot retrieval, MJPEG chunk streaming, and health status reporting.
    """

    def __init__(self, base_url: str = DEFAULT_EDGE_FRAME_URL, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def get_snapshot(
        self,
        camera_id: int,
        quality: int = 80,
        max_age: float = 5.0,
    ) -> tuple[bytes, dict[str, str]]:
        """Fetch raw JPEG bytes and telemetry headers for a given camera."""
        url = f"{self.base_url}/internal/cameras/{camera_id}/snapshot"
        params = {"quality": quality, "max_age": max_age}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()

            headers = {
                "Content-Type": "image/jpeg",
                "Cache-Control": resp.headers.get("Cache-Control", "no-cache, no-store, must-revalidate"),
            }
            for h in ("X-Camera-ID", "X-Camera-Code", "X-Frame-Timestamp", "X-Camera-Status", "X-Frame-Age-Ms"):
                if h in resp.headers:
                    headers[h] = resp.headers[h]
            return resp.content, headers

    async def stream_mjpeg(
        self,
        camera_id: int,
        fps: int = 15,
        quality: int = 75,
        max_frames: int | None = None,
    ) -> AsyncIterator[bytes]:
        """Stream multipart/x-mixed-replace MJPEG bytes from the edge server."""
        url = f"{self.base_url}/internal/cameras/{camera_id}/stream"
        params = {"fps": fps, "quality": quality}
        if max_frames is not None:
            params["max_frames"] = max_frames

        client_timeout = httpx.Timeout(connect=self.timeout, read=None, write=self.timeout, pool=self.timeout)
        async with httpx.AsyncClient(timeout=client_timeout) as client:
            async with client.stream("GET", url, params=params) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk

    async def get_edge_health(self) -> dict[str, Any]:
        """Fetch health telemetry from edge frame server."""
        url = f"{self.base_url}/internal/health"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()


# Default singleton instance
edge_bridge_client = EdgeBridgeService()
