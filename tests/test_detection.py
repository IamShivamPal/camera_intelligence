from pathlib import Path
import torch
from ultralytics import YOLO

print("Loading YOLO11s...")

# Dynamically resolve path to the model weights
model_path = Path(__file__).resolve().parent.parent / "ai_engine" / "models" / "detection" / "yolo11s.pt"
if not model_path.exists():
    model_path = Path("models/detection/yolo11s.pt")

model = YOLO(str(model_path))

print("Running GPU detection test...")

test_image = Path(__file__).resolve().parent.parent / "bus.jpg"
image_source = str(test_image) if test_image.exists() else "https://ultralytics.com/images/bus.jpg"

results = model.predict(
    source=image_source,
    device=0,
    conf=0.5,
    save=True
)

print("\nDetection completed!")
print("GPU:", torch.cuda.get_device_name(0))
print("Detected objects:")

for result in results:
    for box in result.boxes:
        class_id = int(box.cls[0])
        confidence = float(box.conf[0])

        print(
            f"{model.names[class_id]} "
            f"- Confidence: {confidence:.2f}"
        )