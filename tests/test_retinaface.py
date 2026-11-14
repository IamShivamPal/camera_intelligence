import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

# --------------------------------------------------
# PATH CONFIGURATION
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RETINAFACE_REPO = (
    PROJECT_ROOT
    / "ai_engine"
    / "third_party"
    / "retinaface-pytorch"
)

WEIGHTS_PATH = (
    PROJECT_ROOT
    / "ai_engine"
    / "models"
    / "face"
    / "retinaface_r34.pth"
)

VIDEO_PATH = PROJECT_ROOT / "1.mp4"

OUTPUT_DIR = PROJECT_ROOT / "runs" / "face_detection"
OUTPUT_PATH = OUTPUT_DIR / "retinaface_test.mp4"

# Make RetinaFace repository modules importable
sys.path.insert(0, str(RETINAFACE_REPO))

from config import get_config
from models.retinaface import RetinaFace
from layers.functions.prior_box import PriorBox
from utils.box_utils import decode, decode_landmarks, nms


# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

CONFIDENCE_THRESHOLD = 0.60
NMS_THRESHOLD = 0.40

PRE_NMS_TOP_K = 5000
POST_NMS_TOP_K = 750

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

if not torch.cuda.is_available():
    raise RuntimeError(
        "CUDA is unavailable! Activate the AI virtual environment."
    )

# RetinaFace BGR normalization mean
RGB_MEAN = (104, 117, 123)


# --------------------------------------------------
# LOAD MODEL
# --------------------------------------------------

def load_retinaface():

    print("Loading RetinaFace ResNet34...")

    if not WEIGHTS_PATH.exists():
        raise FileNotFoundError(
            f"Model weights not found: {WEIGHTS_PATH}"
        )

    cfg = get_config("resnet34").copy()

    # The RetinaFace checkpoint contains the trained
    # detector parameters, so avoid downloading a
    # separate ImageNet backbone checkpoint.
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

    print("RetinaFace loaded successfully!")
    print("Device:", DEVICE)

    if DEVICE.type == "cuda":
        print("GPU:", torch.cuda.get_device_name(0))

    return model, cfg


# --------------------------------------------------
# FACE DETECTION
# --------------------------------------------------

@torch.inference_mode()
def detect_faces(model, cfg, frame):

    original_height, original_width = frame.shape[:2]

    # BGR image preprocessing
    image = frame.astype(np.float32)
    image -= np.array(RGB_MEAN, dtype=np.float32)

    # HWC -> CHW
    image = image.transpose(2, 0, 1)

    # Add batch dimension
    image_tensor = torch.from_numpy(
        np.ascontiguousarray(image)
    ).unsqueeze(0).to(DEVICE)

    # RetinaFace inference
    loc, conf, landmarks = model(image_tensor)

    loc = loc.squeeze(0)
    conf = conf.squeeze(0)
    landmarks = landmarks.squeeze(0)

    # Generate anchor boxes
    priorbox = PriorBox(
        cfg,
        image_size=(original_height, original_width)
    )

    priors = priorbox.generate_anchors().to(DEVICE)

    # Decode bounding boxes and landmarks
    boxes = decode(
        loc,
        priors,
        cfg["variance"]
    )

    landmarks = decode_landmarks(
        landmarks,
        priors,
        cfg["variance"]
    )

    bbox_scale = torch.tensor(
        [
            original_width,
            original_height,
            original_width,
            original_height
        ],
        device=DEVICE
    )

    landmark_scale = torch.tensor(
        [
            original_width,
            original_height
        ] * 5,
        device=DEVICE
    )

    boxes = (
        boxes * bbox_scale
    ).cpu().numpy()

    landmarks = (
        landmarks * landmark_scale
    ).cpu().numpy()

    scores = conf[:, 1].cpu().numpy()

    # Confidence filtering
    indices = np.where(
        scores > CONFIDENCE_THRESHOLD
    )[0]

    boxes = boxes[indices]
    landmarks = landmarks[indices]
    scores = scores[indices]

    if len(scores) == 0:
        return []

    # Sort by confidence
    order = scores.argsort()[::-1][:PRE_NMS_TOP_K]

    boxes = boxes[order]
    landmarks = landmarks[order]
    scores = scores[order]

    # Non-Maximum Suppression
    detections = np.hstack(
        (
            boxes,
            scores[:, np.newaxis]
        )
    ).astype(np.float32, copy=False)

    keep = nms(
        detections,
        NMS_THRESHOLD
    )

    detections = detections[keep]
    landmarks = landmarks[keep]

    detections = detections[:POST_NMS_TOP_K]
    landmarks = landmarks[:POST_NMS_TOP_K]

    results = []

    for detection, landmark in zip(detections, landmarks):

        x1, y1, x2, y2, confidence = detection

        results.append({
            "box": (
                int(max(0, x1)),
                int(max(0, y1)),
                int(min(original_width - 1, x2)),
                int(min(original_height - 1, y2))
            ),
            "confidence": float(confidence),
            "landmarks": landmark.reshape(5, 2)
        })

    return results


