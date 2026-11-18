"""
Backend Configuration Synchronizer
Pulls live camera inventory, stream configurations, and workstation polygon zones
from FastAPI backend REST endpoints to keep edge AI pipelines synchronized.
"""

import logging
import os
from typing import Any, Callable
import requests

from ai_engine.stream.camera_config import CameraConfig
from ai_engine.analytics.polygon import PolygonZone
from ai_engine.config import DEFAULT_BACKEND_URL
from ai_engine.utils.security import sanitize_stream_uri

logger = logging.getLogger(__name__)


class BackendConfigClient:
    """
    HTTP client for synchronizing camera and zone configuration from backend API.
    Endpoints consumed:
      - POST /api/v1/auth/login (JWT token issuance)
      - GET /api/v1/cameras (paginated camera registry)
      - GET /api/v1/cameras/{id} (single camera details)
      - GET /api/v1/zones (paginated workstation zones with normalized polygons)
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BACKEND_URL,
        email: str | None = None,
        password: str | None = None,
        auth_token: str | None = None,
        timeout: float = 5.0,
        uri_resolver: Callable[[str | None, dict[str, Any]], str] | dict[str, str] | None = None,
        request_adapter: Callable[[str, str, dict[str, Any] | None, dict[str, Any] | None], dict[str, Any]] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.email = email or os.getenv("EDGE_SERVICE_EMAIL")
        self.password = password or os.getenv("EDGE_SERVICE_PASSWORD")
        self.auth_token = auth_token or os.getenv("EDGE_SERVICE_TOKEN")
        self.timeout = timeout
        self.uri_resolver = uri_resolver
        self.request_adapter = request_adapter

    def _get_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def login(self, email: str | None = None, password: str | None = None) -> bool:
        """Authenticate with backend API and obtain JWT Bearer access token."""
        login_email = email or self.email
        login_password = password or self.password

        if not login_email or not login_password:
            logger.debug("No credentials provided for backend login.")
            return False

        url = f"{self.base_url}/api/v1/auth/login"
        payload = {"email": login_email, "password": login_password}

        if self.request_adapter is not None:
            try:
                res = self.request_adapter("POST", url, headers=None, json=payload)
                token = res.get("access_token")
                if token:
                    self.auth_token = token
                    return True
                return False
            except Exception as e:
                logger.error("Mock adapter login failed: %s", e)
                return False

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                self.auth_token = data.get("access_token")
                logger.info("Successfully authenticated edge client as '%s'.", login_email)
                return True
            else:
                logger.warning("Backend authentication failed (HTTP %d): %s", resp.status_code, resp.text)
                return False
        except Exception as e:
            logger.error("Failed to connect to auth endpoint %s: %s", url, e)
            return False

    def _http_get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Perform authenticated GET request with auto-retry on 401/403."""
        url = f"{self.base_url}{path}"

        if self.request_adapter is not None:
            return self.request_adapter("GET", url, headers=self._get_headers(), json=params)

        if not self.auth_token and self.email and self.password:
            self.login()

        try:
            resp = requests.get(url, headers=self._get_headers(), params=params, timeout=self.timeout)

            # Auto re-login on token expiration or unauthenticated status
            if resp.status_code in (401, 403) and self.email and self.password:
                logger.info("Authentication required or expired (HTTP %d). Attempting re-authentication...", resp.status_code)
                if self.login():
                    resp = requests.get(url, headers=self._get_headers(), params=params, timeout=self.timeout)

            if resp.status_code == 200:
                return resp.json()
            else:
                logger.warning("GET %s returned HTTP %d: %s", path, resp.status_code, resp.text)
                return None
        except Exception as e:
            logger.error("Network error during GET %s: %s", path, e)
            return None

    def resolve_stream_uri(self, secret_ref: str | None, camera_data: dict[str, Any]) -> str:
        """
        Resolve a camera's physical stream URI from secret manager or environment mapping.
        Never logs plaintext passwords or tokens.
        """
        # 1. Custom Callable or Dict Resolver
        if callable(self.uri_resolver):
            return self.uri_resolver(secret_ref, camera_data)
        elif isinstance(self.uri_resolver, dict) and secret_ref:
            if secret_ref in self.uri_resolver:
                return self.uri_resolver[secret_ref]

        # 2. Environment Variable Resolution (e.g. secret_ref="CAM_01_URI")
        if secret_ref:
            env_val = os.getenv(secret_ref)
            if env_val:
                return env_val

        # 3. Fallbacks based on camera code or stream type
        code = camera_data.get("camera_code", "cam")
        env_cam_code = os.getenv(f"RTSP_{code.upper()}_URI")
        if env_cam_code:
            return env_cam_code

        stream_type = camera_data.get("stream_type", "rtsp")
        if stream_type == "webcam":
            return "0"
        elif stream_type == "file":
            return f"storage/test_video_{code}.mp4"

        # Safe local mock default
        return f"rtsp://localhost:8554/{code}"

    def fetch_cameras(
        self,
        location_id: int | None = None,
        is_active: bool = True,
        page_size: int = 100,
    ) -> list[CameraConfig]:
        """
        Synchronize registered camera inventory from backend API.
        Handles pagination and returns CameraConfig instances ready for CameraStreamManager.
        """
        cameras: list[CameraConfig] = []
        page = 1

        while True:
            params: dict[str, Any] = {"page": page, "size": page_size}
            if location_id is not None:
                params["location_id"] = location_id
            if is_active is not None:
                params["is_active"] = is_active

            data = self._http_get("/api/v1/cameras", params=params)
            if not data or "items" not in data:
                break

            items = data["items"]
            for c in items:
                try:
                    cid = c["id"]
                    code = c["camera_code"]
                    name = c.get("name", code)
                    loc_id = c["location_id"]
                    role = c.get("camera_role", "general")
                    secret_ref = c.get("stream_secret_ref")
                    active_flag = c.get("is_active", True)

                    stream_uri = self.resolve_stream_uri(secret_ref, c)

                    config = CameraConfig(
                        camera_id=cid,
                        camera_code=code,
                        name=name,
                        stream_uri=stream_uri,
                        location_id=loc_id,
                        camera_role=role,
                        is_active=active_flag,
                    )
                    cameras.append(config)
                    logger.debug(
                        "Synchronized camera %s (ID %d) at location %d [URI: %s]",
                        code,
                        cid,
                        loc_id,
                        sanitize_stream_uri(stream_uri),
                    )
                except Exception as e:
                    logger.error("Failed to parse camera config from API item %s: %s", c, e)

            total = data.get("total", len(items))
            if len(cameras) >= total or not items:
                break
            page += 1

        logger.info("Successfully synchronized %d cameras from backend API.", len(cameras))
        return cameras

    def fetch_workstation_zones(
        self,
        camera_id: int | None = None,
        location_id: int | None = None,
        is_active: bool = True,
        page_size: int = 100,
    ) -> list[PolygonZone]:
        """
        Synchronize registered workstation zones and polygon geometries.
        Handles pagination and returns PolygonZone instances ready for MultiZoneManager.
        """
        zones: list[PolygonZone] = []
        page = 1

        while True:
            params: dict[str, Any] = {"page": page, "size": page_size}
            if camera_id is not None:
                params["camera_id"] = camera_id
            if location_id is not None:
                params["location_id"] = location_id
            if is_active is not None:
                params["is_active"] = is_active

            data = self._http_get("/api/v1/zones", params=params)
            if not data or "items" not in data:
                break

            items = data["items"]
            for z in items:
                try:
                    zid = z["id"]
                    zcode = z["zone_code"]
                    name = z.get("name", zcode)
                    cid = z["camera_id"]
                    loc_id = z["location_id"]
                    poly_points = z["polygon_points"]
                    inactivity_sec = float(z.get("inactivity_threshold_seconds", 900.0))
                    active_flag = z.get("is_active", True)

                    # Validate polygon format: list of [x, y] tuples
                    polygon_tuple_list = [(float(pt[0]), float(pt[1])) for pt in poly_points]

                    zone = PolygonZone(
                        zone_id=zid,
                        zone_code=zcode,
                        name=name,
                        camera_id=cid,
                        location_id=loc_id,
                        polygon_points=polygon_tuple_list,
                        inactivity_threshold_seconds=inactivity_sec,
                        is_active=active_flag,
                    )
                    zones.append(zone)
                    logger.debug(
                        "Synchronized workstation zone '%s' (ID %d, Cam %d, %d vertices)",
                        zcode,
                        zid,
                        cid,
                        len(polygon_tuple_list),
                    )
                except Exception as e:
                    logger.error("Failed to parse zone from API item %s: %s", z, e)

            total = data.get("total", len(items))
            if len(zones) >= total or not items:
                break
            page += 1

        logger.info("Successfully synchronized %d workstation zones from backend API.", len(zones))
        return zones

    def sync_all(
        self,
        location_id: int | None = None,
    ) -> tuple[list[CameraConfig], list[PolygonZone]]:
        """Synchronize both cameras and workstation zones in a unified call."""
        cameras = self.fetch_cameras(location_id=location_id)
        zones = self.fetch_workstation_zones(location_id=location_id)
        return cameras, zones
