"""
Create/update an Admin user in config/users.json (non-interactive).

Usage (PowerShell):
  python .\\scripts\\bootstrap_admin_user.py --username admin --password "Admin@12345"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bcrypt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
USERS_PATH = PROJECT_ROOT / "config" / "users.json"
USERS_EXAMPLE = PROJECT_ROOT / "config" / "users.example.json"
MAX_BCRYPT_BYTES = 72


def load_users_doc() -> dict:
    if USERS_PATH.exists():
        return json.loads(USERS_PATH.read_text(encoding="utf-8"))
    if USERS_EXAMPLE.exists():
        doc = json.loads(USERS_EXAMPLE.read_text(encoding="utf-8"))
        doc["users"] = []
        return doc
    return {"users": []}


def save_users_doc(doc: dict) -> None:
    USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    USERS_PATH.write_text(json.dumps(doc, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--username", default="admin")
    ap.add_argument("--password", required=True)
    ap.add_argument("--role", choices=["Admin", "Analyst", "Viewer"], default="Admin")
    args = ap.parse_args()

    pw = args.password
    if len(pw) < 6:
        raise SystemExit("Password too short (min 6 chars).")
    if len(pw.encode("utf-8")) > MAX_BCRYPT_BYTES:
        raise SystemExit("Password too long (bcrypt supports max 72 bytes). Use a shorter password.")

    pw_hash = bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    doc = load_users_doc()
    users = doc.get("users", [])
    if not isinstance(users, list):
        users = []

    updated = False
    for u in users:
        if u.get("username") == args.username:
            u["password_bcrypt"] = pw_hash
            u["role"] = args.role
            updated = True
            break

    if not updated:
        users.append({"username": args.username, "password_bcrypt": pw_hash, "role": args.role})

    doc["users"] = users
    save_users_doc(doc)
    print(f"Wrote {USERS_PATH} (user={args.username}, role={args.role})")


if __name__ == "__main__":
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    main()


