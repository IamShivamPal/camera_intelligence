import sys
import time
from pathlib import Path
from collections import Counter

import cv2
import numpy as np
import torch
from ultralytics import YOLO

# --------------------------------------------------
# PATHS
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

RETINAFACE_REPO = (
    ROOT / "ai_engine" / "third_party" / "retinaface-pytorch"
)

YOLO_WEIGHTS = ROOT / "ai_engine" / "models" / "detection" / "yolo11s.pt"

FACE_WEIGHTS = (
    ROOT / "ai_engine" / "models" / "face" / "retinaface_r34.pth"
)

VIDEO_PATH = ROOT / "1.mp4"

OUTPUT_DIR = ROOT / "runs" / "face_quality"
OUTPUT_PATH = OUTPUT_DIR / "face_quality_test.mp4"

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
        "CUDA unavailable. Activate the AI virtual environment."
    )

PERSON_CONFIDENCE = 0.40
FACE_CONFIDENCE = 0.60

MIN_FACE_WIDTH = 40
MIN_FACE_HEIGHT = 40

# Provisional threshold; must be evaluated on actual footage.
MIN_BLUR_VARIANCE = 50.0

NMS_THRESHOLD = 0.40
PRE_NMS_TOP_K = 5000
POST_NMS_TOP_K = 750

RGB_MEAN = (104, 117, 123)


# --------------------------------------------------
# LOAD RETINAFACE
# --------------------------------------------------

def load_retinaface():

    print("Loading RetinaFace ResNet34...")

    cfg = get_config("resnet34").copy()
    cfg["pretrain"] = False

    model = RetinaFace(cfg=cfg)

    checkpoint = torch.load(
        FACE_WEIGHTS,
        map_location=DEVICE,
        weights_only=True
    )

    model.load_state_dict(checkpoint)
    model.to(DEVICE)
    model.eval()

    print("RetinaFace loaded on:", torch.cuda.get_device_name(0))

    return model, cfg


# --------------------------------------------------
# DETECT FACES IN PERSON CROP
# --------------------------------------------------

