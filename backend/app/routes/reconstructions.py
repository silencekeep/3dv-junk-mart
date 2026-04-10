from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote, urlencode

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile, status

from backend.app.schemas import (
    MaskPromptRequest,
    PipelineStartRequest,
    PublishFlowStateUpdate,
    ReconstructionTaskResponse,
    ViewerConfigResponse,
    ViewerConfigUpdate,
)
from backend.app.services.trainer_service_client import TrainerServiceError, get_trainer_service_client
from shared.task_store import (
    REPO_ROOT,
    STORAGE_ROOT,
    atomic_write_json,
    build_task_record,
    create_task,
    delete_task,
    generate_task_id,
    get_task,
    list_tasks,
    now_iso,
    path_to_storage_url,
    task_model_dir,
    task_processed_dir,
    task_upload_dir,
    update_task,
)
from trainer.pipeline import (
    PipelineReporter,
    adapt_quality_profile_to_video,
    build_sam2_preview_command,
    format_command_failure,
    restore_effective_quality_profile,
    select_mask_prompt_frame,
    resolve_quality_profile,
    resolve_train_max_steps,
    run_logged_streaming_command,
)

router = APIRouter(prefix="/api/v1/reconstructions", tags=["reconstructions"])

AUTO_START_PIPELINE = False
AUTO_START_PIPELINE_MOCK = os.getenv("BACKEND_PIPELINE_MOCK", "false").lower() == "true"
VIEWER_BUILD_VERSION = "20260408_43"
PIPELINE_ACTIVE_STATUSES = {"queued", "preprocessing", "masking", "training", "exporting"}
MASK_INTERACTION_STATUSES = {"awaiting_mask_prompt", "awaiting_mask_confirmation"}
PIPELINE_CANCELABLE_STATUSES = PIPELINE_ACTIVE_STATUSES | MASK_INTERACTION_STATUSES
PIPELINE_STARTABLE_STATUSES = {"uploaded", "failed", "cancelled"}
DEFAULT_VIEWER_CONFIG = {
    "model_rotation_deg": [0, 0, 0],
    "model_translation": [0, 0, 0],
    "model_scale": 1.0,
    "camera_rotation_deg": [-18, 26, 0],
    "camera_distance": 1.6,
}

UPLOAD_VIDEO_MAX_DURATION_SECONDS = 60
LOCAL_TASK_PRESERVE_FIELDS = {
    "is_published",
    "published_at",
    "viewer_rotation_done",
    "viewer_translation_done",
    "viewer_initial_view_done",
    "viewer_animation_approved",
}
REMOTE_TASK_URL_FIELD_MAP = {
    "video_url": "video_rel_path",
    "model_url": "model_rel_path",
    "model_ply_url": "model_ply_rel_path",
    "model_sog_url": "model_sog_rel_path",
    "log_url": "log_rel_path",
    "mask_prompt_frame_url": "mask_prompt_frame_rel_path",
    "mask_prompts_url": "mask_prompts_rel_path",
    "mask_preview_url": "mask_preview_rel_path",
    "mask_preview_manifest_url": "mask_preview_manifest_rel_path",
    "mask_summary_url": "mask_summary_rel_path",
    "viewer_url": "viewer_url",
}


def _probe_uploaded_video(video_path: Path) -> dict[str, object]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise HTTPException(
            status_code=400,
            detail=result.stderr.strip() or "视频元数据校验失败，请确认上传的是有效视频。",
        )

    try:
        metadata = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"无法解析视频元数据：{exc}") from exc

    if not isinstance(metadata, dict):
        raise HTTPException(status_code=400, detail="视频元数据格式不正确。")
    return metadata


def _validate_uploaded_video(video_path: Path) -> dict[str, object]:
    metadata = _probe_uploaded_video(video_path)
    streams = metadata.get("streams")
    format_meta = metadata.get("format")
    if not isinstance(streams, list) or not isinstance(format_meta, dict):
        raise HTTPException(status_code=400, detail="视频元数据不完整。")

    video_stream = next(
        (
            stream
            for stream in streams
            if isinstance(stream, dict) and stream.get("codec_type") == "video"
        ),
        None,
    )
    if video_stream is None:
        raise HTTPException(status_code=400, detail="上传文件中未检测到有效视频流。")

    try:
        duration = float(format_meta.get("duration", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="无法识别视频时长。") from exc

    if duration <= 0:
        raise HTTPException(status_code=400, detail="视频时长无效，请重新录制或选择视频。")
    if duration > UPLOAD_VIDEO_MAX_DURATION_SECONDS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"视频时长 {duration:.2f}s 超过 {UPLOAD_VIDEO_MAX_DURATION_SECONDS}s 限制。"
            ),
        )

    return metadata


