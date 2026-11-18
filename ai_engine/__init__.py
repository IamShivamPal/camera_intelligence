"""
Camera Intelligence — AI Engine
Production-grade RTSP streaming, person tracking, biometric recognition,
and persistent edge ingestion service.
"""

from ai_engine.service import EdgeIngestionService, ServiceStatus
from ai_engine.client.persistent_dispatcher import PersistentTelemetryDispatcher
from ai_engine.client.config_client import BackendConfigClient

__version__ = "1.0.0"

__all__ = [
    "EdgeIngestionService",
    "ServiceStatus",
    "PersistentTelemetryDispatcher",
    "BackendConfigClient",
]
