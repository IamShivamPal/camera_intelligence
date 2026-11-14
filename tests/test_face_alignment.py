
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

# --------------------------------------------------
# PATH CONFIGURATION
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT / "ai_engine" / "third_party" / "retinaface-pytorch")
)

from config import get_config
from models.retinaface import RetinaFace
from layers.functions.prior_box import PriorBox
from utils.box_utils import decode, decode_landmarks, nms


WEIGHTS_PATH = ROOT / "ai_engine" / "models" / "face" / "retinaface_r34.pth"

VIDEO_PATH = ROOT / "1.mp4"

OUTPUT_DIR = ROOT / "runs" / "face_alignment"
OUTPUT_PATH = OUTPUT_DIR / "aligned_face.jpg"

DEVICE = torch.device("cuda")

CONFIDENCE_THRESHOLD = 0.60
NMS_THRESHOLD = 0.40

RGB_MEAN = (104, 117, 123)

# Standard ArcFace 112x112 reference landmarks.
REFERENCE_LANDMARKS = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32
)


# --------------------------------------------------
# LOAD RETINAFACE
# --------------------------------------------------

def load_retinaface():

    print("Loading RetinaFace ResNet34...")

    if not WEIGHTS_PATH.exists():
        raise FileNotFoundError(WEIGHTS_PATH)

    cfg = get_config("resnet34").copy()
    cfg["pretrain"] = False

    model = RetinaFace(cfg=cfg)

    checkpoint = torch.load(
        WEIGHTS_PATH,
        map_location=DEVICE,
        weights_only=True
    )

    model.load_state_dict(checkpoint)
    model.to(DEVICE)
    model.eval()

    print("RetinaFace loaded on:", torch.cuda.get_device_name(0))

    return model, cfg


# --------------------------------------------------
# DETECT FACES AND LANDMARKS
# --------------------------------------------------

@torch.inference_mode()
def detect_faces(model, cfg, frame):

    height, width = frame.shape[:2]

    image = frame.astype(np.float32)
    image -= np.array(RGB_MEAN, dtype=np.float32)
    image = image.transpose(2, 0, 1)

    tensor = torch.from_numpy(
        np.ascontiguousarray(image)
    ).unsqueeze(0).to(DEVICE)

    loc, conf, landmarks = model(tensor)

    loc = loc.squeeze(0)
    conf = conf.squeeze(0)
    landmarks = landmarks.squeeze(0)

    priors = PriorBox(
        cfg,
        image_size=(height, width)
    ).generate_anchors().to(DEVICE)

    boxes = decode(loc, priors, cfg["variance"])

    landmarks = decode_landmarks(
        landmarks,
        priors,
        cfg["variance"]
    )

    boxes = boxes.cpu().numpy()
    landmarks = landmarks.cpu().numpy()
    scores = conf[:, 1].cpu().numpy()

    scale = np.array(
        [width, height, width, height],
        dtype=np.float32
    )

    landmark_scale = np.array(
        [width, height] * 5,
        dtype=np.float32
    )

    boxes *= scale
    landmarks *= landmark_scale

    indices = np.where(scores > CONFIDENCE_THRESHOLD)[0]

    if len(indices) == 0:
        return []

    boxes = boxes[indices]
    landmarks = landmarks[indices]
    scores = scores[indices]

    detections = np.hstack(
        (boxes, scores[:, None])
    ).astype(np.float32)

    keep = nms(detections, NMS_THRESHOLD)

    results = []

    for index in keep:

        x1, y1, x2, y2 = boxes[index]

        results.append({
            "box": (
                int(max(0, x1)),
                int(max(0, y1)),
                int(min(width - 1, x2)),
                int(min(height - 1, y2))
            ),
            "confidence": float(scores[index]),
            "landmarks": landmarks[index].reshape(5, 2)
        })

    return results


# --------------------------------------------------
# ALIGN FACE USING FIVE LANDMARKS
# --------------------------------------------------