def _absolute_url(request: Request, rel_url: str | None) -> str | None:
    if not rel_url:
        return None

    if rel_url.startswith("http://") or rel_url.startswith("https://"):
        return rel_url

    base = str(request.base_url).rstrip("/")
    absolute = f"{base}{rel_url}"
    if not rel_url.startswith("/storage/"):
        return absolute

    storage_path = STORAGE_ROOT / rel_url.removeprefix("/storage/")
    try:
        stat = storage_path.stat()
    except OSError:
        return absolute

    separator = "&" if "?" in absolute else "?"
    return f"{absolute}{separator}v={stat.st_mtime_ns}_{stat.st_size}"


def _append_viewer_param(query: dict[str, str], key: str, value: object | None) -> None:
    if value is None:
        return
    query[key] = str(value)


def _load_viewer_query(task_id: str) -> dict[str, str]:
    payload = _load_viewer_config(task_id)
    if not payload:
        return {}

    query: dict[str, str] = {}

    model_rotation = payload.get("model_rotation_deg")
    if isinstance(model_rotation, list) and len(model_rotation) >= 3:
        _append_viewer_param(query, "model_rx", model_rotation[0])
        _append_viewer_param(query, "model_ry", model_rotation[1])
        _append_viewer_param(query, "model_rz", model_rotation[2])

    model_translation = payload.get("model_translation")
    if isinstance(model_translation, list) and len(model_translation) >= 3:
        _append_viewer_param(query, "model_tx", model_translation[0])
        _append_viewer_param(query, "model_ty", model_translation[1])
        _append_viewer_param(query, "model_tz", model_translation[2])

    _append_viewer_param(query, "model_scale", payload.get("model_scale"))

    camera_rotation = payload.get("camera_rotation_deg")
    if isinstance(camera_rotation, list) and len(camera_rotation) >= 3:
        _append_viewer_param(query, "cam_rx", camera_rotation[0])
        _append_viewer_param(query, "cam_ry", camera_rotation[1])
        _append_viewer_param(query, "cam_rz", camera_rotation[2])

    _append_viewer_param(query, "cam_dist", payload.get("camera_distance"))
    return query


def _load_viewer_config(task_id: str) -> dict:
    metadata_path = task_model_dir(task_id) / "viewer.json"
    if not metadata_path.exists():
        return {}

    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}

    payload = payload if isinstance(payload, dict) else {}
    merged = dict(DEFAULT_VIEWER_CONFIG)
    merged.update(payload)
    return merged


def _storage_url_to_path(url: str | None) -> Path | None:
    if not url or not url.startswith("/storage/"):
        return None
    relative = url.removeprefix("/storage/").strip("/")
    if not relative:
        return None
    return STORAGE_ROOT / Path(relative)


def _round_vec3(values: list[float]) -> list[float]:
    return [round(float(values[index]), 4) for index in range(3)]


def _save_viewer_config(task_id: str, payload: ViewerConfigUpdate) -> dict:
    metadata_path = task_model_dir(task_id) / "viewer.json"
    current = _load_viewer_config(task_id) or dict(DEFAULT_VIEWER_CONFIG)

    if payload.model_rotation_deg is not None:
        current["model_rotation_deg"] = _round_vec3(payload.model_rotation_deg)
    if payload.model_translation is not None:
        current["model_translation"] = _round_vec3(payload.model_translation)
    if payload.model_scale is not None:
        current["model_scale"] = round(float(payload.model_scale), 6)
    if payload.camera_rotation_deg is not None:
        current["camera_rotation_deg"] = _round_vec3(payload.camera_rotation_deg)
    if payload.camera_distance is not None:
        current["camera_distance"] = round(float(payload.camera_distance), 6)

    atomic_write_json(metadata_path, current)
    return current


