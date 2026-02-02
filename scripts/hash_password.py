r"""
Generate a bcrypt hash for a password (to paste into .env).

Usage:
  python .\scripts\hash_password.py
"""

from __future__ import annotations

import getpass

import bcrypt

MAX_BCRYPT_BYTES = 72


def main() -> None:
    pw = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm: ")
    if pw != confirm:
        raise SystemExit("Passwords do not match.")
    if len(pw) < 6:
        raise SystemExit("Password too short (min 6 chars).")
    if len(pw.encode("utf-8")) > MAX_BCRYPT_BYTES:
        raise SystemExit("Password too long (bcrypt supports max 72 bytes). Use a shorter password.")

    print("\nPaste this into your .env as SUPER_ADMIN_PASSWORD_BCRYPT:\n")
    print(bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"))


if __name__ == "__main__":
    main()


