import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO

# --------------------------------------------------
# PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RETINAFACE_REPO = (
    PROJECT_ROOT / "ai_engine" / "third_party" / "retinaface-pytorch"
)

YOLO_MODEL_PATH = (
    PROJECT_ROOT / "ai_engine" / "models" / "detection" / "yolo11s.pt"
)

RETINAFACE_WEIGHTS = (
    PROJECT_ROOT / "ai_engine" / "models" / "face" / "retinaface_r34.pth"
)

VIDEO_PATH = PROJECT_ROOT / "1.mp4"

OUTPUT_DIR = PROJECT_ROOT / "runs" / "face_detection"
OUTPUT_PATH = OUTPUT_DIR / "person_face_retinaface.mp4"

# Make RetinaFace repository modules importable
sys.path.insert(0, str(RETINAFACE_REPO))

from config import get_config
from models.retinaface import RetinaFace
from layers import PriorBox
from utils.box_utils import decode, decode_landmarks, nms


# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

if DEVICE.type != "cuda":
    raise RuntimeError(
        "CUDA is unavailable. Activate the AI virtual environment."
    )

PERSON_CONFIDENCE = 0.40
FACE_CONFIDENCE = 0.60
NMS_THRESHOLD = 0.40

PRE_NMS_TOP_K = 5000
POST_NMS_TOP_K = 750

RGB_MEAN = (104, 117, 123)


# --------------------------------------------------
# LOAD RETINAFACE
# --------------------------------------------------

def load_retinaface():

    print("Loading RetinaFace ResNet34...")

    if not RETINAFACE_WEIGHTS.exists():
        raise FileNotFoundError(RETINAFACE_WEIGHTS)

    cfg = get_config("resnet34").copy()

    # The RetinaFace checkpoint supplies the trained parameters.
    # Avoid downloading a separate ImageNet backbone checkpoint.
    cfg["pretrain"] = False

    model = RetinaFace(cfg=cfg)

    checkpoint = torch.load(
        RETINAFACE_WEIGHTS,
        map_location=DEVICE,
        weights_only=True
    )

    model.load_state_dict(checkpoint)
    model.to(DEVICE)
    model.eval()

    print("RetinaFace loaded on:", torch.cuda.get_device_name(0))

    return model, cfg


# --------------------------------------------------
# DETECT FACES IN ONE PERSON CROP
# --------------------------------------------------

