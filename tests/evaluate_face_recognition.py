
import argparse
import csv
from pathlib import Path

import numpy as np
import torch

# Import torch before ONNX Runtime for CUDA DLL loading on Windows.
import onnxruntime as ort

ROOT = Path(__file__).resolve().parents[1]

MODEL_PATH = (
    ROOT / "ai_engine/models/face/auraface_v1_glintr100.onnx"
)

TEMPLATE_PATH = (
    ROOT / "runs/employee_enrollment/employee_templates.npz"
)

VERIFICATION_DIR = (
    ROOT / "ai_engine/datasets/face_recognition/verification"
)

OUTPUT_DIR = ROOT / "runs/face_recognition_batch_evaluation"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


def normalize(vector):
    norm = np.linalg.norm(vector)
    if norm < 1e-12:
        raise ValueError("Cannot normalize a zero-length embedding.")
    return vector / norm


def load_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    available = ort.get_available_providers()

    providers = []
    if "CUDAExecutionProvider" in available:
        providers.append("CUDAExecutionProvider")
    providers.append("CPUExecutionProvider")

    session = ort.InferenceSession(
        str(MODEL_PATH),
        providers=providers
    )

    print("Active providers:", session.get_providers())
    return session


def load_templates():
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"Employee templates not found: {TEMPLATE_PATH}"
        )

    data = np.load(TEMPLATE_PATH, allow_pickle=False)

    employee_ids = [
        str(employee_id)
        for employee_id in data["employee_ids"]
    ]

    templates = np.asarray(data["templates"], dtype=np.float32)

    if templates.ndim != 2 or templates.shape[1] != 512:
        raise ValueError(
            f"Expected templates shaped (employees, 512), got {templates.shape}"
        )

    if len(employee_ids) != len(templates):
        raise ValueError("Employee IDs and templates count do not match.")

    templates = np.stack([normalize(t) for t in templates])

    return employee_ids, templates


def extract_embedding(session, image_path):
    import cv2

    image = cv2.imread(str(image_path))

    if image is None:
        raise ValueError(f"Could not read image: {image_path}")

    if image.shape[:2] != (112, 112):
        raise ValueError(
            f"Expected aligned 112x112 image, received "
            f"{image.shape[1]}x{image.shape[0]}: {image_path}"
        )

    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = image.astype(np.float32)
    image = (image - 127.5) / 127.5
    image = np.transpose(image, (2, 0, 1))
    image = np.expand_dims(image, axis=0)

    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name

    embedding = session.run(
        [output_name],
        {input_name: image}
    )[0][0]

    return normalize(np.asarray(embedding, dtype=np.float32))


