import os
from pathlib import Path

from firebolt.client.auth import ClientCredentials
from firebolt.db import connect


def load_dotenv_if_present(project_root: Path | None = None) -> None:
    """
    Minimal .env loader to avoid extra dependencies.
    Loads KEY=VALUE pairs into environment only if the key isn't already set.
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent

    dotenv_path = project_root / ".env"
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_firebolt_settings() -> dict:
    load_dotenv_if_present()

    required = ["FIREBOLT_SERVICE_ACCOUNT_ID", "FIREBOLT_SERVICE_ACCOUNT_SECRET"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            "Missing required Firebolt environment variables: "
            + ", ".join(missing)
            + "\nCreate a project-root .env file (recommended) or set them in your shell."
        )

    return {
        "service_account_id": os.environ["FIREBOLT_SERVICE_ACCOUNT_ID"],
        "service_account_secret": os.environ["FIREBOLT_SERVICE_ACCOUNT_SECRET"],
        "account_name": os.getenv("FIREBOLT_ACCOUNT_NAME", ""),
        "engine_name": os.getenv("FIREBOLT_ENGINE_NAME", ""),
        "database": os.getenv("FIREBOLT_DATABASE", ""),
    }


def connect_firebolt():
    s = get_firebolt_settings()
    return connect(
        auth=ClientCredentials(s["service_account_id"], s["service_account_secret"]),
        account_name=s["account_name"] or None,
        engine_name=s["engine_name"] or None,
        database=s["database"] or None,
    )


