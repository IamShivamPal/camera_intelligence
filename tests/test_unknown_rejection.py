
from pathlib import Path
import argparse
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

VERIFICATION_SCRIPT = ROOT / "tests" / "test_employee_verification.py"


def main():
    parser = argparse.ArgumentParser(
        description="Test rejection of an unregistered person."
    )

    parser.add_argument(
        "--image",
        required=True,
        help="Path to an aligned 112x112 unknown face image."
    )

    parser.add_argument(
        "--threshold",
        type=float,
        required=True,
        help="Experimental similarity threshold."
    )

    args = parser.parse_args()

    image_path = Path(args.image)

    if not image_path.is_absolute():
        image_path = ROOT / image_path

    if not image_path.exists():
        raise FileNotFoundError(
            f"Unknown face image not found: {image_path}"
        )

    print("Starting unknown-person rejection test...")
    print(f"Input: {image_path}")

    command = [
        sys.executable,
        str(VERIFICATION_SCRIPT),
        "--image",
        str(image_path),
        "--threshold",
        str(args.threshold)
    ]

    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True
    )

    print(result.stdout)

    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError("Verification process failed.")

    if "Predicted identity: UNKNOWN" in result.stdout:
        print("PASS: Unregistered person was rejected.")
    else:
        print("FAIL: Unregistered person was matched to an enrolled identity.")
        print("Review the similarity scores and threshold.")

    print("\nThis is a diagnostic test, not a security guarantee.")


if __name__ == "__main__":
    main()

