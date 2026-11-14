
from pathlib import Path

import cv2
import numpy as np
import torch
import onnxruntime as ort


ROOT = Path(__file__).resolve().parents[1]

ENROLLMENT_DIR = (
    ROOT / "ai_engine" / "datasets" / "face_recognition" / "enrollment"
)

MODEL_PATH = (
    ROOT / "ai_engine" / "models" / "face" / "auraface_v1_glintr100.onnx"
)

OUTPUT_DIR = ROOT / "runs" / "employee_enrollment"
OUTPUT_PATH = OUTPUT_DIR / "employee_templates.npz"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


def load_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"AuraFace model not found: {MODEL_PATH}")

    available = ort.get_available_providers()

    providers = (
        ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if "CUDAExecutionProvider" in available
        else ["CPUExecutionProvider"]
    )

    session = ort.InferenceSession(
        str(MODEL_PATH),
        providers=providers
    )

    print("Active providers:", session.get_providers())

    return session


def extract_embedding(session, image_path):
    image = cv2.imread(str(image_path))

    if image is None:
        raise ValueError(f"Cannot read image: {image_path}")

    if image.shape[:2] != (112, 112):
        raise ValueError(
            f"Expected aligned 112x112 image: {image_path}"
        )

    # BGR to RGB
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # AuraFace preprocessing used in our existing tests
    image = image.astype(np.float32)
    image = (image - 127.5) / 127.5

    # HWC to NCHW
    image = np.transpose(image, (2, 0, 1))
    image = np.expand_dims(image, axis=0)

    input_name = session.get_inputs()[0].name
    output = session.run(None, {input_name: image})[0]

    embedding = output.reshape(-1).astype(np.float32)

    if embedding.shape != (512,):
        raise ValueError(
            f"Expected 512D embedding, received {embedding.shape}"
        )

    norm = np.linalg.norm(embedding)

    if norm == 0 or not np.isfinite(norm):
        raise ValueError(f"Invalid embedding: {image_path}")

    return embedding / norm


def main():
    print("Starting employee enrollment...")

    if not ENROLLMENT_DIR.exists():
        raise FileNotFoundError(ENROLLMENT_DIR)

    session = load_model()

    employee_ids = []
    employee_templates = []
    image_counts = []

    employee_dirs = sorted(
        path for path in ENROLLMENT_DIR.iterdir()
        if path.is_dir()
    )

    if not employee_dirs:
        raise RuntimeError(
            "No employee folders found inside enrollment directory."
        )

    for employee_dir in employee_dirs:
        employee_id = employee_dir.name

        image_paths = sorted(
            path for path in employee_dir.iterdir()
            if path.suffix.lower() in IMAGE_EXTENSIONS
        )

        if len(image_paths) < 2:
            print(
                f"Skipping {employee_id}: "
                "at least 2 aligned images are required."
            )
            continue

        print(f"\nEnrolling {employee_id}...")

        embeddings = []

        for image_path in image_paths:
            try:
                embedding = extract_embedding(session, image_path)
                embeddings.append(embedding)

                print(f"  Processed: {image_path.name}")

            except Exception as error:
                print(f"  Rejected {image_path.name}: {error}")

        if len(embeddings) < 2:
            print(f"Skipping {employee_id}: insufficient valid images.")
            continue

        # Average the normalized image embeddings
        template = np.mean(
            np.stack(embeddings),
            axis=0
        )

        # Normalize the employee reference template
        template_norm = np.linalg.norm(template)

        if template_norm == 0 or not np.isfinite(template_norm):
            print(f"Skipping {employee_id}: invalid template.")
            continue

        template = template / template_norm

        employee_ids.append(employee_id)
        employee_templates.append(template)
        image_counts.append(len(embeddings))

        print(
            f"  Enrollment successful: "
            f"{len(embeddings)} images, 512D template"
        )

    if not employee_templates:
        raise RuntimeError(
            "No employee templates were generated. "
            "Check the enrollment images."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(
        OUTPUT_PATH,
        employee_ids=np.array(employee_ids),
        templates=np.stack(employee_templates),
        image_counts=np.array(image_counts, dtype=np.int32)
    )

    print("\n========== ENROLLMENT SUMMARY ==========")
    print(f"Employees enrolled: {len(employee_ids)}")
    print(f"Template dimensions: {employee_templates[0].shape}")
    print(f"Templates saved: {OUTPUT_PATH}")

    for employee_id, count in zip(employee_ids, image_counts):
        print(f"  {employee_id}: {count} images")


if __name__ == "__main__":
    main()
