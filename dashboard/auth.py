from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import bcrypt

Role = Literal["Admin", "Analyst", "Viewer"]

MAX_BCRYPT_BYTES = 72


@dataclass(frozen=True)
class User:
    username: str
    role: Role


def _users_path() -> Path:
    # project_root/config/users.json
    return Path(__file__).resolve().parents[1] / "config" / "users.json"

def _users_example_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "users.example.json"


def load_users() -> dict[str, dict]:
    """
    Loads config/users.json:
      { "users": [ {"username": "...", "password_bcrypt": "...", "role": "Admin"} ] }
    """
    p = _users_path()
    if not p.exists():
        # No users file yet — allow the app to show Register UI.
        return {}

    data = json.loads(p.read_text(encoding="utf-8"))
    users = data.get("users", [])
    by_name: dict[str, dict] = {}
    for u in users:
        if not u.get("username"):
            continue
        by_name[u["username"]] = u
    return by_name


def authenticate(username: str, password: str) -> Optional[User]:
    # bcrypt only uses first 72 bytes; reject longer to avoid surprising truncation.
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) > MAX_BCRYPT_BYTES:
        return None

    # Optional "super admin" via environment (works even if users.json is missing).
    # Set in .env:
    #   SUPER_ADMIN_USERNAME=admin
    #   SUPER_ADMIN_PASSWORD_BCRYPT=$2b$12$...
    super_user = (os.getenv("SUPER_ADMIN_USERNAME") or "").strip()
    super_hash = os.getenv("SUPER_ADMIN_PASSWORD_BCRYPT") or ""
    if super_user and super_hash and username == super_user:
        try:
            if bcrypt.checkpw(pw_bytes, super_hash.encode("utf-8")):
                return User(username=username, role="Admin")
        except Exception:
            return User(username=username, role="Admin")

    users = load_users()
    u = users.get(username)
    if not u:
        return None
    pw_hash = u.get("password_bcrypt") or ""
    if not pw_hash:
        return None
    try:
        if not bcrypt.checkpw(pw_bytes, pw_hash.encode("utf-8")):
            return None
    except Exception:
        return None
    role: Role = u.get("role", "Viewer")
    return User(username=username, role=role)


def _read_users_doc() -> dict:
    p = _users_path()
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    ex = _users_example_path()
    if ex.exists():
        doc = json.loads(ex.read_text(encoding="utf-8"))
        doc["users"] = []
        return doc
    return {"users": []}


def _write_users_doc(doc: dict) -> None:
    p = _users_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2), encoding="utf-8")


def register_user(username: str, password: str, role: Role = "Viewer") -> User:
    username = (username or "").strip()
    if not username:
        raise ValueError("Username is required.")
    if len(username) < 3:
        raise ValueError("Username must be at least 3 characters.")
    if any(ch.isspace() for ch in username):
        raise ValueError("Username cannot contain spaces.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) > MAX_BCRYPT_BYTES:
        raise ValueError("Password too long (bcrypt supports max 72 bytes). Use a shorter password.")

    doc = _read_users_doc()
    users = doc.get("users", [])
    if not isinstance(users, list):
        users = []

    if any((u.get("username") == username) for u in users):
        raise ValueError("Username already exists.")

    pw_hash = bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")
    users.append({"username": username, "password_bcrypt": pw_hash, "role": role})
    doc["users"] = users
    _write_users_doc(doc)
    return User(username=username, role=role)


# -------------------------
# Admin user management APIs
# -------------------------

def list_users_for_admin() -> list[dict]:
    """
    Returns users as a list of dicts: [{username, role}...]
    (password hashes are intentionally not returned)
    """
    users = load_users()
    out: list[dict] = []
    for username, u in users.items():
        out.append({"username": username, "role": u.get("role", "Viewer")})
    out.sort(key=lambda x: (str(x.get("role")), str(x.get("username"))))
    return out


def _validate_username(username: str) -> str:
    username = (username or "").strip()
    if not username:
        raise ValueError("Username is required.")
    if len(username) < 3:
        raise ValueError("Username must be at least 3 characters.")
    if any(ch.isspace() for ch in username):
        raise ValueError("Username cannot contain spaces.")
    return username


def _hash_password(password: str) -> str:
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) > MAX_BCRYPT_BYTES:
        raise ValueError("Password too long (bcrypt supports max 72 bytes). Use a shorter password.")
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def admin_create_user(username: str, password: str, role: Role = "Viewer") -> User:
    username = _validate_username(username)
    doc = _read_users_doc()
    users = doc.get("users", [])
    if not isinstance(users, list):
        users = []
    if any((u.get("username") == username) for u in users):
        raise ValueError("Username already exists.")
    users.append({"username": username, "password_bcrypt": _hash_password(password), "role": role})
    doc["users"] = users
    _write_users_doc(doc)
    return User(username=username, role=role)


def admin_set_role(username: str, role: Role) -> None:
    username = _validate_username(username)
    doc = _read_users_doc()
    users = doc.get("users", [])
    if not isinstance(users, list):
        users = []
    for u in users:
        if u.get("username") == username:
            u["role"] = role
            doc["users"] = users
            _write_users_doc(doc)
            return
    raise ValueError("User not found.")


def admin_reset_password(username: str, new_password: str) -> None:
    username = _validate_username(username)
    doc = _read_users_doc()
    users = doc.get("users", [])
    if not isinstance(users, list):
        users = []
    for u in users:
        if u.get("username") == username:
            u["password_bcrypt"] = _hash_password(new_password)
            doc["users"] = users
            _write_users_doc(doc)
            return
    raise ValueError("User not found.")


def admin_delete_user(username: str) -> None:
    username = _validate_username(username)
    doc = _read_users_doc()
    users = doc.get("users", [])
    if not isinstance(users, list):
        users = []
    new_users = [u for u in users if u.get("username") != username]
    if len(new_users) == len(users):
        raise ValueError("User not found.")
    doc["users"] = new_users
    _write_users_doc(doc)


