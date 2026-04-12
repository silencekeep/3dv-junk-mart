from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from shared.config import (
    GS_SERVICE_BASE_URL,
    GS_SERVICE_PUBLIC_BASE_URL,
    GS_SERVICE_TIMEOUT_SECONDS,
    trainer_service_headers,
)


class TrainerServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502, payload: Any | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def _payload_as_dict(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)
    if hasattr(value, "dict"):
        return value.dict(exclude_none=True)
    return value


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def _extract_error_detail(response: httpx.Response) -> str:
    payload = _safe_json(response)
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        if detail is not None:
            return json.dumps(detail, ensure_ascii=False)
        message = payload.get("message")
        if isinstance(message, str):
            return message
        return json.dumps(payload, ensure_ascii=False)
    if isinstance(payload, list):
        return json.dumps(payload, ensure_ascii=False)
    if isinstance(payload, str):
        return payload

    text = response.text.strip()
    if text:
        return text
    return response.reason_phrase or f"HTTP {response.status_code}"


class TrainerServiceClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        public_base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        resolved_base_url = (base_url or GS_SERVICE_BASE_URL).rstrip("/")
        resolved_public_base_url = (public_base_url or GS_SERVICE_PUBLIC_BASE_URL or resolved_base_url).rstrip("/")
        self.base_url = resolved_base_url
        self.public_base_url = resolved_public_base_url
        self.timeout_seconds = timeout_seconds or GS_SERVICE_TIMEOUT_SECONDS
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=trainer_service_headers(),
            timeout=self.timeout_seconds,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TrainerServiceClient":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_payload: Any | None = None,
        data: Any | None = None,
        params: dict[str, Any] | None = None,
        files: Any | None = None,
    ) -> Any:
        try:
            response = self._client.request(
                method,
                path,
                json=json_payload,
                data=data,
                params=params,
                files=files,
            )
        except httpx.RequestError as exc:
            raise TrainerServiceError(
                f"Failed to reach trainer service at {self.base_url}: {exc}",
                status_code=502,
            ) from exc

        if response.is_success:
            if response.status_code == 204 or not response.content:
                return {}

            payload = _safe_json(response)
            if payload is not None:
                return payload
            return response.text

        raise TrainerServiceError(
            _extract_error_detail(response),
            status_code=response.status_code,
            payload=_safe_json(response),
        )

    def health(self) -> Any:
        return self._request("GET", "/health")

    def list_tasks(self, *, status: str | None = None) -> list[dict[str, Any]]:
        params = {"status": status} if status else None
        payload = self._request("GET", "/tasks", params=params)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            items = payload.get("items")
            if isinstance(items, list):
                return items
        raise TrainerServiceError("Unexpected task list response.", payload=payload)

    def get_task(self, task_id: str) -> dict[str, Any]:
        payload = self._request("GET", f"/tasks/{task_id}")
        if isinstance(payload, dict):
            return payload
        raise TrainerServiceError("Unexpected task detail response.", payload=payload)

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
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        form_data = {
            "title": title,
            "description": description,
            "price": price,
        }
        mime_type = content_type or "video/mp4"
        with video_path.open("rb") as handle:
            payload = self._request(
                "POST",
                "/tasks",
                data=form_data,
                files={"video": (video_filename, handle, mime_type)},
            )

        if isinstance(payload, dict):
            return payload
        raise TrainerServiceError("Unexpected task creation response.", payload=payload)

    def start_task(self, task_id: str, payload: Any) -> dict[str, Any]:
        response = self._request("POST", f"/tasks/{task_id}/start", json_payload=_payload_as_dict(payload))
        if isinstance(response, dict):
            return response
        raise TrainerServiceError("Unexpected task start response.", payload=response)

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        response = self._request("POST", f"/tasks/{task_id}/cancel")
        if isinstance(response, dict):
            return response
        raise TrainerServiceError("Unexpected task cancel response.", payload=response)

    def start_mask_debug(self, task_id: str) -> dict[str, Any]:
        response = self._request("POST", f"/tasks/{task_id}/mask-debug")
        if isinstance(response, dict):
            return response
        raise TrainerServiceError("Unexpected mask debug response.", payload=response)

    def preview_mask_prompts(self, task_id: str, payload: Any) -> dict[str, Any]:
        response = self._request("POST", f"/tasks/{task_id}/mask-preview", json_payload=_payload_as_dict(payload))
        if isinstance(response, dict):
            return response
        raise TrainerServiceError("Unexpected mask preview response.", payload=response)

    def confirm_mask_preview(self, task_id: str) -> dict[str, Any]:
        response = self._request("POST", f"/tasks/{task_id}/mask-confirm")
        if isinstance(response, dict):
            return response
        raise TrainerServiceError("Unexpected mask confirm response.", payload=response)

    def update_viewer_config(self, task_id: str, payload: Any) -> dict[str, Any]:
        response = self._request("PUT", f"/tasks/{task_id}/viewer", json_payload=_payload_as_dict(payload))
        if isinstance(response, dict):
            return response
        raise TrainerServiceError("Unexpected viewer config response.", payload=response)


@lru_cache(maxsize=1)
def get_trainer_service_client() -> TrainerServiceClient:
    return TrainerServiceClient()


__all__ = ["TrainerServiceClient", "TrainerServiceError", "get_trainer_service_client"]