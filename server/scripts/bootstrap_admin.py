#!/usr/bin/env python3
"""
Camera Intelligence — Administrative Bootstrap CLI
Securely creates the initial super_admin user.

Usage:
  python server/scripts/bootstrap_admin.py --email admin@example.com --password SecretPassword123
  python server/scripts/bootstrap_admin.py (prompts interactively or reads from environment)

Environment Variables:
  BOOTSTRAP_SUPERADMIN_EMAIL
  BOOTSTRAP_SUPERADMIN_PASSWORD
  BOOTSTRAP_SUPERADMIN_FULL_NAME (optional)
"""

import sys
import os
import argparse
import getpass
from pathlib import Path

# Add server root to sys.path
SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.database.session import SessionLocal
from app.services.bootstrap import bootstrap_super_admin


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap initial super_admin user for Camera Intelligence."
    )
    parser.add_argument(
        "--email",
        type=str,
        default=os.getenv("BOOTSTRAP_SUPERADMIN_EMAIL"),
        help="Super admin email (or via BOOTSTRAP_SUPERADMIN_EMAIL env var)",
    )
    parser.add_argument(
        "--password",
        type=str,
        default=os.getenv("BOOTSTRAP_SUPERADMIN_PASSWORD"),
        help="Super admin password (or via BOOTSTRAP_SUPERADMIN_PASSWORD env var)",
    )
    parser.add_argument(
        "--full-name",
        type=str,
        default=os.getenv("BOOTSTRAP_SUPERADMIN_FULL_NAME", "System Administrator"),
        help="Super admin full name (default: 'System Administrator')",
    )

    args = parser.parse_args()

    email = args.email
    password = args.password
    full_name = args.full_name

    # Interactive prompt if email is not supplied
    if not email:
        try:
            email = input("Enter super_admin email: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.", file=sys.stderr)
            return 1

    # Secure interactive prompt if password is not supplied
    if not password:
        try:
            password = getpass.getpass("Enter super_admin password (min 8 chars): ")
            confirm = getpass.getpass("Confirm super_admin password: ")
            if password != confirm:
                print("Error: Passwords do not match.", file=sys.stderr)
                return 1
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.", file=sys.stderr)
            return 1

    db = SessionLocal()
    try:
        user, created, message = bootstrap_super_admin(
            db=db,
            email=email,
            password=password,
            full_name=full_name,
        )

        status_label = "CREATED" if created else "ALREADY_EXISTS"
        print(f"[{status_label}] {message}")
        print(f"User ID: {user.id}")
        print(f"Email: {user.email}")
        print(f"Role: {user.system_role}")
        print(f"Active: {user.is_active}")
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error during bootstrap: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