def collect_images():
    if not VERIFICATION_DIR.exists():
        raise FileNotFoundError(VERIFICATION_DIR)

    samples = []

    # Genuine employee verification images.
    for folder in sorted(VERIFICATION_DIR.glob("employee_*")):
        if not folder.is_dir():
            continue

        employee_id = folder.name

        for image_path in sorted(folder.iterdir()):
            if image_path.suffix.lower() in IMAGE_EXTENSIONS:
                samples.append({
                    "path": image_path,
                    "true_identity": employee_id,
                    "sample_type": "genuine"
                })

    # Unknown-person verification images.
    unknown_folder = VERIFICATION_DIR / "unknown"

    if unknown_folder.exists():
        for image_path in sorted(unknown_folder.iterdir()):
            if image_path.suffix.lower() in IMAGE_EXTENSIONS:
                samples.append({
                    "path": image_path,
                    "true_identity": "UNKNOWN",
                    "sample_type": "unknown"
                })

    return samples


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Batch evaluation of AuraFace employee recognition."
    )

    parser.add_argument(
        "--start",
        type=float,
        default=0.10,
        help="First similarity threshold."
    )

    parser.add_argument(
        "--end",
        type=float,
        default=0.90,
        help="Last similarity threshold."
    )

    parser.add_argument(
        "--step",
        type=float,
        default=0.01,
        help="Threshold increment."
    )

    args = parser.parse_args()

    if args.step <= 0 or args.start > args.end:
        raise ValueError("Invalid threshold range or step.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("\nLoading AuraFace model...")
    session = load_model()

    print("\nLoading employee templates...")
    employee_ids, templates = load_templates()

    print("Enrolled employees:", len(employee_ids))
    print("Employee IDs:", employee_ids)

    samples = collect_images()

    if not samples:
        raise RuntimeError(
            "No verification images found. Add aligned 112x112 images "
            "to verification/employee_* or verification/unknown."
        )

    print("\nVerification images found:", len(samples))

    prediction_rows = []
    pair_rows = []
    skipped_rows = []

    for index, sample in enumerate(samples, start=1):
        image_path = sample["path"]
        true_identity = sample["true_identity"]
        sample_type = sample["sample_type"]

        print(
            f"\n[{index}/{len(samples)}] "
            f"Processing {image_path.name} ({true_identity})"
        )

        try:
            embedding = extract_embedding(session, image_path)
        except Exception as error:
            print("SKIPPED:", error)
            skipped_rows.append({
                "image": str(image_path.relative_to(ROOT)),
                "reason": str(error)
            })
            continue

        scores = templates @ embedding

        best_index = int(np.argmax(scores))
        best_employee = employee_ids[best_index]
        best_score = float(scores[best_index])

        if sample_type == "genuine":
            if true_identity not in employee_ids:
                print("SKIPPED: employee folder has no enrolled template.")
                skipped_rows.append({
                    "image": str(image_path.relative_to(ROOT)),
                    "reason": "No matching enrolled employee template."
                })
                continue

            genuine_index = employee_ids.index(true_identity)
            genuine_score = float(scores[genuine_index])
        else:
            genuine_score = ""

        prediction_rows.append({
            "image": str(image_path.relative_to(ROOT)),
            "sample_type": sample_type,
            "true_identity": true_identity,
            "best_employee": best_employee,
            "best_similarity": round(best_score, 6),
            "genuine_similarity": (
                round(genuine_score, 6)
                if genuine_score != "" else ""
            )
        })

        for employee_id, score in zip(employee_ids, scores):
            pair_rows.append({
                "image": str(image_path.relative_to(ROOT)),
                "sample_type": sample_type,
                "true_identity": true_identity,
                "compared_employee": employee_id,
                "cosine_similarity": round(float(score), 6)
            })

        print("Best match:", best_employee)
        print("Best similarity:", round(best_score, 6))

    if not prediction_rows:
        raise RuntimeError(
            "No valid images were evaluated. Check the skipped image reasons."
        )

    # Sweep thresholds and calculate image-level error rates.
    metrics_rows = []

    genuine_samples = [
        row for row in prediction_rows
        if row["sample_type"] == "genuine"
    ]

    unknown_samples = [
        row for row in prediction_rows
        if row["sample_type"] == "unknown"
    ]

    thresholds = np.arange(
        args.start,
        args.end + args.step / 2,
        args.step
    )

    for threshold in thresholds:
        genuine_rejected = 0
        wrong_identity_accepted = 0
        unknown_accepted = 0

        for row in genuine_samples:
            accepted = row["best_similarity"] >= threshold
            correctly_identified = (
                row["best_employee"] == row["true_identity"]
            )

            if not accepted or not correctly_identified:
                genuine_rejected += 1

            if accepted and not correctly_identified:
                wrong_identity_accepted += 1

        for row in unknown_samples:
            if row["best_similarity"] >= threshold:
                unknown_accepted += 1

        frr = (
            genuine_rejected / len(genuine_samples)
            if genuine_samples else float("nan")
        )

        far = (
            unknown_accepted / len(unknown_samples)
            if unknown_samples else float("nan")
        )

        wrong_rate = (
            wrong_identity_accepted / len(genuine_samples)
            if genuine_samples else float("nan")
        )

        metrics_rows.append({
            "threshold": round(float(threshold), 4),
            "genuine_images": len(genuine_samples),
            "unknown_images": len(unknown_samples),
            "FAR": round(far, 6) if np.isfinite(far) else "",
            "FRR": round(frr, 6) if np.isfinite(frr) else "",
            "wrong_identity_accept_rate": (
                round(wrong_rate, 6)
                if np.isfinite(wrong_rate) else ""
            ),
            "unknown_false_accepts": unknown_accepted,
            "genuine_rejections": genuine_rejected,
            "wrong_identity_accepts": wrong_identity_accepted
        })

    write_csv(
        OUTPUT_DIR / "predictions.csv",
        prediction_rows,
        [
            "image",
            "sample_type",
            "true_identity",
            "best_employee",
            "best_similarity",
            "genuine_similarity"
        ]
    )

    write_csv(
        OUTPUT_DIR / "pairwise_scores.csv",
        pair_rows,
        [
            "image",
            "sample_type",
            "true_identity",
            "compared_employee",
            "cosine_similarity"
        ]
    )

    write_csv(
        OUTPUT_DIR / "threshold_metrics.csv",
        metrics_rows,
        [
            "threshold",
            "genuine_images",
            "unknown_images",
            "FAR",
            "FRR",
            "wrong_identity_accept_rate",
            "unknown_false_accepts",
            "genuine_rejections",
            "wrong_identity_accepts"
        ]
    )

    write_csv(
        OUTPUT_DIR / "skipped_images.csv",
        skipped_rows,
        ["image", "reason"]
    )

    print("\n========== BATCH EVALUATION ==========")
    print("Valid images:", len(prediction_rows))
    print("Genuine images:", len(genuine_samples))
    print("Unknown images:", len(unknown_samples))
    print("Skipped images:", len(skipped_rows))

    if genuine_samples and unknown_samples:
        valid_metrics = [
            row for row in metrics_rows
            if row["FAR"] != "" and row["FRR"] != ""
        ]

        eer_row = min(
            valid_metrics,
            key=lambda row: abs(row["FAR"] - row["FRR"])
        )

        print("\nApproximate EER operating point:")
        print("Threshold:", eer_row["threshold"])
        print("FAR:", eer_row["FAR"])
        print("FRR:", eer_row["FRR"])
        print(
            "Note: This is a small-sample diagnostic, "
            "not a production threshold."
        )
    else:
        print(
            "\nEER unavailable: both genuine and unknown "
            "verification samples are required."
        )

    print("\nReports saved to:", OUTPUT_DIR)


if __name__ == "__main__":
    main()

