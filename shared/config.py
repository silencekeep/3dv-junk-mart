from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _resolve_repo_path(value: str | None, default: Path) -> Path:
    raw_value = (value or "").strip()
    if not raw_value:
        return default.resolve()

    candidate = Path(raw_value).expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate.resolve()


def _resolve_float_env(name: str, default: float) -> float:
    raw_value = (os.getenv(name) or "").strip()
    if not raw_value:
        return default

    try:
        parsed = float(raw_value)
    except ValueError:
        return default
    return max(parsed, 1.0)


STORAGE_ROOT = _resolve_repo_path(os.getenv("STORAGE_ROOT"), REPO_ROOT / "storage")
VIEWER_ROOT = _resolve_repo_path(os.getenv("VIEWER_ROOT"), REPO_ROOT / "viewer")
SQLITE_DB_PATH = _resolve_repo_path(os.getenv("SQLITE_DB_PATH"), STORAGE_ROOT / "db" / "business.db")

GS_SERVICE_BASE_URL = (
    (os.getenv("GS_SERVICE_BASE_URL") or os.getenv("TRAINER_SERVICE_BASE_URL") or "http://127.0.0.1:9000")
    .strip()
    .rstrip("/")
)
GS_SERVICE_PUBLIC_BASE_URL = (
    (os.getenv("GS_SERVICE_PUBLIC_BASE_URL") or os.getenv("TRAINER_SERVICE_PUBLIC_BASE_URL") or "")
    .strip()
    .rstrip("/")
    or None
)
GS_SERVICE_TIMEOUT_SECONDS = _resolve_float_env(
    "GS_SERVICE_TIMEOUT_SECONDS",
    _resolve_float_env("TRAINER_SERVICE_TIMEOUT_SECONDS", 30.0),
)

# Backward-compatible aliases for the current transition phase.
TRAINER_SERVICE_BASE_URL = GS_SERVICE_BASE_URL
TRAINER_SERVICE_PUBLIC_BASE_URL = GS_SERVICE_PUBLIC_BASE_URL
TRAINER_SERVICE_TIMEOUT_SECONDS = GS_SERVICE_TIMEOUT_SECONDS
TRAINER_SERVICE_AUTH_TOKEN = (os.getenv("TRAINER_SERVICE_AUTH_TOKEN") or "").strip() or None
BUSINESS_DB_PATH = SQLITE_DB_PATH


def trainer_service_headers() -> dict[str, str]:
    if not TRAINER_SERVICE_AUTH_TOKEN:
        return {}
    return {"X-Internal-Token": TRAINER_SERVICE_AUTH_TOKEN}
