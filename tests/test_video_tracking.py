from ultralytics import YOLO
import torch

model = YOLO("ai_engine/models/detection/yolo11s.pt")

print("GPU:", torch.cuda.get_device_name(0))
print("Starting video tracking...")

results = model.track(
    source="1.mp4",
    tracker="bytetrack.yaml",
    classes=[0],
    conf=0.4,
    device=0,
    persist=True,
    show=True,
    save=True
)

print("Video tracking completed!")