@torch.inference_mode()
def detect_faces(model, cfg, crop):

    crop_height, crop_width = crop.shape[:2]

    if crop_width < 20 or crop_height < 20:
        return []

    # Pad dimensions to multiples of 32 so the feature maps
    # and generated RetinaFace anchors align.
    padded_width = ((crop_width + 31) // 32) * 32
    padded_height = ((crop_height + 31) // 32) * 32

    padded = np.zeros(
        (padded_height, padded_width, 3),
        dtype=np.uint8
    )

    padded[:crop_height, :crop_width] = crop

    image = padded.astype(np.float32)
    image -= np.array(RGB_MEAN, dtype=np.float32)
    image = image.transpose(2, 0, 1)

    image_tensor = torch.from_numpy(
        np.ascontiguousarray(image)
    ).unsqueeze(0).to(DEVICE)

    loc, conf, landmarks = model(image_tensor)

    loc = loc.squeeze(0)
    conf = conf.squeeze(0)
    landmarks = landmarks.squeeze(0)

    priorbox = PriorBox(
        cfg,
        image_size=(padded_height, padded_width)
    )

    priors = priorbox.generate_anchors().to(DEVICE)

    boxes = decode(loc, priors, cfg["variance"])
    landmarks = decode_landmarks(
        landmarks, priors, cfg["variance"]
    )

    bbox_scale = torch.tensor(
        [
            padded_width, padded_height,
            padded_width, padded_height
        ],
        device=DEVICE
    )

    landmark_scale = torch.tensor(
        [
            padded_width, padded_height
        ] * 5,
        device=DEVICE
    )

    boxes = (boxes * bbox_scale).cpu().numpy()
    landmarks = (landmarks * landmark_scale).cpu().numpy()
    scores = conf[:, 1].cpu().numpy()

    # Confidence filtering
    indices = np.where(scores >= FACE_CONFIDENCE)[0]

    if len(indices) == 0:
        return []

    boxes = boxes[indices]
    landmarks = landmarks[indices]
    scores = scores[indices]

    # Sort by confidence
    order = scores.argsort()[::-1][:PRE_NMS_TOP_K]

    boxes = boxes[order]
    landmarks = landmarks[order]
    scores = scores[order]

    # Non-Maximum Suppression
    detections = np.hstack(
        (boxes, scores[:, np.newaxis])
    ).astype(np.float32, copy=False)

    keep = nms(detections, NMS_THRESHOLD)

    detections = detections[keep][:POST_NMS_TOP_K]
    landmarks = landmarks[keep][:POST_NMS_TOP_K]

    results = []

    for detection, landmark in zip(detections, landmarks):

        x1, y1, x2, y2, confidence = detection

        # Clamp coordinates to the original, unpadded crop.
        x1 = int(np.clip(x1, 0, crop_width - 1))
        y1 = int(np.clip(y1, 0, crop_height - 1))
        x2 = int(np.clip(x2, 0, crop_width - 1))
        y2 = int(np.clip(y2, 0, crop_height - 1))

        if x2 <= x1 or y2 <= y1:
            continue

        landmark = landmark.reshape(5, 2)

        results.append({
            "box": (x1, y1, x2, y2),
            "confidence": float(confidence),
            "landmarks": landmark
        })

    return results


# --------------------------------------------------
# MAIN INTEGRATION TEST
# --------------------------------------------------

def main():

    print("\nStarting YOLO11s + ByteTrack + RetinaFace...")
    print("Device:", torch.cuda.get_device_name(0))

    for path in [VIDEO_PATH, YOLO_MODEL_PATH, RETINAFACE_WEIGHTS]:
        if not path.exists():
            raise FileNotFoundError(f"Required file missing: {path}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load models
    print("\nLoading YOLO11s...")
    yolo = YOLO(str(YOLO_MODEL_PATH))

    retinaface, cfg = load_retinaface()

    # Open video
    cap = cv2.VideoCapture(str(VIDEO_PATH))

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {VIDEO_PATH}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if fps <= 0:
        fps = 25.0

    writer = cv2.VideoWriter(
        str(OUTPUT_PATH),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height)
    )

    if not writer.isOpened():
        raise RuntimeError("Could not create output video.")

    frame_count = 0
    person_detections = 0
    face_detections = 0
    frames_with_faces = 0

    # Count frames in which each temporary track ID
    # has at least one face detection.
    track_face_frames = {}

    start_time = time.time()

    # YOLO tracking stream
    results = yolo.track(
        source=str(VIDEO_PATH),
        stream=True,
        persist=True,
        tracker="bytetrack.yaml",
        classes=[0],
        conf=PERSON_CONFIDENCE,
        device=0,
        verbose=False
    )

    for result in results:

        frame = result.orig_img.copy()
        frame_count += 1

        frame_track_ids = set()

        if result.boxes is not None and len(result.boxes) > 0:

            person_boxes = result.boxes.xyxy.cpu().numpy()

            if result.boxes.id is not None:
                track_ids = result.boxes.id.int().cpu().tolist()
            else:
                track_ids = [None] * len(person_boxes)

            person_detections += len(person_boxes)

            for person_box, track_id in zip(person_boxes, track_ids):

                px1, py1, px2, py2 = map(
                    int, person_box
                )

                px1 = max(0, px1)
                py1 = max(0, py1)
                px2 = min(width, px2)
                py2 = min(height, py2)

                if px2 <= px1 or py2 <= py1:
                    continue

                person_crop = frame[py1:py2, px1:px2]

                faces = detect_faces(
                    retinaface,
                    cfg,
                    person_crop
                )

                # Draw person bounding box
                cv2.rectangle(
                    frame,
                    (px1, py1),
                    (px2, py2),
                    (255, 0, 0),
                    2
                )

                person_label = (
                    f"Person ID: {track_id}"
                    if track_id is not None
                    else "Person ID: unavailable"
                )

                cv2.putText(
                    frame,
                    person_label,
                    (px1, max(20, py1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 0, 0),
                    2
                )

                if faces:

                    for face in faces:

                        fx1, fy1, fx2, fy2 = face["box"]

                        # Convert person-crop coordinates
                        # back to original frame coordinates.
                        fx1 += px1
                        fx2 += px1
                        fy1 += py1
                        fy2 += py1

                        confidence = face["confidence"]

                        cv2.rectangle(
                            frame,
                            (fx1, fy1),
                            (fx2, fy2),
                            (0, 255, 0),
                            2
                        )

                        cv2.putText(
                            frame,
                            f"Face: {confidence:.2f}",
                            (fx1, max(20, fy1 - 7)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.45,
                            (0, 255, 0),
                            2
                        )

                        # Draw five facial landmarks
                        for point in face["landmarks"]:

                            lx = int(point[0]) + px1
                            ly = int(point[1]) + py1

                            if 0 <= lx < width and 0 <= ly < height:
                                cv2.circle(
                                    frame,
                                    (lx, ly),
                                    2,
                                    (0, 0, 255),
                                    -1
                                )

                    face_detections += len(faces)

                    if track_id is not None:
                        frame_track_ids.add(track_id)

                else:

                    cv2.putText(
                        frame,
                        "Face unavailable",
                        (px1, min(height - 5, py2 + 18)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (0, 165, 255),
                        1
                    )

        if frame_track_ids:
            frames_with_faces += 1

            for track_id in frame_track_ids:
                track_face_frames[track_id] = (
                    track_face_frames.get(track_id, 0) + 1
                )

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
            print(f"Processed {frame_count}/{total_frames} frames")

    # Synchronize GPU before measuring elapsed time
    torch.cuda.synchronize()

    processing_time = time.time() - start_time

    cap.release()
    writer.release()

    average_fps = (
        frame_count / processing_time
        if processing_time > 0 else 0
    )

    # --------------------------------------------------
    # RESULTS
    # --------------------------------------------------

    print("\n========== INTEGRATION RESULTS ==========")

    print("Device: CUDA")
    print("GPU:", torch.cuda.get_device_name(0))
    print("Frames processed:", frame_count)
    print("Person detections:", person_detections)
    print("Face detections:", face_detections)
    print("Frames containing faces:", frames_with_faces)
    print("Unique track IDs with face detections:", len(track_face_frames))

    print(f"Processing time: {processing_time:.2f} seconds")
    print(f"Average FPS: {average_fps:.2f}")

    print("Output video:", OUTPUT_PATH)

    print("\nFace detections by track ID:")

    for track_id, count in sorted(track_face_frames.items()):
        print(f"Track ID {track_id}: {count} face-containing frames")

    print("\nIntegration test completed.")


if __name__ == "__main__":
    main()