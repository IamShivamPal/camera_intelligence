from ultralytics import YOLO

model = YOLO("ai_engine/models/detection/yolo11s.pt")

results = model.track(
    source="https://ultralytics.com/images/bus.jpg",
    tracker="bytetrack.yaml",
    classes=[0],  # Person only
    conf=0.4,
    device=0,
    save=True,
    show=False
)

for result in results:
    if result.boxes.id is not None:
        for box, track_id in zip(
            result.boxes,
            result.boxes.id
        ):
            print(
                f"Person Track ID: {int(track_id)} "
                f"Confidence: {float(box.conf[0]):.2f}"
            )

print("Person tracking test completed!")


