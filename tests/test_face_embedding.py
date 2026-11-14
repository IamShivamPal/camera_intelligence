import argparse
from pathlib import Path
import cv2
import numpy as np
import torch  # Load bundled CUDA/cuDNN DLLs for ONNX Runtime CUDAExecutionProvider
import onnxruntime as ort

ROOT = Path(__file__).resolve().parents[1]

MODEL_PATH = (
    ROOT / "ai_engine" / "models" / "face"
    / "auraface_v1_glintr100.onnx"
)

DEFAULT_FACE_PATH = (
    ROOT / "runs" / "face_alignment"
    / "aligned_face.jpg"
)

DEFAULT_OUTPUT_PATH = (
    ROOT / "runs" / "face_alignment"
    / "face_embedding.npy"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract 512D AuraFace embedding from a 112x112 aligned face."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_FACE_PATH,
        help="Path to the 112x112 aligned face image."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to save the normalized .npy embedding."
    )
    return parser.parse_args()


def main():
    args = parse_args()
    face_path = args.input if args.input.is_absolute() else ROOT / args.input
    output_path = args.output if args.output.is_absolute() else ROOT / args.output

    print("Starting AuraFace embedding extraction...")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(MODEL_PATH)

    if not face_path.exists():
        raise FileNotFoundError(face_path)

    session = ort.InferenceSession(
        str(MODEL_PATH),
        providers=[
            "CUDAExecutionProvider",
            "CPUExecutionProvider"
        ]
    )

    print("Active providers:", session.get_providers())

    image = cv2.imread(str(face_path))

    if image is None:
        raise RuntimeError("Could not read aligned face.")

    if image.shape[:2] != (112, 112):
        raise ValueError("Expected a 112x112 aligned face.")

    # BGR to RGB
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Convert pixel values from [0,255] to [-1,1].
    image = image.astype(np.float32)
    image = (image - 127.5) / 127.5

    # HWC -> CHW -> NCHW
    image = np.transpose(image, (2, 0, 1))
    image = np.expand_dims(image, axis=0)

    input_name = session.get_inputs()[0].name

    outputs = session.run(None, {input_name: image})
    raw_embedding = outputs[0][0]

    if raw_embedding.shape != (512,):
        raise RuntimeError(
            f"Unexpected embedding shape: {raw_embedding.shape}"
        )

    raw_norm = float(np.linalg.norm(raw_embedding))
    normalized_embedding = raw_embedding / max(raw_norm, 1e-12)
    final_norm = float(np.linalg.norm(normalized_embedding))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(output_path, normalized_embedding)

    print("\n========== EMBEDDING RESULTS ==========")
    print("Input image:", face_path)
    print("Embedding shape:", normalized_embedding.shape)
    print("Embedding dimensions:", normalized_embedding.shape[0])
    print(f"Raw L2 norm: {raw_norm:.6f}")
    print(f"Normalized L2 norm: {final_norm:.6f}")
    print("Sample values (first 5):", np.round(normalized_embedding[:5], 6))
    print("Saved embedding to:", output_path)
    print("\nEmbedding extraction completed successfully.")


if __name__ == "__main__":
    main()

