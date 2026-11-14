
from pathlib import Path
import argparse

import cv2
import numpy as np

# Import torch before ONNX Runtime for CUDA DLL compatibility on Windows.
import torch
import onnxruntime as ort


ROOT = Path(__file__).resolve().parents[1]

MODEL_PATH = (
    ROOT / "ai_engine" / "models" / "face" / "auraface_v1_glintr100.onnx"
)

TEMPLATE_PATH = (
    ROOT / "runs" / "employee_enrollment" / "employee_templates.npz"
)


def load_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

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


def load_templates():
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"Employee templates not found: {TEMPLATE_PATH}"
        )

    data = np.load(TEMPLATE_PATH, allow_pickle=False)

    employee_ids = data["employee_ids"].astype(str)
    templates = data["templates"].astype(np.float32)

    if templates.shape != (len(employee_ids), 512):
        raise ValueError(
            f"Invalid template dimensions: {templates.shape}"
        )

    if not np.all(np.isfinite(templates)):
        raise ValueError("Templates contain invalid values.")

    norms = np.linalg.norm(templates, axis=1)

    if np.any(norms == 0):
        raise ValueError("A template has zero norm.")

    templates = templates / norms[:, None]

    return employee_ids, templates


def extract_embedding(session, image_path):
    image = cv2.imread(str(image_path))

    if image is None:
        raise ValueError(f"Could not read image: {image_path}")

    if image.shape[:2] != (112, 112):
        raise ValueError(
            f"Expected an aligned 112x112 image, "
            f"received {image.shape[1]}x{image.shape[0]}"
        )

    # BGR to RGB
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Same AuraFace preprocessing as enrollment
    image = image.astype(np.float32)
    image = (image - 127.5) / 127.5

    # HWC -> NCHW
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
        raise ValueError("Invalid face embedding.")

    return embedding / norm


def recognize_face(embedding, employee_ids, templates, threshold):
    # Each template is normalized, as is the incoming embedding.
    similarities = templates @ embedding

    best_index = int(np.argmax(similarities))
    best_employee = employee_ids[best_index]
    best_similarity = float(similarities[best_index])

    rankings = np.argsort(similarities)[::-1]

    print("\n========== MATCH RANKINGS ==========")

    for index in rankings:
        print(
            f"{employee_ids[index]}: "
            f"{similarities[index]:.6f}"
        )

    if best_similarity >= threshold:
        return best_employee, best_similarity

    return "UNKNOWN", best_similarity


def main():
    parser = argparse.ArgumentParser(
        description="Test AuraFace employee verification."
    )

    parser.add_argument(
        "--image",
        required=True,
        help="Path to an aligned 112x112 face image."
    )

    parser.add_argument(
        "--threshold",
        required=True,
        type=float,
        help="Experimental cosine similarity threshold."
    )

    args = parser.parse_args()

    if not -1.0 <= args.threshold <= 1.0:
        parser.error("Threshold must be between -1 and 1.")

    image_path = Path(args.image)

    if not image_path.is_absolute():
        image_path = ROOT / image_path

    print("Starting employee face verification...")
    print(f"Input image: {image_path}")
    print(f"Experimental threshold: {args.threshold:.4f}")

    session = load_model()

    employee_ids, templates = load_templates()

    print(f"Enrolled employees: {len(employee_ids)}")

    embedding = extract_embedding(session, image_path)

    identity, similarity = recognize_face(
        embedding,
        employee_ids,
        templates,
        args.threshold
    )

    print("\n========== VERIFICATION RESULT ==========")
    print(f"Predicted identity: {identity}")
    print(f"Best similarity: {similarity:.6f}")

    if identity == "UNKNOWN":
        print("Result: No employee matched the supplied threshold.")
    else:
        print("Result: An enrolled employee passed the threshold.")

    print("\nNote: This is a prototype verification test.")
    print("Do not use this threshold for production access decisions.")


if __name__ == "__main__":
    main()
