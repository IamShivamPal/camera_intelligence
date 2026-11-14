
from pathlib import Path
import torch
import numpy as np
import onnxruntime as ort


ROOT = Path(__file__).resolve().parent.parent

MODEL_PATH = (
    ROOT
    / "ai_engine"
    / "models"
    / "face"
    / "auraface_v1_glintr100.onnx"
)


def main():
    print("Starting AuraFace GPU test...")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    print(f"Model size: {MODEL_PATH.stat().st_size / (1024**2):.2f} MB")

    available = ort.get_available_providers()
    print("Available providers:", available)

    if "CUDAExecutionProvider" not in available:
        raise RuntimeError("CUDAExecutionProvider is unavailable.")

    print("\nLoading AuraFace with CUDA...")


    print("\nPreloading CUDA and cuDNN libraries...")

    ort.preload_dlls(directory="")

    ort.print_debug_info()

    session = ort.InferenceSession(
        str(MODEL_PATH),
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
    )

    print("Active providers:", session.get_providers())

    if "CUDAExecutionProvider" not in session.get_providers():
        raise RuntimeError("CUDA provider was not activated.")

    inputs = session.get_inputs()
    outputs = session.get_outputs()

    print("\nModel inputs:")
    for item in inputs:
        print(f"Name: {item.name}, Shape: {item.shape}, Type: {item.type}")

    print("\nModel outputs:")
    for item in outputs:
        print(f"Name: {item.name}, Shape: {item.shape}, Type: {item.type}")

    if len(inputs) != 1:
        raise RuntimeError(
            f"Expected one model input, found {len(inputs)}."
        )

    input_info = inputs[0]

    # Use the model's declared dimensions.
    shape = [
        dim if isinstance(dim, int) and dim > 0 else 1
        for dim in input_info.shape
    ]

    dummy_input = np.zeros(shape, dtype=np.float32)

    print("\nRunning test inference...")
    results = session.run(
        None,
        {input_info.name: dummy_input},
    )

    for index, result in enumerate(results):
        print(
            f"Output {index}: "
            f"shape={result.shape}, dtype={result.dtype}"
        )

    embedding = results[0]

    if embedding.ndim != 2 or embedding.shape[0] != 1:
        raise RuntimeError(
            f"Unexpected embedding output shape: {embedding.shape}"
        )

    print("\nAuraFace model test completed successfully.")


if __name__ == "__main__":
    main()