def _serialize_task(request: Request, task: dict) -> ReconstructionTaskResponse:
    model_rel_url = task.get("model_rel_path")
    viewer_rel_url = None
    explicit_viewer_url = task.get("viewer_url")
    if explicit_viewer_url:
        viewer_rel_url = explicit_viewer_url
    elif model_rel_url:
        query = {
            "task_id": task["task_id"],
            "model": quote(model_rel_url, safe='/:'),
            "viewer_build": VIEWER_BUILD_VERSION,
        }
        model_path = _storage_url_to_path(model_rel_url)
        if model_path is not None and model_path.exists():
            model_stat = model_path.stat()
            query["model_v"] = f"{model_stat.st_mtime_ns}_{model_stat.st_size}"
        query.update(_load_viewer_query(task["task_id"]))
        viewer_rel_url = "/viewer/index.html?" + urlencode(query)

    return ReconstructionTaskResponse(
        task_id=task["task_id"],
        title=task.get("title", ""),
        description=task.get("description", ""),
        price=task.get("price", ""),
        status=task.get("status", "uploaded"),
        progress=int(task.get("progress", 0)),
        status_message=task.get("status_message"),
        error_message=task.get("error_message"),
        created_at=task.get("created_at", ""),
        updated_at=task.get("updated_at", ""),
        video_url=_absolute_url(request, task.get("video_rel_path")),
        model_url=_absolute_url(request, model_rel_url),
        model_ply_url=_absolute_url(request, task.get("model_ply_rel_path")),
        model_sog_url=_absolute_url(request, task.get("model_sog_rel_path")),
        model_format=task.get("model_format"),
        viewer_url=_absolute_url(request, viewer_rel_url),
        log_url=_absolute_url(request, task.get("log_rel_path")),
        log_tail=list(task.get("log_tail") or []),
        train_step=task.get("train_step"),
        train_total_steps=task.get("train_total_steps"),
        train_eta=task.get("train_eta"),
        train_max_steps=task.get("train_max_steps"),
        quality_profile=task.get("quality_profile"),
        object_masking=bool(task.get("object_masking", False)),
        mask_prompt_frame_url=_absolute_url(request, task.get("mask_prompt_frame_rel_path")),
        mask_prompt_frame_name=task.get("mask_prompt_frame_name"),
        mask_prompt_frame_width=task.get("mask_prompt_frame_width"),
        mask_prompt_frame_height=task.get("mask_prompt_frame_height"),
        mask_prompts_url=_absolute_url(request, task.get("mask_prompts_rel_path")),
        mask_preview_url=_absolute_url(request, task.get("mask_preview_rel_path")),
        mask_preview_manifest_url=_absolute_url(request, task.get("mask_preview_manifest_rel_path")),
        mask_summary_url=_absolute_url(request, task.get("mask_summary_rel_path")),
        can_debug_masking=_can_debug_masking(task),
        pipeline_pid=task.get("pipeline_pid"),
        mock_mode=bool(task.get("mock_mode", False)),
        is_published=bool(task.get("is_published", False)),
        published_at=task.get("published_at"),
        viewer_rotation_done=bool(task.get("viewer_rotation_done", False)),
        viewer_translation_done=bool(task.get("viewer_translation_done", False)),
        viewer_initial_view_done=bool(task.get("viewer_initial_view_done", False)),
        viewer_animation_approved=bool(task.get("viewer_animation_approved", False)),
    )


def _remote_task_changes(task: dict, remote_task: dict) -> dict[str, object]:
    changes: dict[str, object] = {}
    remote_task_id = remote_task.get("task_id") or remote_task.get("id")
    if remote_task_id:
        changes["remote_task_id"] = str(remote_task_id)

    for field in (
        "status",
        "status_message",
        "error_message",
        "created_at",
        "updated_at",
        "model_format",
        "progress",
        "train_step",
        "train_total_steps",
        "train_eta",
        "train_max_steps",
        "quality_profile",
        "object_masking",
        "pipeline_pid",
        "mock_mode",
    ):
        if field in remote_task:
            changes[field] = remote_task.get(field)

    if "log_tail" in remote_task:
        changes["log_tail"] = list(remote_task.get("log_tail") or [])

    for remote_key, local_key in REMOTE_TASK_URL_FIELD_MAP.items():
        if remote_key in remote_task:
            changes[local_key] = remote_task.get(remote_key)

    viewer_config = remote_task.get("viewer_config")
    if isinstance(viewer_config, dict):
        try:
            _save_viewer_config(task["task_id"], ViewerConfigUpdate.model_validate(viewer_config))
        except Exception:
            pass

    return changes


