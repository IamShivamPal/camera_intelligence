
import cv2
import torch
from ultralytics import YOLO
import time

MODEL_PATH = "ai_engine/models/detection/yolo11s.pt"
VIDEO_PATH = "1.mp4"

# COCO class 0 = person
PERSON_CLASS = [0]

model = YOLO(MODEL_PATH)

print("CUDA available:", torch.cuda.is_available())

if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))

results = model.track(
    source=VIDEO_PATH,
    stream=True,
    persist=True,
    tracker="bytetrack.yaml",
    classes=PERSON_CLASS,
    device=0,
    conf=0.40,
    verbose=False
)

frame_count = 0
start_time = time.time()
seen_track_ids = set()

try:
    for result in results:
        frame_count += 1

        if result.boxes is not None and result.boxes.id is not None:
            track_ids = result.boxes.id.int().cpu().tolist()
            seen_track_ids.update(track_ids)

            print(
                f"Frame {frame_count} | "
                f"People: {len(track_ids)} | "
                f"IDs: {track_ids}"
            )
        else:
            print(f"Frame {frame_count} | People: 0")

        frame = result.plot()
        cv2.imshow("Person Tracking", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    cv2.destroyAllWindows()

elapsed = time.time() - start_time

print("\n--- Tracking Summary ---")
print("Frames processed:", frame_count)
print("Unique temporary track IDs:", len(seen_track_ids))
print("Total processing time:", round(elapsed, 2), "seconds")
print("Average FPS:", round(frame_count / elapsed, 2))
