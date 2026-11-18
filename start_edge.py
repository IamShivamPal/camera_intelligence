import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

from ai_engine.pipeline.detector import PersonDetector
from ai_engine.service import EdgeIngestionService

print("Initializing Edge Ingestion Service...")

detector = PersonDetector()
service = EdgeIngestionService(
    detector=detector,
    enable_periodic_sync=True
)

service.register_signal_handlers()
service.start(sync_config=True)

print("[OK] Edge Ingestion Service is running.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopping Edge Ingestion Service...")
    service.stop()
    print("[OK] Shutdown complete.")
