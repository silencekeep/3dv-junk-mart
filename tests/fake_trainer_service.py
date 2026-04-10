from __future__ import annotations

import copy
import uuid
from pathlib import Path
from typing import Any

from backend.app.services.trainer_service_client import TrainerServiceError
from shared.task_store import now_iso, task_model_dir


def _payload_as_dict(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if hasattr(payload, "model_dump"):
        value = payload.model_dump(exclude_none=True)
        return value if isinstance(value, dict) else {}
    if hasattr(payload, "dict"):
        value = payload.dict(exclude_none=True)
        return value if isinstance(value, dict) else {}
    if isinstance(payload, dict):
        return dict(payload)
    return {}


class FakeTrainerServiceClient:
    def __init__(self, *, base_url: str = "http://trainer.local", public_base_url: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.public_base_url = (public_base_url or self.base_url).rstrip("/")
        self._tasks: dict[str, dict[str, Any]] = {}

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "base_url": self.base_url,
            "public_base_url": self.public_base_url,
        }

    def _remote_url(self, path: str | None) -> str | None:
        if not path:
            return None
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if path.startswith("/"):
            return f"{self.public_base_url}{path}"
        return f"{self.public_base_url}/{path}"

    def _load_viewer_config(self, task_id: str) -> dict[str, Any]:
        metadata_path = task_model_dir(task_id) / "viewer.json"
        if not metadata_path.exists():
            return {}

        try:
            payload = metadata_path.read_text(encoding="utf-8")
        except OSError:
            return {}

        try:
            loaded = __import__("json").loads(payload)
        except ValueError:
            return {}

        return loaded if isinstance(loaded, dict) else {}

    def _task_response(self, task: dict[str, Any]) -> dict[str, Any]:
        response = copy.deepcopy(task)
        response["viewer_config"] = self._load_viewer_config(str(response["task_id"])) or copy.deepcopy(
            response.get("viewer_config") or {}
        )
        return response

    def _get_task(self, task_id: str) -> dict[str, Any]:
        task = self._tasks.get(task_id)
        if task is None:
            raise TrainerServiceError(f"Task '{task_id}' not found.", status_code=404)
        return task

    def _store_task(self, task: dict[str, Any]) -> dict[str, Any]:
        task_id = str(task["task_id"])
        task["updated_at"] = now_iso()
        self._tasks[task_id] = copy.deepcopy(task)
        return self._task_response(self._tasks[task_id])

    def seed_task(self, task: dict[str, Any]) -> dict[str, Any]:
        task_id = str(task["task_id"])
        now = task.get("created_at") or now_iso()
        seeded = {
            "task_id": task_id,
            "title": task.get("title") or "",
            "description": task.get("description") or "",
            "price": task.get("price") or "",
            "status": task.get("status") or "uploaded",
            "progress": int(task.get("progress") or 0),
            "status_message": task.get("status_message") or "任务已创建，等待进入流水线",
            "error_message": task.get("error_message"),
            "created_at": now,
            "updated_at": task.get("updated_at") or now,
            "video_url": self._remote_url(task.get("video_rel_path")),
            "model_url": self._remote_url(task.get("model_rel_path")),
            "model_ply_url": self._remote_url(task.get("model_ply_rel_path")),
            "model_sog_url": self._remote_url(task.get("model_sog_rel_path")),
            "model_format": task.get("model_format"),
            "viewer_url": self._remote_url(task.get("viewer_url")),
            "log_url": self._remote_url(task.get("log_rel_path")),
            "log_tail": list(task.get("log_tail") or []),
            "train_step": task.get("train_step"),
            "train_total_steps": task.get("train_total_steps"),
            "train_eta": task.get("train_eta"),
            "train_max_steps": task.get("train_max_steps"),
            "quality_profile": task.get("quality_profile"),
            "object_masking": bool(task.get("object_masking", False)),
            "mask_prompt_frame_url": self._remote_url(task.get("mask_prompt_frame_rel_path")),
            "mask_prompt_frame_name": task.get("mask_prompt_frame_name"),
            "mask_prompt_frame_width": task.get("mask_prompt_frame_width"),
            "mask_prompt_frame_height": task.get("mask_prompt_frame_height"),
            "mask_prompts_url": self._remote_url(task.get("mask_prompts_rel_path")),
            "mask_preview_url": self._remote_url(task.get("mask_preview_rel_path")),
            "mask_preview_manifest_url": self._remote_url(task.get("mask_preview_manifest_rel_path")),
            "mask_summary_url": self._remote_url(task.get("mask_summary_rel_path")),
            "pipeline_pid": task.get("pipeline_pid"),
            "mock_mode": bool(task.get("mock_mode", False)),
            "is_published": bool(task.get("is_published", False)),
            "published_at": task.get("published_at"),
            "viewer_config": copy.deepcopy(task.get("viewer_config") or {}),
            "remote_task_id": task.get("remote_task_id") or task_id,
        }
        self._tasks[task_id] = copy.deepcopy(seeded)
        return self._task_response(self._tasks[task_id])

    def list_tasks(self, *, status: str | None = None) -> list[dict[str, Any]]:
        tasks = [self._task_response(task) for task in self._tasks.values()]
        if status:
            allowed = {item.strip() for item in status.split(",") if item.strip()}
            tasks = [task for task in tasks if task.get("status") in allowed]
        tasks.sort(key=lambda task: task.get("created_at", ""), reverse=True)
        return tasks

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._task_response(self._get_task(task_id))

    def create_task(
        self,
        *,
        title: str,
        description: str,
        price: str,
        video_path: Path,
        video_filename: str,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        file_name = Path(video_filename).name or "source.mp4"
        now = now_iso()
        task = {
            "task_id": task_id,
            "title": title,
            "description": description,
            "price": price,
            "status": "uploaded",
            "progress": 0,
            "status_message": "任务已创建，等待进入流水线",
            "error_message": None,
            "created_at": now,
            "updated_at": now,
            "video_url": self._remote_url(f"/storage/uploads/{task_id}/{file_name}"),
            "model_url": None,
            "model_ply_url": None,
            "model_sog_url": None,
            "model_format": None,
            "viewer_url": None,
            "log_url": None,
            "log_tail": [],
            "train_step": None,
            "train_total_steps": None,
            "train_eta": None,
            "train_max_steps": None,
            "quality_profile": None,
            "object_masking": False,
            "mask_prompt_frame_url": None,
            "mask_prompt_frame_name": None,
            "mask_prompt_frame_width": None,
            "mask_prompt_frame_height": None,
            "mask_prompts_url": None,
            "mask_preview_url": None,
            "mask_preview_manifest_url": None,
            "mask_summary_url": None,
            "pipeline_pid": None,
            "mock_mode": False,
            "is_published": False,
            "published_at": None,
            "viewer_config": {},
            "remote_task_id": task_id,
            "source_filename": file_name,
        }
        return self._store_task(task)

    def start_task(self, task_id: str, payload: Any) -> dict[str, Any]:
        task = copy.deepcopy(self._get_task(task_id))
        payload_dict = _payload_as_dict(payload)
        if task.get("status") not in {"uploaded", "failed", "cancelled"}:
            raise TrainerServiceError(
                f"Pipeline can only be started from uploaded, failed, or cancelled status, current status is {task.get('status')}.",
                status_code=409,
            )

        task.update(
            {
                "status": "queued",
                "progress": 0,
                "status_message": "训练配置已确认，正在启动流水线",
                "error_message": None,
                "train_max_steps": payload_dict.get("train_max_steps", task.get("train_max_steps")),
                "quality_profile": payload_dict.get("quality_profile", task.get("quality_profile") or "balanced"),
                "object_masking": bool(payload_dict.get("object_masking", False)),
                "pipeline_pid": 4321,
                "mock_mode": bool(payload_dict.get("mock_mode")) if payload_dict.get("mock_mode") is not None else bool(task.get("mock_mode", False)),
            }
        )
        return self._store_task(task)

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        task = copy.deepcopy(self._get_task(task_id))
        current_status = task.get("status")
        if current_status == "cancelled":
            return self._task_response(task)
        if current_status not in {"queued", "preprocessing", "awaiting_mask_prompt", "awaiting_mask_confirmation", "masking", "training", "exporting"}:
            raise TrainerServiceError(
                f"Pipeline can only be cancelled while active, current status is {current_status}.",
                status_code=409,
            )

        task.update(
            {
                "status": "cancelled",
                "status_message": "流水线已终止",
                "error_message": None,
                "pipeline_pid": None,
                "train_eta": None,
            }
        )
        return self._store_task(task)

    def start_mask_debug(self, task_id: str) -> dict[str, Any]:
        task = copy.deepcopy(self._get_task(task_id))
        current_status = task.get("status")
        if current_status in {"queued", "preprocessing", "masking", "training", "exporting"}:
            raise TrainerServiceError(
                f"Mask debug can only start when the pipeline is idle, current status is {current_status}.",
                status_code=409,
            )

        frame_name = task.get("mask_prompt_frame_name") or "frame_001.jpg"
        task.update(
            {
                "status": "awaiting_mask_prompt",
                "progress": 54,
                "status_message": "等待补充 mask 提示点",
                "error_message": None,
                "object_masking": True,
                "pipeline_pid": None,
                "mask_prompt_frame_name": frame_name,
                "mask_prompt_frame_width": task.get("mask_prompt_frame_width") or 1920,
                "mask_prompt_frame_height": task.get("mask_prompt_frame_height") or 1080,
                "mask_prompt_frame_url": self._remote_url(task.get("mask_prompt_frame_rel_path") or f"/storage/processed/{task_id}/{Path(frame_name).name}"),
                "mask_prompts_url": None,
                "mask_preview_url": None,
                "mask_preview_manifest_url": None,
                "mask_summary_url": None,
            }
        )
        return self._store_task(task)

    def preview_mask_prompts(self, task_id: str, payload: Any) -> dict[str, Any]:
        task = copy.deepcopy(self._get_task(task_id))
        payload_dict = _payload_as_dict(payload)
        points = list(payload_dict.get("points") or [])
        if not points:
            raise TrainerServiceError("At least one mask prompt point is required.", status_code=400)
        if not any(isinstance(point, dict) and point.get("label") == 1 for point in points):
            raise TrainerServiceError("At least one positive object point is required.", status_code=400)

        frame_name = task.get("mask_prompt_frame_name") or "frame_001.jpg"
        frame_stem = Path(frame_name).stem
        task.update(
            {
                "status": "awaiting_mask_confirmation",
                "progress": int(task.get("progress") or 54),
                "status_message": "已生成全帧分割预览，请拖动进度条检查任意时刻的分割效果；如果不理想，可以补点后重新预览",
                "error_message": None,
                "mask_prompts_url": self._remote_url(f"/storage/processed/{task_id}/mask_prompts.json"),
                "mask_preview_url": self._remote_url(f"/storage/processed/{task_id}/mask_preview_frames/{frame_stem}.jpg"),
                "mask_preview_manifest_url": self._remote_url(f"/storage/processed/{task_id}/mask_preview_manifest.json"),
                "mask_summary_url": self._remote_url(f"/storage/processed/{task_id}/dataset/mask_summary.json"),
                "pipeline_pid": None,
            }
        )
        return self._store_task(task)

    def confirm_mask_preview(self, task_id: str) -> dict[str, Any]:
        task = copy.deepcopy(self._get_task(task_id))
        if task.get("status") != "awaiting_mask_confirmation":
            raise TrainerServiceError(
                f"Mask confirmation is only allowed while awaiting_mask_confirmation, current status is {task.get('status')}.",
                status_code=409,
            )

        task.update(
            {
                "status": "queued",
                "status_message": "Mask 预览已确认，正在启动 SAM 2 分割流水线",
                "error_message": None,
                "pipeline_pid": 9876,
            }
        )
        return self._store_task(task)

    def update_viewer_config(self, task_id: str, payload: Any) -> dict[str, Any]:
        task = copy.deepcopy(self._get_task(task_id))
        viewer_config = _payload_as_dict(payload)
        task["viewer_config"] = viewer_config
        stored = self._store_task(task)
        return {
            "task_id": task_id,
            "viewer_config": copy.deepcopy(viewer_config),
            "task": stored,
        }


__all__ = ["FakeTrainerServiceClient"]