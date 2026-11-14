import argparse
import sys
from pathlib import Path

import cv2
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_face_alignment import (
    load_retinaface,
    detect_faces,
    align_face,
    DEVICE,
)


def main():
    parser = argparse.ArgumentParser(
        description="Align an unknown person's face using RetinaFace."
    )
    parser.add_argument(
        "--image",
        type=Path,
        required=True,
        help="Path to the original face image."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "runs/face_alignment/unknown_01_aligned.jpg",
        help="Output path for the aligned face."
    )
    args = parser.parse_args()

    if DEVICE.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable. Activate the AI virtual environment.")

    image_path = args.image if args.image.is_absolute() else ROOT / args.image
    output_path = args.output if args.output.is_absolute() else ROOT / args.output

    if not image_path.exists():
        raise FileNotFoundError(f"Input image not found: {image_path}")

    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f"Could not read image: {image_path}")

    img_h, img_w = image.shape[:2]
    print(f"Loaded image: {image_path} ({img_w}x{img_h})")

    model, cfg = load_retinaface()
    faces = detect_faces(model, cfg, image)

    if not faces:
        raise RuntimeError("No faces detected in the image.")

    # Sort descending by bounding box area and pick the largest face >= 80x80
    faces.sort(
        key=lambda face: (
            (face["box"][2] - face["box"][0])
            * (face["box"][3] - face["box"][1])
        ),
        reverse=True
    )

    selected_face = None
    for face in faces:
        x1, y1, x2, y2 = face["box"]
        face_w = x2 - x1
        face_h = y2 - y1
        if face_w >= 80 and face_h >= 80:
            selected_face = face
            break

    if selected_face is None:
        raise RuntimeError("No face with dimensions >= 80x80 found.")

    aligned = align_face(image, selected_face["landmarks"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), aligned)

    x1, y1, x2, y2 = selected_face["box"]
    print("\n========== ALIGNMENT RESULTS ==========")
    print(f"Input dimensions: {img_w}x{img_h}")
    print(f"Face confidence: {selected_face['confidence']:.3f}")
    print(f"Original face box: {selected_face['box']} ({x2 - x1}x{y2 - y1} px)")
    print(f"Aligned dimensions: {aligned.shape}")
    print(f"Saved: {output_path}")
    print("\nUnknown face alignment completed successfully.")


if __name__ == "__main__":
    main()

