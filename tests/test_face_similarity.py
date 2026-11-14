from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FACE_DIR = ROOT / "runs" / "face_alignment"

IMAGE_1 = FACE_DIR / "face_embedding_2.npy"
IMAGE_2 = FACE_DIR / "face_embedding_3.npy"


def load_embedding(path):
    if not path.exists():
        raise FileNotFoundError(path)

    embedding = np.load(path).astype(np.float32)

    if embedding.shape != (512,):
        raise ValueError(
            f"Expected 512 dimensions, got {embedding.shape}"
        )

    norm = np.linalg.norm(embedding)
    if norm == 0 or not np.isfinite(norm):
        raise ValueError("Invalid embedding.")

    return embedding / norm


def cosine_similarity(first, second):
    return float(np.dot(first, second))


def main():
    print("Starting face similarity evaluation...")
    print("Comparing Frame 215 vs Frame 240")

    first = load_embedding(IMAGE_1)
    second = load_embedding(IMAGE_2)

    similarity = cosine_similarity(first, second)

    print("\n========== SIMILARITY RESULTS ==========")
    print(f"Cosine similarity: {similarity:.6f}")
    print("\nInterpretation:")
    print("Higher similarity means more similar embeddings.")
    print("This single comparison cannot establish an identity threshold.")


if __name__ == "__main__":
    main()

