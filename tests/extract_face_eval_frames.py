import cv2
from pathlib import Path

VIDEO_PATH = Path("1.mp4")
OUTPUT_DIR = Path("tests/face_eval_frames")
SAMPLE_COUNT = 40

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

cap = cv2.VideoCapture(str(VIDEO_PATH))
if not cap.isOpened():
    raise RuntimeError("Could not open 1.mp4")

total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
if total_frames == 0:
    raise RuntimeError("Video contains no readable frames")

sample_indices = [
    round(i * (total_frames - 1) / (SAMPLE_COUNT - 1))
    for i in range(SAMPLE_COUNT)
]

for frame_number in sample_indices:
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()
    if not ret:
        print(f"Could not read frame {frame_number}")
        continue
    output_path = OUTPUT_DIR / f"frame_{frame_number:04d}.jpg"
    cv2.imwrite(str(output_path), frame)
    print(f"Saved: {output_path}")

cap.release()

print(f"\nExtraction complete. Total video frames: {total_frames}")
print(f"Evaluation frames saved in: {OUTPUT_DIR}")