# --------------------------------------------------
# DRAW DETECTIONS
# --------------------------------------------------

def draw_faces(frame, faces):

    for face in faces:

        x1, y1, x2, y2 = face["box"]
        confidence = face["confidence"]

        # Face bounding box
        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            2
        )

        # Confidence label
        label = f"Face: {confidence:.2f}"

        cv2.putText(
            frame,
            label,
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 0),
            2
        )

        # Five facial landmarks
        for point in face["landmarks"]:

            px, py = map(int, point)

            cv2.circle(
                frame,
                (px, py),
                2,
                (0, 0, 255),
                -1
            )

    return frame


# --------------------------------------------------
# MAIN VIDEO PROCESSING
# --------------------------------------------------

def main():

    print("\nStarting RetinaFace detection test...")

    if not VIDEO_PATH.exists():
        raise FileNotFoundError(
            f"Video not found: {VIDEO_PATH}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    model, cfg = load_retinaface()

    cap = cv2.VideoCapture(str(VIDEO_PATH))

    if not cap.isOpened():
        raise RuntimeError("Unable to open input video.")

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if fps <= 0:
        fps = 25.0

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    writer = cv2.VideoWriter(
        str(OUTPUT_PATH),
        fourcc,
        fps,
        (width, height)
    )

    if not writer.isOpened():
        raise RuntimeError("Unable to create output video.")

    frame_count = 0
    total_detections = 0
    frames_with_faces = 0

    start_time = time.time()

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        faces = detect_faces(
            model,
            cfg,
            frame
        )

        frame_count += 1

        total_detections += len(faces)

        if faces:
            frames_with_faces += 1

        frame = draw_faces(
            frame,
            faces
        )

        # Display frame counter
        cv2.putText(
            frame,
            f"Frame: {frame_count}/{total_frames}",
            (15, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        writer.write(frame)

        if frame_count % 50 == 0:

            print(
                f"Processed {frame_count}/{total_frames} frames"
            )

    processing_time = time.time() - start_time

    cap.release()
    writer.release()

    average_fps = (
        frame_count / processing_time
        if processing_time > 0
        else 0
    )

    # --------------------------------------------------
    # RESULTS
    # --------------------------------------------------

    print("\n========== RETINAFACE RESULTS ==========")

    print("Model: RetinaFace ResNet34")
    print("Device:", DEVICE)
    print("Frames processed:", frame_count)
    print("Frames containing faces:", frames_with_faces)
    print("Total face detections:", total_detections)

    print(
        f"Processing time: {processing_time:.2f} seconds"
    )

    print(
        f"Average FPS: {average_fps:.2f}"
    )

    print("Output video:", OUTPUT_PATH)

    print("\nRetinaFace test completed successfully.")


if __name__ == "__main__":
    main()