@torch.inference_mode()
def detect_faces(model, cfg, crop):

    crop_h, crop_w = crop.shape[:2]

    if crop_w < 20 or crop_h < 20:
        return []

    # Pad to multiples of 32 for anchor alignment.
    padded_w = ((crop_w + 31) // 32) * 32
    padded_h = ((crop_h + 31) // 32) * 32

    padded = np.zeros((padded_h, padded_w, 3), dtype=np.uint8)
    padded[:crop_h, :crop_w] = crop

    image = padded.astype(np.float32)
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
        image_size=(padded_h, padded_w)
    ).generate_anchors().to(DEVICE)

    boxes = decode(loc, priors, cfg["variance"])
    landmarks = decode_landmarks(
        landmarks, priors, cfg["variance"]
    )

    box_scale = torch.tensor(
        [padded_w, padded_h, padded_w, padded_h],
        device=DEVICE
    )

    landmark_scale = torch.tensor(
        [padded_w, padded_h] * 5,
        device=DEVICE
    )

    boxes = (boxes * box_scale).cpu().numpy()
    landmarks = (landmarks * landmark_scale).cpu().numpy()
    scores = conf[:, 1].cpu().numpy()

    indices = np.where(scores >= FACE_CONFIDENCE)[0]

    if len(indices) == 0:
        return []

    boxes = boxes[indices]
    landmarks = landmarks[indices]
    scores = scores[indices]

    order = scores.argsort()[::-1][:PRE_NMS_TOP_K]

    boxes = boxes[order]
    landmarks = landmarks[order]
    scores = scores[order]

    detections = np.hstack(
        (boxes, scores[:, np.newaxis])
    ).astype(np.float32, copy=False)

    keep = nms(detections, NMS_THRESHOLD)

    detections = detections[keep][:POST_NMS_TOP_K]
    landmarks = landmarks[keep][:POST_NMS_TOP_K]

    results = []

    for detection, points in zip(detections, landmarks):

        x1, y1, x2, y2, score = detection

        x1 = int(np.clip(x1, 0, crop_w - 1))
        y1 = int(np.clip(y1, 0, crop_h - 1))
        x2 = int(np.clip(x2, 0, crop_w - 1))
        y2 = int(np.clip(y2, 0, crop_h - 1))

        if x2 <= x1 or y2 <= y1:
            continue

        results.append({
            "box": (x1, y1, x2, y2),
            "confidence": float(score),
            "landmarks": points.reshape(5, 2)
        })

    return results


# --------------------------------------------------
# FACE QUALITY CHECKS
# --------------------------------------------------

def evaluate_face(crop, face):

    x1, y1, x2, y2 = face["box"]

    face_w = x2 - x1
    face_h = y2 - y1

    reasons = []

    # 1. Face dimensions
    if face_w < MIN_FACE_WIDTH or face_h < MIN_FACE_HEIGHT:
        reasons.append("SMALL")

    # 2. Face confidence
    if face["confidence"] < FACE_CONFIDENCE:
        reasons.append("LOW CONF")

    # 3. Blur / sharpness
    face_image = crop[y1:y2, x1:x2]

    if face_image.size == 0:
        blur_variance = 0.0
        reasons.append("INVALID CROP")
    else:
        gray = cv2.cvtColor(
            face_image,
            cv2.COLOR_BGR2GRAY
        )

        blur_variance = float(
            cv2.Laplacian(
                gray,
                cv2.CV_64F
            ).var()
        )

        if blur_variance < MIN_BLUR_VARIANCE:
            reasons.append("BLUR")

    # 4. Landmark validity
    points = face["landmarks"]

    if (
        points.shape != (5, 2)
        or not np.isfinite(points).all()
        or np.any(points[:, 0] < x1 - 2)
        or np.any(points[:, 0] > x2 + 2)
        or np.any(points[:, 1] < y1 - 2)
        or np.any(points[:, 1] > y2 + 2)
    ):
        reasons.append("LANDMARKS")
    else:
        # RetinaFace landmark order:
        # 0 = right eye, 1 = left eye, 2 = nose,
        # 3 = right mouth, 4 = left mouth
        landmarks = np.asarray(face["landmarks"], dtype=np.float32)
        right_eye = landmarks[0]
        left_eye = landmarks[1]
        nose = landmarks[2]

        # 1. Minimum inter-eye distance
        inter_eye_distance = np.linalg.norm(right_eye - left_eye)
        minimum_eye_distance = max(8.0, face_w * 0.18)

        if inter_eye_distance < minimum_eye_distance:
            reasons.append("EYES_TOO_CLOSE")

        # 2. Face pose estimation using nose displacement
        eye_midpoint_x = (right_eye[0] + left_eye[0]) / 2.0
        nose_offset = abs(nose[0] - eye_midpoint_x)
        pose_ratio = nose_offset / max(inter_eye_distance, 1.0)

        if pose_ratio > 0.45:
            reasons.append("EXTREME_POSE")

    return {
        "accepted": len(reasons) == 0,
        "reasons": reasons,
        "blur_variance": blur_variance,
        "width": face_w,
        "height": face_h
    }


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print("\nStarting face-quality evaluation...")
    print("GPU:", torch.cuda.get_device_name(0))

    for path in [VIDEO_PATH, YOLO_WEIGHTS, FACE_WEIGHTS]:
        if not path.exists():
            raise FileNotFoundError(path)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    yolo = YOLO(str(YOLO_WEIGHTS))
    retinaface, cfg = load_retinaface()

    cap = cv2.VideoCapture(str(VIDEO_PATH))

    if not cap.isOpened():
        raise RuntimeError("Unable to open input video.")

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
        raise RuntimeError("Unable to create output video.")

    stats = Counter({
        "reject_eyes_too_close": 0,
        "reject_extreme_pose": 0,
    })

    frame_count = 0
    frames_with_accepted_faces = 0
    start_time = time.time()

    results_stream = yolo.track(
        source=str(VIDEO_PATH),
        stream=True,
        persist=True,
        tracker="bytetrack.yaml",
        classes=[0],
        conf=PERSON_CONFIDENCE,
        device=0,
        verbose=False
    )

    for result in results_stream:

        frame = result.orig_img.copy()
        frame_count += 1

        accepted_in_frame = False

        if result.boxes is not None and len(result.boxes) > 0:

            person_boxes = result.boxes.xyxy.cpu().numpy()

            track_ids = (
                result.boxes.id.int().cpu().tolist()
                if result.boxes.id is not None
                else [None] * len(person_boxes)
            )

            for person_box, track_id in zip(person_boxes, track_ids):

                px1, py1, px2, py2 = map(int, person_box)

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

                stats["person_detections"] += 1

                cv2.rectangle(
                    frame,
                    (px1, py1),
                    (px2, py2),
                    (255, 0, 0),
                    2
                )

                label = (
                    f"Person ID: {track_id}"
                    if track_id is not None
                    else "Person"
                )

                cv2.putText(
                    frame,
                    label,
                    (px1, max(20, py1 - 7)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 0, 0),
                    2
                )

                for face in faces:

                    stats["face_candidates"] += 1

                    quality = evaluate_face(
                        person_crop,
                        face
                    )

                    x1, y1, x2, y2 = face["box"]

                    x1 += px1
                    x2 += px1
                    y1 += py1
                    y2 += py1

                    if quality["accepted"]:

                        stats["accepted"] += 1
                        accepted_in_frame = True

                        color = (0, 255, 0)
                        label = (
                            f"ACCEPT {face['confidence']:.2f}"
                        )

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

                    else:

                        stats["rejected"] += 1

                        color = (0, 0, 255)
                        label = "REJECT: " + ",".join(
                            quality["reasons"]
                        )

                        for reason in quality["reasons"]:
                            stats[f"reject_{reason.lower()}"] += 1

                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        color,
                        2
                    )

                    cv2.putText(
                        frame,
                        label,
                        (x1, max(20, y1 - 7)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.42,
                        color,
                        1
                    )

        if accepted_in_frame:
            frames_with_accepted_faces += 1

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

    print("\n========== FACE QUALITY RESULTS ==========")

    print("GPU:", torch.cuda.get_device_name(0))
    print("Frames processed:", frame_count)
    print("Person detections:", stats["person_detections"])
    print("Face candidates:", stats["face_candidates"])
    print("Accepted faces:", stats["accepted"])
    print("Rejected faces:", stats["rejected"])
    print(
        "Frames with accepted faces:",
        frames_with_accepted_faces
    )

    print("\nRejection reasons:")

    for reason in [
        "small",
        "blur",
        "low conf",
        "landmarks",
        "invalid crop",
        "eyes_too_close",
        "extreme_pose"
    ]:
        print(
            f"{reason}: {stats[f'reject_{reason}']}"
        )

    print(f"\nProcessing time: {processing_time:.2f} seconds")
    print(f"Average FPS: {average_fps:.2f}")
    print("Output:", OUTPUT_PATH)

    print("\nFace quality evaluation completed.")


if __name__ == "__main__":
    main()  