def align_face(image, landmarks):

    landmarks = np.asarray(landmarks, dtype=np.float32)

    if landmarks.shape != (5, 2):
        raise ValueError("Expected five facial landmarks.")

    if not np.isfinite(landmarks).all():
        raise ValueError("Invalid landmark coordinates.")

    transform, _ = cv2.estimateAffinePartial2D(
        landmarks,
        REFERENCE_LANDMARKS,
        method=cv2.LMEDS
    )

    if transform is None:
        raise RuntimeError("Face alignment failed.")

    # Transform the detected landmarks into aligned-face coordinates
    transformed_landmarks = cv2.transform(
        landmarks.reshape(1, 5, 2),
        transform
    ).reshape(5, 2)

    # Calculate the error between transformed and reference landmarks
    errors = np.linalg.norm(
        transformed_landmarks - REFERENCE_LANDMARKS,
        axis=1
    )

    print("\nLandmark alignment errors:")
    landmark_names = [
        "Left eye",
        "Right eye",
        "Nose",
        "Left mouth",
        "Right mouth"
    ]
    for name, error in zip(landmark_names, errors):
        print(f"{name}: {error:.2f} pixels")
    print(f"Mean alignment error: {errors.mean():.2f} pixels")

    aligned = cv2.warpAffine(
        image,
        transform,
        (112, 112),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0
    )

    return aligned


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Test RetinaFace 5-point alignment and measure landmark error."
    )
    parser.add_argument(
        "--frame",
        type=int,
        default=None,
        help="Optional 1-based target frame number to evaluate."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help="Path to save the aligned face image."
    )
    return parser.parse_args()


def find_aligned_face(model, cfg, frame, frame_number, min_size=80):
    """Detect faces in a frame, select the largest meeting min_size, and align it."""
    faces = detect_faces(model, cfg, frame)
    faces.sort(
        key=lambda face: (
            (face["box"][2] - face["box"][0])
            * (face["box"][3] - face["box"][1])
        ),
        reverse=True
    )

    for face in faces:
        x1, y1, x2, y2 = face["box"]
        if (x2 - x1) < min_size or (y2 - y1) < min_size:
            continue

        aligned = align_face(frame, face["landmarks"])
        return {
            "image": aligned,
            "confidence": face["confidence"],
            "frame": frame_number,
            "box": face["box"]
        }

    return None


def main():
    args = parse_args()
    output_path = args.output if args.output.is_absolute() else ROOT / args.output

    print("\nStarting RetinaFace + ArcFace alignment test...")

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable.")

    if not VIDEO_PATH.exists():
        raise FileNotFoundError(VIDEO_PATH)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    model, cfg = load_retinaface()

    cap = cv2.VideoCapture(str(VIDEO_PATH))

    if not cap.isOpened():
        raise RuntimeError("Could not open input video.")

    frame_number = 0
    selected_face = None

    if args.frame is not None:
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, args.frame - 1))
        ret, frame = cap.read()
        if not ret:
            cap.release()
            raise RuntimeError(f"Could not read frame {args.frame}.")
        selected_face = find_aligned_face(
            model, cfg, frame, args.frame, min_size=0
        )
    else:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_number += 1
            selected_face = find_aligned_face(model, cfg, frame, frame_number)
            if selected_face is not None:
                break

            if frame_number % 50 == 0:
                print(f"Scanned {frame_number} frames...")

    cap.release()

    if selected_face is None:
        raise RuntimeError(
            "No sufficiently large face with valid landmarks found."
        )

    cv2.imwrite(
        str(output_path),
        selected_face["image"]
    )

    print("\n========== ALIGNMENT RESULTS ==========")
    print("Frame:", selected_face["frame"])
    print("Face confidence:", round(selected_face["confidence"], 3))
    print("Original face box:", selected_face["box"])
    print("Aligned dimensions:", selected_face["image"].shape)
    print("Saved:", output_path)

    print("\nFace alignment completed successfully.")


if __name__ == "__main__":
    main()
