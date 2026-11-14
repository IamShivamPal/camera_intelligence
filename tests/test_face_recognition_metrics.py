
from pathlib import Path
import csv
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

CSV_PATH = (
    ROOT / "runs" / "face_recognition_evaluation" / "pair_scores.csv"
)

OUTPUT_DIR = ROOT / "runs" / "face_recognition_evaluation"


def load_scores():
    if not CSV_PATH.exists():
        raise FileNotFoundError(CSV_PATH)

    genuine = []
    impostor = []

    with CSV_PATH.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            score = float(row["cosine_similarity"])

            if row["pair_type"] == "genuine":
                genuine.append(score)
            elif row["pair_type"] == "impostor":
                impostor.append(score)

    if not genuine or not impostor:
        raise ValueError("Both genuine and impostor scores are required.")

    return np.array(genuine), np.array(impostor)


def calculate_metrics(genuine, impostor):
    all_scores = np.concatenate([genuine, impostor])
    thresholds = np.sort(np.unique(all_scores))

    results = []

    for threshold in thresholds:
        far = np.mean(impostor >= threshold)
        frr = np.mean(genuine < threshold)

        results.append({
            "threshold": float(threshold),
            "far": float(far),
            "frr": float(frr),
        })

    # Find the point where FAR and FRR are closest.
    eer_index = min(
        range(len(results)),
        key=lambda i: abs(results[i]["far"] - results[i]["frr"])
    )

    eer_result = results[eer_index]

    # Calculate ROC AUC using the Mann-Whitney rank statistic.
    # Ties receive average ranks.
    labels = np.concatenate([
        np.ones(len(genuine)),
        np.zeros(len(impostor))
    ])

    scores = np.concatenate([genuine, impostor])

    order = np.argsort(scores)
    sorted_scores = scores[order]

    ranks = np.empty(len(scores), dtype=float)

    start = 0
    while start < len(scores):
        end = start + 1

        while (
            end < len(scores)
            and sorted_scores[end] == sorted_scores[start]
        ):
            end += 1

        average_rank = (start + 1 + end) / 2
        ranks[order[start:end]] = average_rank
        start = end

    positive_ranks = np.sum(ranks[labels == 1])

    auc = (
        positive_ranks
        - len(genuine) * (len(genuine) + 1) / 2
    ) / (len(genuine) * len(impostor))

    return results, eer_result, auc


def save_roc_data(results):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = OUTPUT_DIR / "roc_metrics.csv"

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["threshold", "far", "frr"]
        )
        writer.writeheader()
        writer.writerows(results)

    return output_path


def main():
    print("Starting ROC / EER evaluation...")

    genuine, impostor = load_scores()

    print(f"Genuine pairs: {len(genuine)}")
    print(f"Impostor pairs: {len(impostor)}")

    results, eer_result, auc = calculate_metrics(
        genuine,
        impostor
    )

    output_path = save_roc_data(results)

    print("\n========== ROC / EER RESULTS ==========")
    print(f"ROC AUC: {auc:.4f}")
    print(f"EER threshold: {eer_result['threshold']:.4f}")
    print(f"Approximate EER: {(eer_result['far'] + eer_result['frr']) / 2 * 100:.2f}%")
    print(f"FAR at EER: {eer_result['far'] * 100:.2f}%")
    print(f"FRR at EER: {eer_result['frr'] * 100:.2f}%")

    print(f"\nROC data saved to: {output_path}")
    print("\nThese are diagnostic results, not production guarantees.")


if __name__ == "__main__":
    main()