def _refresh_task_from_remote(task: dict) -> dict:
    remote_task_id = task.get("remote_task_id") or task.get("task_id")
    if not remote_task_id:
        return task

    try:
        remote_task = get_trainer_service_client().get_task(str(remote_task_id))
    except TrainerServiceError:
        return task

    changes = _remote_task_changes(task, remote_task)
    if not changes:
        return task

    return update_task(task["task_id"], **changes)


def _start_pipeline_subprocess(
    task_id: str,
    input_video: Path,
    *,
    quality_profile: str,
    train_max_steps: int,
    object_masking: bool,
    mock_mode: bool,
    resume_after_mask: bool = False,
) -> int:
    command = [
        sys.executable,
        "-m",
        "trainer.pipeline",
        "--task-id",
        task_id,
        "--input-video",
        str(input_video),
        "--output-root",
        str(STORAGE_ROOT),
        "--quality-profile",
        quality_profile,
        "--train-max-steps",
        str(train_max_steps),
    ]

    if mock_mode:
        command.append("--mock")
    if object_masking:
        command.append("--object-masking")
    if resume_after_mask:
        command.append("--resume-after-mask")

    process = subprocess.Popen(
        command,
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
    )
    return int(process.pid)


def _kill_process_tree(pid: int) -> None:
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
        output = "\n".join(part for part in (result.stdout, result.stderr) if part)
        not_found_markers = ("not found", "not running", "找不到", "未找到", "不存在")
        if result.returncode != 0 and not any(marker in output.lower() for marker in not_found_markers):
            raise RuntimeError(output.strip() or f"taskkill failed for PID {pid}.")
        return

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def _find_windows_task_pids(task_id: str) -> list[int]:
    escaped_task_id = task_id.replace("'", "''")
    script = (
        "Get-CimInstance Win32_Process | "
        f"Where-Object {{ $_.CommandLine -like '*{escaped_task_id}*' -and $_.ProcessId -ne $PID }} | "
        "Select-Object -ExpandProperty ProcessId"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []

    pids: list[int] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pids.append(int(line))
        except ValueError:
            continue
    return pids


def _find_task_process_pids(task_id: str, stored_pid: int | None) -> list[int]:
    pids: list[int] = []
    if stored_pid is not None:
        pids.append(stored_pid)
    if os.name == "nt":
        pids.extend(_find_windows_task_pids(task_id))
    return sorted(set(pids), reverse=True)


def _terminate_task_processes(task_id: str, stored_pid: int | None) -> list[int]:
    pids = _find_task_process_pids(task_id, stored_pid)
    killed: list[int] = []
    errors: list[str] = []
    for pid in pids:
        try:
            _kill_process_tree(pid)
            killed.append(pid)
        except RuntimeError as exc:
            errors.append(f"PID {pid}: {exc}")

    if errors and not killed:
        raise RuntimeError("; ".join(errors))
    return killed


def _task_input_video_path(task: dict) -> Path:
    video_rel_path = task.get("video_rel_path")
    if not video_rel_path:
        raise HTTPException(status_code=400, detail="Task has no uploaded video.")

    if not video_rel_path.startswith("/storage/"):
        raise HTTPException(status_code=400, detail="Task video path is invalid.")

    input_video = STORAGE_ROOT / video_rel_path.removeprefix("/storage/")
    if not input_video.exists():
        raise HTTPException(status_code=404, detail="Uploaded video file not found.")
    return input_video


def _legacy_mask_preview_path(task_id: str) -> Path:
    return task_processed_dir(task_id) / "mask_preview_overlay.png"


def _mask_preview_frames_dir(task_id: str) -> Path:
    return task_processed_dir(task_id) / "mask_preview_frames"


def _mask_preview_manifest_path(task_id: str) -> Path:
    return task_processed_dir(task_id) / "mask_preview_manifest.json"


def _mask_preview_frame_path(task_id: str, frame_name: str) -> Path:
    return _mask_preview_frames_dir(task_id) / f"{Path(frame_name).stem}.jpg"


def _mask_prompts_path(task_id: str) -> Path:
    return task_processed_dir(task_id) / "mask_prompts.json"


def _processed_dataset_dir(task_id: str) -> Path:
    return task_processed_dir(task_id) / "dataset"


def _task_quality_profile(task: dict):
    return resolve_quality_profile(task.get("quality_profile"))


def _task_effective_quality_profile(task: dict):
    requested_profile = _task_quality_profile(task)
    restored_profile = restore_effective_quality_profile(task, requested_profile)
    if restored_profile is not None:
        return restored_profile

    video_metadata = task.get("video_metadata")
    if isinstance(video_metadata, dict):
        return adapt_quality_profile_to_video(video_metadata, requested_profile)

    return requested_profile


def _has_mask_debug_dataset(task_id: str) -> bool:
    dataset_dir = _processed_dataset_dir(task_id)
    return (
        dataset_dir.exists()
        and (dataset_dir / "transforms.json").exists()
        and (dataset_dir / "images").is_dir()
    )


def _can_debug_masking(task: dict) -> bool:
    status_value = task.get("status")
    if status_value in PIPELINE_ACTIVE_STATUSES or status_value in MASK_INTERACTION_STATUSES:
        return False
    quality_name = task.get("quality_profile")
    if not quality_name:
        return False
    try:
        quality_profile = _task_quality_profile(task)
    except ValueError:
        return False
    if quality_profile.name == "raw":
        return False
    return True


def _write_mask_prompts(task_id: str, task: dict, payload: MaskPromptRequest) -> Path:
    prompt_frame_name = task.get("mask_prompt_frame_name")
    if not prompt_frame_name:
        raise HTTPException(status_code=400, detail="Task has no mask prompt frame.")

    prompts_path = _mask_prompts_path(task_id)
    prompts_payload = {
        "task_id": task_id,
        "prompt_frame_name": prompt_frame_name,
        "prompt_frame_rel_path": task.get("mask_prompt_frame_rel_path"),
        "points": [
            point.model_dump() if hasattr(point, "model_dump") else point.dict()
            for point in payload.points
        ],
    }
    atomic_write_json(prompts_path, prompts_payload)
    return prompts_path


def _clear_mask_debug_artifacts(task_id: str) -> None:
    dataset_dir = _processed_dataset_dir(task_id)

    for path in (
        _mask_prompts_path(task_id),
        _legacy_mask_preview_path(task_id),
        _mask_preview_manifest_path(task_id),
        dataset_dir / "mask_summary.json",
    ):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            continue

    for directory in (
        _mask_preview_frames_dir(task_id),
        dataset_dir / "masks",
        dataset_dir / "masks_2",
        dataset_dir / "masks_4",
    ):
        try:
            shutil.rmtree(directory)
        except OSError:
            continue


@router.post("", response_model=ReconstructionTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_reconstruction(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    price: str = Form(""),
    video: UploadFile = File(...),
) -> ReconstructionTaskResponse:
    if not video.filename:
        raise HTTPException(status_code=400, detail="Missing video filename.")

    if video.content_type and not video.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a video.")

    upload_task_id = generate_task_id()
    upload_dir = task_upload_dir(upload_task_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(video.filename).suffix.lower() or ".mp4"
    source_path = upload_dir / f"source{suffix}"

    try:
        with source_path.open("wb") as target:
            shutil.copyfileobj(video.file, target)
        video_metadata = _validate_uploaded_video(source_path)
        remote_task = get_trainer_service_client().create_task(
            title=title.strip(),
            description=description.strip(),
            price=price.strip(),
            video_path=source_path,
            video_filename=video.filename,
            content_type=video.content_type,
        )
    except HTTPException:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise
    except TrainerServiceError as exc:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise

    try:
        remote_task_id = str(remote_task.get("task_id") or remote_task.get("id") or "").strip()
        if not remote_task_id:
            raise HTTPException(status_code=502, detail="Trainer service did not return a task id.")

        task = build_task_record(
            task_id=remote_task_id,
            title=title.strip(),
            description=description.strip(),
            price=price.strip(),
            source_filename=video.filename,
            video_path=source_path,
            video_metadata=video_metadata,
        )
        task.update(_remote_task_changes(task, remote_task))
        create_task(task)
        return _serialize_task(request, task)
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)


@router.post("/{task_id}/pipeline/start", response_model=ReconstructionTaskResponse)
async def start_reconstruction_pipeline(
    request: Request,
    task_id: str,
    payload: PipelineStartRequest,
) -> ReconstructionTaskResponse:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    if task.get("status") not in PIPELINE_STARTABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                "Pipeline can only be started from uploaded, failed, or cancelled status, "
                f"current status is {task.get('status')}."
            ),
        )

    try:
        quality_profile = resolve_quality_profile(payload.quality_profile).name
        train_max_steps = resolve_train_max_steps(payload.train_max_steps)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload.object_masking and quality_profile == "raw":
        raise HTTPException(
            status_code=400,
            detail="Object masking is disabled for the raw profile in the MVP because mask generation at full resolution is too expensive.",
        )

    mock_mode = AUTO_START_PIPELINE_MOCK if payload.mock_mode is None else payload.mock_mode
    try:
        remote_task = get_trainer_service_client().start_task(
            str(task.get("remote_task_id") or task_id),
            payload,
        )
        updates = _remote_task_changes(task, remote_task)
        updates.update(
            {
                "train_max_steps": train_max_steps,
                "quality_profile": quality_profile,
                "object_masking": payload.object_masking,
                "mock_mode": mock_mode,
            }
        )
        updated_task = update_task(task_id, **updates)
    except TrainerServiceError as exc:
        update_task(
            task_id,
            status="failed",
            progress=100,
            status_message="流水线启动失败",
            error_message=str(exc),
            pipeline_pid=None,
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return _serialize_task(request, updated_task)


@router.post("/{task_id}/pipeline/cancel", response_model=ReconstructionTaskResponse)
async def cancel_reconstruction_pipeline(request: Request, task_id: str) -> ReconstructionTaskResponse:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    current_status = task.get("status")
    if current_status == "cancelled":
        return _serialize_task(request, task)
    if current_status not in PIPELINE_CANCELABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Pipeline can only be cancelled while active, current status is {current_status}.",
        )

    try:
        remote_task = get_trainer_service_client().cancel_task(str(task.get("remote_task_id") or task_id))
        updated_task = update_task(task_id, **_remote_task_changes(task, remote_task))
    except TrainerServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return _serialize_task(request, updated_task)


