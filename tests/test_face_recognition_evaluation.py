from pathlib import Path
from itertools import combinations, product
import csv
import cv2
import numpy as np

# Import torch before ONNX Runtime.
# This helps load the CUDA/cuDNN DLLs bundled with PyTorch on Windows.
import torch
import onnxruntime as ort

ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "ai_engine" / "datasets" / "face_recognition"
MODEL_PATH = ROOT / "ai_engine" / "models" / "face" / "auraface_v1_glintr100.onnx"
OUTPUT_DIR = ROOT / "runs" / "face_recognition_evaluation"
CSV_PATH = OUTPUT_DIR / "pair_scores.csv"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


def load_model():
    """Load the AuraFace ONNX session using CUDA if available."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    available = ort.get_available_providers()
    if "CUDAExecutionProvider" in available:
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    else:
        providers = ["CPUExecutionProvider"]

    session = ort.InferenceSession(str(MODEL_PATH), providers=providers)
    print("Active providers:", session.get_providers())
    return session


def extract_embedding(session, input_name, image_path):
    """Extract an L2-normalized 512D embedding from a 112x112 aligned face."""
    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f"Could not read image: {image_path}")

    if image.shape[:2] != (112, 112):
        raise ValueError(
            f"Expected 112x112 aligned face for {image_path}, got {image.shape[:2]}"
        )

    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB).astype(np.float32)
    image = (image - 127.5) / 127.5
    tensor = np.expand_dims(np.transpose(image, (2, 0, 1)), axis=0)

    embedding = session.run(None, {input_name: tensor})[0][0]
    if embedding.shape != (512,):
        raise RuntimeError(f"Unexpected embedding shape {embedding.shape}")

    norm = float(np.linalg.norm(embedding))
    if norm == 0.0 or not np.isfinite(norm):
        raise ValueError(f"Invalid embedding norm for {image_path}")

    return (embedding / norm).astype(np.float32)


def load_dataset_embeddings(session):
    """Scan employee subdirectories and extract face embeddings."""
    if not DATASET_DIR.exists():
        raise FileNotFoundError(f"Dataset directory not found: {DATASET_DIR}")

    input_name = session.get_inputs()[0].name
    embeddings_by_employee = {}

    for employee_dir in sorted(DATASET_DIR.iterdir()):
        if not employee_dir.is_dir():
            continue

        image_paths = sorted(
            p for p in employee_dir.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        )
        if not image_paths:
            continue

        embeddings_by_employee[employee_dir.name] = [
            (img_path.name, extract_embedding(session, input_name, img_path))
            for img_path in image_paths
        ]

    if len(embeddings_by_employee) < 2:
        raise RuntimeError(
            "Need at least 2 employee directories with images to compute impostor similarity."
        )

    return embeddings_by_employee


def compute_pairwise_scores(embeddings_by_employee):
    """Compute genuine and impostor cosine similarity pairs and save to CSV."""
    rows = []
    genuine_scores = []
    impostor_scores = []

    employees = sorted(embeddings_by_employee.keys())

    # Genuine comparisons (same employee)
    for emp_id in employees:
        samples = embeddings_by_employee[emp_id]
        for (name_a, emb_a), (name_b, emb_b) in combinations(samples, 2):
            score = float(np.dot(emb_a, emb_b))
            genuine_scores.append(score)
            rows.append(["genuine", emp_id, name_a, emp_id, name_b, round(score, 6)])

    # Impostor comparisons (different employees)
    for emp_a, emp_b in combinations(employees, 2):
        for (name_a, emb_a), (name_b, emb_b) in product(
            embeddings_by_employee[emp_a], embeddings_by_employee[emp_b]
        ):
            score = float(np.dot(emb_a, emb_b))
            impostor_scores.append(score)
            rows.append(["impostor", emp_a, name_a, emp_b, name_b, round(score, 6)])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CSV_PATH, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "pair_type",
            "employee_a",
            "image_a",
            "employee_b",
            "image_b",
            "cosine_similarity",
        ])
        writer.writerows(rows)

    return np.array(genuine_scores, dtype=np.float32), np.array(impostor_scores, dtype=np.float32)


def print_statistics(embeddings_by_employee, genuine_scores, impostor_scores):
    """Print dataset counts, genuine/impostor distributions, and exploratory FAR/FRR."""
    total_images = sum(len(items) for items in embeddings_by_employee.values())

    print("\n========== DATASET SUMMARY ==========")
    print(f"Employees evaluated  : {len(embeddings_by_employee)}")
    for emp_id, items in embeddings_by_employee.items():
        print(f"  - {emp_id}: {len(items)} images")
    print(f"Total aligned images : {total_images}")
    print(f"Genuine comparisons  : {len(genuine_scores)}")
    print(f"Impostor comparisons : {len(impostor_scores)}")
    print(f"Pair scores CSV      : {CSV_PATH}")

    print("\n========== SIMILARITY DISTRIBUTIONS ==========")
    if len(genuine_scores) > 0:
        print(
            "Genuine  -> "
            f"min: {genuine_scores.min():.4f} | "
            f"median: {np.median(genuine_scores):.4f} | "
            f"max: {genuine_scores.max():.4f} | "
            f"mean: {genuine_scores.mean():.4f}"
        )
    else:
        print("Genuine  -> No genuine pairs available (need >= 2 images for an employee)")

    if len(impostor_scores) > 0:
        print(
            "Impostor -> "
            f"min: {impostor_scores.min():.4f} | "
            f"median: {np.median(impostor_scores):.4f} | "
            f"max: {impostor_scores.max():.4f} | "
            f"mean: {impostor_scores.mean():.4f}"
        )

    if len(genuine_scores) > 0 and len(impostor_scores) > 0:
        margin = float(genuine_scores.min() - impostor_scores.max())
        print(f"Separation margin (Genuine min - Impostor max): {margin:+.4f}")

        print("\n========== EXPLORATORY THRESHOLD ANALYSIS ==========")
        print(f"{'Threshold':>10} | {'FAR (%)':>10} | {'FRR (%)':>10}")
        print("-" * 36)
        thresholds = np.arange(0.15, 0.86, 0.05)
        for threshold in thresholds:
            far = float(np.mean(impostor_scores >= threshold) * 100.0)
            frr = float(np.mean(genuine_scores < threshold) * 100.0)
            print(f"{threshold:10.2f} | {far:9.2f}% | {frr:9.2f}%")


def main():
    print("Starting AuraFace recognition evaluation...")
    session = load_model()
    embeddings_by_employee = load_dataset_embeddings(session)
    genuine_scores, impostor_scores = compute_pairwise_scores(embeddings_by_employee)
    print_statistics(embeddings_by_employee, genuine_scores, impostor_scores)
    print("\nEvaluation completed successfully.")


if __name__ == "__main__":
    main()

