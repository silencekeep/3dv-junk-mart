from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from backend.app.schemas import ApiErrorDetail, ApiEnvelope, ApiMeta, PageMeta


HTTP_TO_APP_CODE = {
    status.HTTP_401_UNAUTHORIZED: 1001,
    status.HTTP_403_FORBIDDEN: 1002,
    status.HTTP_404_NOT_FOUND: 3004,
    status.HTTP_409_CONFLICT: 3002,
    status.HTTP_422_UNPROCESSABLE_ENTITY: 2001,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_request_id(request: Request | None = None) -> str:
    if request is not None:
        request_id = getattr(request.state, 'request_id', None)
        if request_id:
            return str(request_id)
    return uuid4().hex


def build_meta(
    request: Request | None = None,
    *,
    cache_ttl_seconds: int | None = None,
    page: PageMeta | dict[str, Any] | None = None,
) -> ApiMeta:
    return ApiMeta(
        request_id=get_request_id(request),
        cache_ttl_seconds=cache_ttl_seconds,
        page=PageMeta.model_validate(page) if isinstance(page, dict) else page,
    )


def ok(
    request: Request | None,
    data: Any,
    *,
    cache_ttl_seconds: int | None = None,
    page: PageMeta | dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = ApiEnvelope(
        code=0,
        message='ok',
        data=data,
        meta=build_meta(request, cache_ttl_seconds=cache_ttl_seconds, page=page),
    )
    return payload.model_dump(mode='json', exclude_none=True)


def error(
    request: Request | None,
    *,
    message: str,
    status_code: int,
    details: list[ApiErrorDetail | dict[str, Any]] | None = None,
) -> JSONResponse:
    payload = ApiEnvelope(
        code=HTTP_TO_APP_CODE.get(status_code, 5001 if status_code >= 500 else 3001),
        message=message,
        data=None,
        meta=build_meta(request),
        errors=[ApiErrorDetail.model_validate(item) for item in details] if details else None,
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode='json', exclude_none=True))


def validation_error_details(exc: RequestValidationError) -> list[ApiErrorDetail]:
    details: list[ApiErrorDetail] = []
    for item in exc.errors():
        location = item.get('loc', ())
        field = '.'.join(str(part) for part in location if part not in {'body', 'query', 'path'})
        details.append(
            ApiErrorDetail(
                field=field or None,
                reason=item.get('msg', 'validation failed'),
            )
        )
    return details


def http_exception_response(request: Request | None, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, list):
        details = [item if isinstance(item, dict) else {'reason': str(item)} for item in detail]
        message = 'request failed'
    elif isinstance(detail, dict):
        details = [detail]
        message = str(detail.get('detail') or detail.get('reason') or 'request failed')
    else:
        details = None
        message = str(detail) if detail else 'request failed'
    return error(request, message=message, status_code=exc.status_code, details=details)