@router.post("/{task_id}/mask-debug", response_model=ReconstructionTaskResponse)
async def start_mask_debug(request: Request, task_id: str) -> ReconstructionTaskResponse:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    current_status = task.get("status")
    if current_status in PIPELINE_ACTIVE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Mask debug can only start when the pipeline is idle, current status is {current_status}.",
        )
    if current_status in MASK_INTERACTION_STATUSES:
        return _serialize_task(request, task)
    if not _can_debug_masking(task):
        if (task.get("quality_profile") or "").strip().lower() == "raw":
            raise HTTPException(
                status_code=400,
                detail="Mask debug is disabled for the raw profile in the MVP.",
            )
        raise HTTPException(
            status_code=400,
            detail="This task does not have reusable COLMAP output. Wait until preprocessing finishes at least once.",
        )

    try:
        remote_task = get_trainer_service_client().start_mask_debug(str(task.get("remote_task_id") or task_id))
        updated_task = update_task(task_id, **_remote_task_changes(task, remote_task))
    except TrainerServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return _serialize_task(request, updated_task)


@router.post("/{task_id}/mask-prompts", response_model=ReconstructionTaskResponse)
@router.post("/{task_id}/mask-preview", response_model=ReconstructionTaskResponse)
async def preview_mask_prompts(
    request: Request,
    task_id: str,
    payload: MaskPromptRequest,
) -> ReconstructionTaskResponse:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    if task.get("status") not in MASK_INTERACTION_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                "Mask prompts can only be submitted while awaiting_mask_prompt or "
                f"awaiting_mask_confirmation, current status is {task.get('status')}."
            ),
        )
    if not task.get("object_masking"):
        raise HTTPException(status_code=400, detail="Object masking is not enabled for this task.")
    if not payload.points:
        raise HTTPException(status_code=400, detail="At least one mask prompt point is required.")
    if not any(point.label == 1 for point in payload.points):
        raise HTTPException(status_code=400, detail="At least one positive object point is required.")
    try:
        remote_task = get_trainer_service_client().preview_mask_prompts(str(task.get("remote_task_id") or task_id), payload)
        updated_task = update_task(task_id, **_remote_task_changes(task, remote_task))
    except TrainerServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return _serialize_task(request, updated_task)


