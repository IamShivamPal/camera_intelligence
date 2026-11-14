import cv2
from pathlib import Path
import math
import numpy as np

INPUT_DIR = Path("tests/face_eval_frames")
OUTPUT_PATH = Path("tests/face_eval_contact_sheet.jpg")
IMAGE_WIDTH = 320
IMAGE_HEIGHT = 180
LABEL_HEIGHT = 28
COLUMNS = 4

image_paths = sorted(INPUT_DIR.glob("frame_*.jpg"))
if not image_paths:
    raise RuntimeError("No evaluation frames found.")

rows = math.ceil(len(image_paths) / COLUMNS)
canvas = np.full(
    (rows * (IMAGE_HEIGHT + LABEL_HEIGHT), COLUMNS * IMAGE_WIDTH, 3),
    255,
    dtype=np.uint8
)

for index, path in enumerate(image_paths):
    image = cv2.imread(str(path))
    if image is None:
        continue
    image = cv2.resize(image, (IMAGE_WIDTH, IMAGE_HEIGHT))

    col = index % COLUMNS
    row = index // COLUMNS

    x = col * IMAGE_WIDTH
    y = row * (IMAGE_HEIGHT + LABEL_HEIGHT)

    canvas[y : y + IMAGE_HEIGHT, x : x + IMAGE_WIDTH] = image

    # Add frame label text
    label = path.name
    cv2.putText(
        canvas,
        label,
        (x + 10, y + IMAGE_HEIGHT + 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 0, 0),
        1,
        cv2.LINE_AA
    )

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
cv2.imwrite(str(OUTPUT_PATH), canvas)
print(f"Contact sheet successfully created: {OUTPUT_PATH}")
print(f"Total frames included: {len(image_paths)}")
print(f"Grid dimensions: {COLUMNS} columns x {rows} rows ({canvas.shape[1]}x{canvas.shape[0]} px)")

