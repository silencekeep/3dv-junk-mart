from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.http import error, http_exception_response, validation_error_details
from backend.app.routes.marketplace import router as marketplace_router
from backend.app.routes.reconstructions import router as reconstructions_router
from backend.app.schemas import HealthResponse
from backend.app.services.marketplace_store import get_store
from shared.task_store import ensure_layout
from shared.config import STORAGE_ROOT, VIEWER_ROOT

STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
VIEWER_ROOT.mkdir(parents=True, exist_ok=True)
(STORAGE_ROOT / "uploads").mkdir(parents=True, exist_ok=True)


class CacheControlledStaticFiles(StaticFiles):
    def __init__(self, *args, cache_control_by_extension: dict[str, str] | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cache_control_by_extension = cache_control_by_extension or {}

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        cache_control = self.cache_control_by_extension.get(Path(path).suffix.lower())
        if cache_control and response.status_code < 400:
            response.headers["Cache-Control"] = cache_control
        return response


app = FastAPI(
    title="3dv-junk-mart Marketplace Backend",
    version="0.1.0",
    summary="SQLite-backed marketplace backend with remote 3DGS service integration.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(marketplace_router)
app.include_router(reconstructions_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return http_exception_response(request, exc)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    return error(
        request,
        message="请求参数校验失败。",
        status_code=422,
        details=validation_error_details(exc),
    )


@app.on_event("startup")
def startup() -> None:
    ensure_layout()
    get_store()

app.mount(
    "/storage",
    CacheControlledStaticFiles(
        directory=STORAGE_ROOT,
        cache_control_by_extension={
            ".ply": "public, max-age=604800",
            ".sog": "public, max-age=604800",
        },
    ),
    name="storage",
)
app.mount(
    "/viewer",
    CacheControlledStaticFiles(
        directory=VIEWER_ROOT,
        html=True,
        cache_control_by_extension={
            ".css": "public, max-age=31536000, immutable",
            ".html": "no-cache",
            ".js": "public, max-age=31536000, immutable",
        },
    ),
    name="viewer",
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse.model_validate(get_store().health_snapshot())