@router.post("/{task_id}/mask-confirm", response_model=ReconstructionTaskResponse)
async def confirm_mask_preview(request: Request, task_id: str) -> ReconstructionTaskResponse:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    if task.get("status") != "awaiting_mask_confirmation":
        raise HTTPException(
            status_code=409,
            detail=(
                "Mask confirmation is only allowed while awaiting_mask_confirmation, "
                f"current status is {task.get('status')}."
            ),
        )
    if not task.get("object_masking"):
        raise HTTPException(status_code=400, detail="Object masking is not enabled for this task.")

    try:
        remote_task = get_trainer_service_client().confirm_mask_preview(str(task.get("remote_task_id") or task_id))
        updated_task = update_task(task_id, **_remote_task_changes(task, remote_task))
    except TrainerServiceError as exc:
        update_task(
            task_id,
            status="failed",
            progress=100,
            status_message="SAM 2 分割流水线启动失败",
            error_message=str(exc),
            pipeline_pid=None,
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return _serialize_task(request, updated_task)


@router.get("/{task_id}", response_model=ReconstructionTaskResponse)
async def get_reconstruction(request: Request, task_id: str) -> ReconstructionTaskResponse:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    task = _refresh_task_from_remote(task)

    return _serialize_task(request, task)


@router.post("/{task_id}/publish", response_model=ReconstructionTaskResponse)
async def publish_reconstruction(request: Request, task_id: str) -> ReconstructionTaskResponse:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    if task.get("status") != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Only ready tasks can be published, current status is {task.get('status')}.",
        )

    if not task.get("model_rel_path"):
        raise HTTPException(status_code=400, detail="Task has no generated model.")

    updated_task = update_task(
        task_id,
        is_published=True,
        published_at=task.get("published_at") or now_iso(),
        status_message="商品已发布，可在首页和详情页中查看 3D 展示",
        error_message=None,
    )
    return _serialize_task(request, updated_task)


