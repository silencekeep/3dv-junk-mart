from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if os.name == "nt":
    import msvcrt
else:
    import fcntl

STATUSES = {
    "uploaded",
    "queued",
    "preprocessing",
    "awaiting_mask_prompt",
    "awaiting_mask_confirmation",
    "masking",
    "training",
    "exporting",
    "ready",
    "failed",
    "cancelled",
}

REPO_ROOT = Path(__file__).resolve().parents[1]
STORAGE_ROOT = REPO_ROOT / "storage"
TASKS_ROOT = STORAGE_ROOT / "tasks"
UPLOADS_ROOT = STORAGE_ROOT / "uploads"
PROCESSED_ROOT = STORAGE_ROOT / "processed"
MODELS_ROOT = STORAGE_ROOT / "models"
VIEWER_ROOT = REPO_ROOT / "viewer"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_layout() -> None:
    for path in (STORAGE_ROOT, TASKS_ROOT, UPLOADS_ROOT, PROCESSED_ROOT, MODELS_ROOT, VIEWER_ROOT):
        path.mkdir(parents=True, exist_ok=True)


def generate_task_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"task_{timestamp}_{suffix}"


def task_file_path(task_id: str) -> Path:
    return TASKS_ROOT / f"{task_id}.json"


def task_upload_dir(task_id: str) -> Path:
    return UPLOADS_ROOT / task_id


def task_processed_dir(task_id: str) -> Path:
    return PROCESSED_ROOT / task_id


def task_model_dir(task_id: str) -> Path:
    return MODELS_ROOT / task_id


def lock_file_path(path: Path) -> Path:
    return path.with_suffix(f"{path.suffix}.lock")


@contextmanager
def file_lock(path: Path):
    lock_path = lock_file_path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with lock_path.open("a+b") as lock_handle:
        if os.name == "nt":
            lock_handle.seek(0)
            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)

        try:
            yield
        finally:
            if os.name == "nt":
                lock_handle.seek(0)
                msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def path_to_storage_url(path: Path | None) -> str | None:
    if path is None:
        return None

    try:
        relative = path.resolve().relative_to(STORAGE_ROOT.resolve())
    except ValueError:
        return None

    return "/storage/" + relative.as_posix()


def build_task_record(
    *,
    task_id: str,
    title: str,
    description: str,
    price: str,
    source_filename: str,
    video_path: Path,
    video_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    created_at = now_iso()
    return {
        "task_id": task_id,
        "title": title,
        "description": description,
        "price": price,
        "status": "uploaded",
        "progress": 0,
        "status_message": "任务已创建，等待进入流水线",
        "error_message": None,
        "source_filename": source_filename,
        "video_rel_path": path_to_storage_url(video_path),
        "processed_rel_path": None,
        "model_rel_path": None,
        "model_ply_rel_path": None,
        "model_sog_rel_path": None,
        "model_format": None,
        "log_rel_path": None,
        "log_tail": [],
        "train_step": None,
        "train_total_steps": None,
        "train_eta": None,
        "train_max_steps": None,
        "quality_profile": None,
        "object_masking": False,
        "mask_prompt_frame_rel_path": None,
        "mask_prompt_frame_name": None,
        "mask_prompt_frame_width": None,
        "mask_prompt_frame_height": None,
        "mask_prompts_rel_path": None,
        "mask_preview_rel_path": None,
        "mask_preview_manifest_rel_path": None,
        "mask_summary_rel_path": None,
        "pipeline_pid": None,
        "mock_mode": False,
        "is_published": False,
        "published_at": None,
        "viewer_rotation_done": False,
        "viewer_translation_done": False,
        "viewer_initial_view_done": False,
        "viewer_animation_approved": False,
        "video_metadata": video_metadata,
        "created_at": created_at,
        "updated_at": created_at,
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path):
        temp_path = path.parent / f".{path.stem}.{uuid.uuid4().hex}.tmp"

        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())

        last_error: PermissionError | None = None
        for _ in range(40):
            try:
                os.replace(temp_path, path)
                return
            except PermissionError as exc:
                last_error = exc
                time.sleep(0.05)

        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass

        if last_error is not None:
            raise last_error


def save_task(task: dict[str, Any]) -> dict[str, Any]:
    task["updated_at"] = now_iso()
    atomic_write_json(task_file_path(task["task_id"]), task)
    return task


def get_task(task_id: str) -> dict[str, Any] | None:
    path = task_file_path(task_id)
    if not path.exists():
        return None

    with file_lock(path):
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)


def create_task(task: dict[str, Any]) -> dict[str, Any]:
    ensure_layout()
    return save_task(task)


def update_task(task_id: str, **changes: Any) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise FileNotFoundError(f"Task '{task_id}' not found.")

    task.update(changes)
    return save_task(task)


def list_tasks(*, statuses: set[str] | None = None) -> list[dict[str, Any]]:
    ensure_layout()
    tasks: list[dict[str, Any]] = []

    for path in TASKS_ROOT.glob("*.json"):
        with file_lock(path):
            with path.open("r", encoding="utf-8") as handle:
                task = json.load(handle)

        if statuses and task.get("status") not in statuses:
            continue

        tasks.append(task)

    tasks.sort(key=lambda task: task.get("created_at", ""), reverse=True)
    return tasks


def delete_task(task_id: str) -> None:
    task_path = task_file_path(task_id)
    if not task_path.exists():
        raise FileNotFoundError(f"Task '{task_id}' not found.")

    with file_lock(task_path):
        task_path.unlink(missing_ok=True)

    for path in (
        lock_file_path(task_path),
        task_upload_dir(task_id),
        task_processed_dir(task_id),
        task_model_dir(task_id),
    ):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError:
            continue