@router.put("/{task_id}/publish-flow", response_model=ReconstructionTaskResponse)
async def update_publish_flow_state(
    request: Request,
    task_id: str,
    payload: PublishFlowStateUpdate,
) -> ReconstructionTaskResponse:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    changes = {}
    if payload.viewer_rotation_done is not None:
        changes["viewer_rotation_done"] = payload.viewer_rotation_done
    if payload.viewer_translation_done is not None:
        changes["viewer_translation_done"] = payload.viewer_translation_done
    if payload.viewer_initial_view_done is not None:
        changes["viewer_initial_view_done"] = payload.viewer_initial_view_done
    if payload.viewer_animation_approved is not None:
        changes["viewer_animation_approved"] = payload.viewer_animation_approved

    if not changes:
        return _serialize_task(request, task)

    updated_task = update_task(task_id, **changes)
    return _serialize_task(request, updated_task)


@router.put("/{task_id}/viewer", response_model=ViewerConfigResponse)
async def update_viewer_config(
    request: Request,
    task_id: str,
    payload: ViewerConfigUpdate,
) -> ViewerConfigResponse:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    if not task.get("model_rel_path"):
        raise HTTPException(status_code=400, detail="Task has no generated model.")

    previous_viewer_config = _load_viewer_config(task_id)
    viewer_config = _save_viewer_config(task_id, payload)
    updated_task = task

    try:
        remote_response = get_trainer_service_client().update_viewer_config(str(task.get("remote_task_id") or task_id), payload)
        remote_task = remote_response.get("task") if isinstance(remote_response, dict) else None
        if isinstance(remote_task, dict):
            updated_task = update_task(task_id, **_remote_task_changes(task, remote_task))
        else:
            updated_task = _refresh_task_from_remote(task)
    except TrainerServiceError as exc:
        if previous_viewer_config:
            atomic_write_json(task_model_dir(task_id) / "viewer.json", previous_viewer_config)
        else:
            try:
                (task_model_dir(task_id) / "viewer.json").unlink(missing_ok=True)
            except OSError:
                pass
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return ViewerConfigResponse(
        task_id=task_id,
        viewer_config=viewer_config,
        task=_serialize_task(request, updated_task),
    )


@router.get("", response_model=list[ReconstructionTaskResponse])
async def list_reconstructions(
    request: Request,
    status: str | None = None,
) -> list[ReconstructionTaskResponse]:
    statuses = None
    if status:
        parsed = {item.strip() for item in status.split(",") if item.strip()}
        if parsed:
            statuses = parsed

    tasks = [_refresh_task_from_remote(task) for task in list_tasks()]
    if statuses is not None:
        tasks = [task for task in tasks if task.get("status") in statuses]

    return [_serialize_task(request, task) for task in tasks]


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reconstruction(task_id: str) -> Response:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    if task.get("status") in PIPELINE_CANCELABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Delete is disabled while the pipeline is active or waiting for mask interaction.",
        )

    try:
        delete_task(task_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Task not found.") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete task: {exc}") from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
