from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
from datetime import datetime
import importlib.util
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.task_store import (
    STORAGE_ROOT,
    atomic_write_json,
    ensure_layout,
    get_task,
    path_to_storage_url,
    task_model_dir,
    task_processed_dir,
    update_task,
)

DEFAULT_TRAIN_MAX_STEPS = 7000
TRAIN_MAX_STEP_OPTIONS = (7000, 30000)
LOG_TAIL_LIMIT = 30
ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
DEFAULT_QUALITY_PROFILE = "balanced"
DEFAULT_SOG_ITERATIONS = 10


@dataclass(frozen=True)
class QualityProfile:
    name: str
    video_max_long_edge: int | None
    process_num_downscales: int
    train_downscale_factor: int | None
    model_num_downscales: int
    description: str


MIN_TRAIN_LONG_EDGE_BY_PROFILE = {
    "fast": 720,
    "balanced": 960,
    "quality": 1280,
    "raw": 0,
}


QUALITY_PROFILES = {
    "fast": QualityProfile(
        name="fast",
        video_max_long_edge=1600,
        process_num_downscales=2,
        train_downscale_factor=2,
        model_num_downscales=2,
        description="Lower resolution profile for quick local checks.",
    ),
    "balanced": QualityProfile(
        name="balanced",
        video_max_long_edge=2560,
        process_num_downscales=2,
        train_downscale_factor=2,
        model_num_downscales=2,
        description="Default MVP profile, targeting better detail while keeping training cost bounded.",
    ),
    "quality": QualityProfile(
        name="quality",
        video_max_long_edge=3200,
        process_num_downscales=2,
        train_downscale_factor=2,
        model_num_downscales=1,
        description="Higher-detail profile for good captures and enough VRAM.",
    ),
    "raw": QualityProfile(
        name="raw",
        video_max_long_edge=None,
        process_num_downscales=2,
        train_downscale_factor=1,
        model_num_downscales=1,
        description="Experimental profile that keeps original resolution and is likely to be expensive.",
    ),
}


def resolve_quality_profile(name: str | None) -> QualityProfile:
    normalized = (name or DEFAULT_QUALITY_PROFILE).strip().lower()
    profile = QUALITY_PROFILES.get(normalized)
    if profile is None:
        known = ", ".join(sorted(QUALITY_PROFILES))
        raise ValueError(f"Unknown quality profile '{name}'. Expected one of: {known}.")
    return profile


def default_quality_profile_name() -> str:
    normalized = os.getenv("TRAINING_QUALITY_PROFILE", DEFAULT_QUALITY_PROFILE).strip().lower()
    if normalized in QUALITY_PROFILES:
        return normalized
    return DEFAULT_QUALITY_PROFILE


def primary_video_stream(metadata: dict[str, Any]) -> dict[str, Any]:
    return next((stream for stream in metadata.get("streams", []) if stream.get("codec_type") == "video"), {})


def video_dimensions(metadata: dict[str, Any]) -> tuple[int, int]:
    stream = primary_video_stream(metadata)
    width = int(stream.get("width", 0) or 0)
    height = int(stream.get("height", 0) or 0)
    return width, height


def effective_long_edge_for_profile(metadata: dict[str, Any], quality_profile: QualityProfile) -> int:
    width, height = video_dimensions(metadata)
    long_edge = max(width, height)
    if quality_profile.video_max_long_edge is None:
        return long_edge
    return min(long_edge, quality_profile.video_max_long_edge)


def adapt_quality_profile_to_video(metadata: dict[str, Any], quality_profile: QualityProfile) -> QualityProfile:
    base_train_factor = quality_profile.train_downscale_factor or 1
    effective_train_factor = base_train_factor
    effective_long_edge = effective_long_edge_for_profile(metadata, quality_profile)
    min_train_long_edge = MIN_TRAIN_LONG_EDGE_BY_PROFILE.get(quality_profile.name, 0)

    while effective_train_factor > 1 and (effective_long_edge / effective_train_factor) < min_train_long_edge:
        effective_train_factor //= 2

    effective_model_num_downscales = quality_profile.model_num_downscales
    if effective_train_factor < base_train_factor:
        effective_model_num_downscales = min(effective_model_num_downscales, 1)

    return replace(
        quality_profile,
        train_downscale_factor=effective_train_factor,
        model_num_downscales=effective_model_num_downscales,
    )


def serialize_quality_profile(profile: QualityProfile) -> dict[str, Any]:
    payload = asdict(profile)
    payload["effective_train_long_edge_min"] = MIN_TRAIN_LONG_EDGE_BY_PROFILE.get(profile.name, 0)
    return payload


def infer_task_train_downscale_factor(task: dict[str, Any]) -> int | None:
    raw_value = task.get("effective_train_downscale_factor")
    if raw_value is not None:
        try:
            return max(int(raw_value), 1)
        except (TypeError, ValueError):
            return None

    prompt_path = str(task.get("mask_prompt_frame_rel_path") or "").replace("\\", "/")
    matched = re.search(r"/images_(\d+)/", prompt_path)
    if matched:
        try:
            return max(int(matched.group(1)), 1)
        except ValueError:
            return None
    if "/images/" in prompt_path:
        return 1
    return None


def restore_effective_quality_profile(task: dict[str, Any], quality_profile: QualityProfile) -> QualityProfile | None:
    train_factor = infer_task_train_downscale_factor(task)
    if train_factor is None:
        return None

    raw_model_num_downscales = task.get("effective_model_num_downscales")
    if raw_model_num_downscales is None:
        model_num_downscales = min(quality_profile.model_num_downscales, 1) if train_factor < (quality_profile.train_downscale_factor or 1) else quality_profile.model_num_downscales
    else:
        try:
            model_num_downscales = max(int(raw_model_num_downscales), 0)
        except (TypeError, ValueError):
            model_num_downscales = quality_profile.model_num_downscales

    return replace(
        quality_profile,
        train_downscale_factor=train_factor,
        model_num_downscales=model_num_downscales,
    )


def log_effective_quality_profile(
    reporter: "PipelineReporter",
    *,
    requested_profile: QualityProfile,
    effective_profile: QualityProfile,
    metadata: dict[str, Any] | None,
    restored_from_task: bool = False,
) -> None:
    source_width, source_height = video_dimensions(metadata or {})
    effective_long_edge = effective_long_edge_for_profile(metadata or {}, requested_profile)
    reporter.log_event(
        "quality-profile",
        "Effective quality profile resolved",
        requested_quality_profile=requested_profile.name,
        requested_quality_profile_config=serialize_quality_profile(requested_profile),
        effective_quality_profile_config=serialize_quality_profile(effective_profile),
        source_width=source_width or None,
        source_height=source_height or None,
        effective_input_long_edge=effective_long_edge or None,
        restored_from_task=restored_from_task,
        force=restored_from_task or effective_profile != requested_profile,
    )


def resolve_train_max_steps(value: int | str | None) -> int:
    if value is None:
        return DEFAULT_TRAIN_MAX_STEPS

    try:
        steps = int(value)
    except (TypeError, ValueError):
        known = ", ".join(str(option) for option in TRAIN_MAX_STEP_OPTIONS)
        raise ValueError(f"Unknown train max steps '{value}'. Expected one of: {known}.")

    if steps not in TRAIN_MAX_STEP_OPTIONS:
        known = ", ".join(str(option) for option in TRAIN_MAX_STEP_OPTIONS)
        raise ValueError(f"Unknown train max steps '{value}'. Expected one of: {known}.")
    return steps


def default_train_max_steps() -> int:
    return resolve_train_max_steps(os.getenv("TRAINING_MAX_STEPS", str(DEFAULT_TRAIN_MAX_STEPS)))


def sog_export_enabled() -> bool:
    return os.getenv("SOG_EXPORT_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}


def sog_export_iterations() -> int:
    raw_value = os.getenv("SOG_EXPORT_ITERATIONS", str(DEFAULT_SOG_ITERATIONS)).strip()
    try:
        iterations = int(raw_value)
    except ValueError:
        return DEFAULT_SOG_ITERATIONS
    return max(iterations, 1)


def sog_export_gpu() -> str | None:
    value = os.getenv("SOG_EXPORT_GPU", "").strip()
    return value or None


def command_to_string(command: list[str] | str) -> str:
    if isinstance(command, str):
        return command
    return subprocess.list2cmdline(command)


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes, remainder = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}m {remainder:.1f}s"
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours)}h {int(minutes)}m {remainder:.1f}s"


def now_local_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the 3DGS reconstruction pipeline for one task.")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--input-video", required=True)
    parser.add_argument("--output-root", default=str(STORAGE_ROOT))
    parser.add_argument("--mock", action="store_true", help="Skip nerfstudio and write a small development PLY.")
    parser.add_argument(
        "--quality-profile",
        choices=sorted(QUALITY_PROFILES),
        default=default_quality_profile_name(),
        help="Training quality profile controlling video scale and nerfstudio downscale settings.",
    )
    parser.add_argument(
        "--train-max-steps",
        type=int,
        choices=TRAIN_MAX_STEP_OPTIONS,
        default=default_train_max_steps(),
        help="Maximum splatfacto training iterations.",
    )
    parser.add_argument(
        "--object-masking",
        action="store_true",
        help="Enable SAM 2 object masking after COLMAP and before splatfacto training.",
    )
    parser.add_argument(
        "--resume-after-mask",
        action="store_true",
        help="Resume an object-masking task after the user submitted mask prompts.",
    )
    return parser.parse_args()


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text).strip()


def tail_text(text: str, limit: int = 6000) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def last_nonempty_line(text: str) -> str | None:
    for line in reversed(text.splitlines()):
        cleaned = strip_ansi(line)
        if cleaned:
            return cleaned
    return None


def summarize_known_failure(text: str, fallback: str) -> str:
    lowered = text.lower()

    if "command '['where', 'cl']' returned non-zero exit status 1" in lowered or "error checking compiler version for cl" in lowered:
        return "训练失败：gsplat 在编译 CUDA 扩展时找不到 cl.exe。流水线需要自动加载 VS 2022 的 MSVC v143 14.38 环境。"

    if "error building extension 'gsplat_cuda'" in lowered or "dispatch_segmented_sort.cuh" in lowered:
        return "训练失败：当前 gsplat 触发了本地 CUDA 编译，并在 Windows + CUDA 11.8 上失败。请安装 gsplat 官方预编译 wheel（pt21cu118 / win_amd64）。"

    if "out of memory" in lowered or "cuda out of memory" in lowered:
        return "训练失败：GPU 显存不足。建议进一步降低输入分辨率、减少训练帧数或改成 CPU 缓存图像。"

    if "no exported .ply file was produced" in lowered:
        return "导出失败：未生成 PLY 模型文件。"

    line = last_nonempty_line(text)
    if line:
        return line
    return fallback


def run_command(
    command: list[str] | str,
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        shell=isinstance(command, str),
        capture_output=True,
        text=True,
        check=False,
    )


def run_streaming_command(
    command: list[str] | str,
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    on_line: Callable[[str], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        shell=isinstance(command, str),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    collected: list[str] = []
    assert process.stdout is not None
    for raw_line in process.stdout:
        line = strip_ansi(raw_line.rstrip("\r\n"))
        if not line:
            continue
        collected.append(line)
        if len(collected) > 400:
            collected = collected[-400:]
        if on_line is not None:
            on_line(line)

    returncode = process.wait()
    return subprocess.CompletedProcess(command, returncode, stdout="\n".join(collected), stderr="")


def run_logged_command(
    reporter: "PipelineReporter",
    stage: str,
    command: list[str] | str,
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    log_output_on_success: bool = False,
) -> subprocess.CompletedProcess[str]:
    reporter.log_event(stage, "Command started", command=command_to_string(command), cwd=str(cwd) if cwd else None)
    started_at = time.perf_counter()
    result = run_command(command, cwd=cwd, env=env)
    duration = time.perf_counter() - started_at
    reporter.log_event(
        stage,
        "Command finished",
        returncode=result.returncode,
        duration=format_duration(duration),
    )

    should_log_output = log_output_on_success or result.returncode != 0
    if should_log_output:
        for stream_name, text in (("stdout", result.stdout), ("stderr", result.stderr)):
            if not text or not text.strip():
                continue
            for line in text.splitlines():
                cleaned = strip_ansi(line)
                if cleaned:
                    reporter.log(f"{stream_name}: {cleaned}", stage=stage)
    return result


def run_logged_streaming_command(
    reporter: "PipelineReporter",
    stage: str,
    command: list[str] | str,
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    on_line: Callable[[str], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    reporter.log_event(stage, "Command started", command=command_to_string(command), cwd=str(cwd) if cwd else None)
    started_at = time.perf_counter()
    result = run_streaming_command(command, cwd=cwd, env=env, on_line=on_line)
    duration = time.perf_counter() - started_at
    reporter.log_event(
        stage,
        "Command finished",
        returncode=result.returncode,
        duration=format_duration(duration),
    )
    return result


def format_command_failure(result: subprocess.CompletedProcess[str], fallback: str) -> str:
    details = []
    if result.stderr and result.stderr.strip():
        details.append(result.stderr.strip())
    if result.stdout and result.stdout.strip():
        details.append(result.stdout.strip())

    if not details:
        return fallback

    merged = "\n".join(details)
    return summarize_known_failure(tail_text(merged), fallback)


def combined_command_output(result: subprocess.CompletedProcess[str]) -> str:
    parts = []
    if result.stderr and result.stderr.strip():
        parts.append(result.stderr.strip())
    if result.stdout and result.stdout.strip():
        parts.append(result.stdout.strip())
    return "\n".join(parts)


def require_command(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Required command '{name}' is not available in PATH.")


def find_vcvars64_bat() -> Path | None:
    override = os.getenv("MSVC_VCVARS_BAT")
    if override:
        path = Path(override)
        if path.exists():
            return path

    roots = [
        Path(r"C:\Program Files\Microsoft Visual Studio\2022"),
        Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022"),
        Path(r"C:\Program Files\Microsoft Visual Studio\2019"),
        Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2019"),
    ]
    editions = ("Community", "BuildTools", "Professional", "Enterprise")

    for root in roots:
        for edition in editions:
            candidate = root / edition / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
            if candidate.exists():
                return candidate
    return None


def wrap_with_msvc(command: list[str]) -> list[str] | str:
    if shutil.which("cl") is not None:
        return command

    vcvars_bat = find_vcvars64_bat()
    if vcvars_bat is None:
        return command

    toolset_version = os.getenv("MSVC_TOOLSET_VERSION", "14.38")
    return f'call "{vcvars_bat}" -vcvars_ver={toolset_version} >nul && {subprocess.list2cmdline(command)}'


class PipelineReporter:
    def __init__(self, task_id: str, processed_dir: Path, *, reset_log: bool = True) -> None:
        self.task_id = task_id
        self.processed_dir = processed_dir
        self.log_path = processed_dir / "pipeline.log"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if reset_log or not self.log_path.exists():
            self.log_path.write_text("", encoding="utf-8")
        self.log_tail: list[str] = []
        self.status_message: str | None = None
        self.train_step: int | None = None
        self.train_total_steps: int | None = None
        self.train_eta: str | None = None
        self._last_sync = 0.0
        self._started_at = time.perf_counter()
        self.current_stage = "init"

    def _is_visible_line(self, line: str) -> bool:
        if not line:
            return False
        if re.match(r"^\d+\s+\([\d.]+%\)", line):
            return True
        markers = (
            "Saving config to:",
            "Saving checkpoints to:",
            "Done converting video to images",
            "Done extracting COLMAP features",
            "Done matching COLMAP features",
            "Done COLMAP bundle adjustment",
            "Done refining intrinsics.",
            "All DONE",
            "Colmap matched",
            "COLMAP found poses",
            "Caching / undistorting",
            "No Nerfstudio checkpoint to load",
            "Disabled comet/tensorboard/wandb",
            "Printing profiling stats",
            "Traceback",
            "RuntimeError",
            "ImportError",
            "CalledProcessError",
            "Error",
            "Failed",
            "SAM2",
            "sam2_start",
            "sam2_done",
            "mask",
            "Mask",
            "prune",
            "Prune",
            "extract",
            "Extract",
            "Warning",
        )
        return any(marker in line for marker in markers)

    def _format_line(self, level: str, stage: str, message: str) -> str:
        elapsed = format_duration(time.perf_counter() - self._started_at)
        return f"{now_local_iso()} +{elapsed} [{level}] [{stage}] {message}"

    def _write_line(self, formatted_line: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(formatted_line + "\n")

    def log_event(self, stage: str, message: str, *, level: str = "INFO", force: bool = False, **fields: Any) -> None:
        if not message:
            return

        self.current_stage = stage
        details = ""
        if fields:
            details = " | " + json.dumps(fields, ensure_ascii=False, default=str, sort_keys=True)
        formatted_line = self._format_line(level, stage, message + details)
        self._write_line(formatted_line)
        self.log_tail.append(formatted_line)
        self.log_tail = self.log_tail[-LOG_TAIL_LIMIT:]
        self.sync(force=force)

    def log(self, line: str, *, stage: str | None = None, force: bool = False) -> None:
        if not line:
            return
        formatted_line = self._format_line("CMD", stage or self.current_stage, line)
        self._write_line(formatted_line)

        if self._is_visible_line(line):
            self.log_tail.append(formatted_line)
            self.log_tail = self.log_tail[-LOG_TAIL_LIMIT:]
            self.sync(force=force)

    def sync(self, *, force: bool = False, **changes: Any) -> None:
        now = time.time()
        if not force and now - self._last_sync < 1.0 and not changes:
            return

        payload = {
            "status_message": self.status_message,
            "log_tail": self.log_tail,
            "train_step": self.train_step,
            "train_total_steps": self.train_total_steps,
            "train_eta": self.train_eta,
            "log_rel_path": path_to_storage_url(self.log_path),
        }
        payload.update(changes)
        update_task(self.task_id, **payload)
        self._last_sync = now

    def set_status(
        self,
        *,
        status: str | None = None,
        progress: int | None = None,
        message: str | None = None,
        error_message: str | None = None,
        force: bool = False,
        **extra: Any,
    ) -> None:
        if message is not None:
            self.status_message = message
        payload: dict[str, Any] = {}
        if status is not None:
            payload["status"] = status
        if progress is not None:
            payload["progress"] = progress
        if error_message is not None:
            payload["error_message"] = error_message
        if "train_step" in extra:
            self.train_step = extra["train_step"]
        if "train_total_steps" in extra:
            self.train_total_steps = extra["train_total_steps"]
        if "train_eta" in extra:
            self.train_eta = extra["train_eta"]
        payload.update(extra)
        if message is not None:
            self.log_event(status or self.current_stage, message, level="STATUS", force=force, progress=progress)
        self.sync(force=force, **payload)

    def update_training_step(self, step: int, total_steps: int, eta: str | None = None) -> None:
        self.train_step = step
        self.train_total_steps = total_steps
        if eta is not None:
            self.train_eta = eta

        fraction = min(max(step / max(total_steps, 1), 0.0), 1.0)
        progress = 55 + int(round(fraction * 30))
        self.status_message = f"3DGS 训练中，第 {step} / {total_steps} 步"
        self.sync(progress=progress)


def extract_video_rotation(video_stream: dict[str, Any]) -> float | None:
    for side_data in video_stream.get("side_data_list") or []:
        rotation = side_data.get("rotation")
        if rotation is not None:
            try:
                return float(rotation)
            except (TypeError, ValueError):
                return None
    return None


def ffmpeg_long_edge_scale_filter(max_long_edge: int) -> str:
    # Use FFmpeg's post-autorotation dimensions and avoid accidental upscaling.
    return (
        f"scale=min({max_long_edge}\\,iw):min({max_long_edge}\\,ih):"
        "force_original_aspect_ratio=decrease:force_divisible_by=2"
    )


def probe_video(video_path: Path, reporter: PipelineReporter) -> dict[str, Any]:
    result = run_logged_command(
        reporter,
        "probe",
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(video_path),
        ],
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed.")

    metadata = json.loads(result.stdout)
    video_stream = primary_video_stream(metadata)
    format_meta = metadata.get("format", {})
    reporter.log_event(
        "probe",
        "Video metadata loaded",
        width=video_stream.get("width"),
        height=video_stream.get("height"),
        duration=format_meta.get("duration"),
        codec=video_stream.get("codec_name"),
        rotation=extract_video_rotation(video_stream),
        avg_frame_rate=video_stream.get("avg_frame_rate"),
    )
    return metadata


def normalize_video(
    input_video: Path,
    output_video: Path,
    metadata: dict[str, Any],
    quality_profile: QualityProfile,
    reporter: PipelineReporter,
) -> None:
    video_stream = primary_video_stream(metadata)
    width = int(video_stream.get("width", 0) or 0)
    height = int(video_stream.get("height", 0) or 0)
    format_meta = metadata.get("format", {})
    duration = float(format_meta.get("duration", 0) or 0)

    if duration > 60:
        raise RuntimeError(f"Video duration {duration:.2f}s exceeds the 60s MVP limit.")

    filters = ["fps=3"]
    if quality_profile.video_max_long_edge is not None:
        filters.append(ffmpeg_long_edge_scale_filter(quality_profile.video_max_long_edge))

    reporter.log_event(
        "normalize",
        "Video normalization configured",
        source_width=width,
        source_height=height,
        source_rotation=extract_video_rotation(video_stream),
        source_duration=f"{duration:.2f}s",
        quality_profile=quality_profile.name,
        effective_quality_profile_config=serialize_quality_profile(quality_profile),
        max_long_edge=quality_profile.video_max_long_edge,
        filters=",".join(filters),
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_video),
        "-vf",
        ",".join(filters),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "21",
        str(output_video),
    ]
    result = run_logged_command(reporter, "normalize", command)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpeg normalization failed.")

    normalized_metadata = probe_video(output_video, reporter)
    normalized_stream = primary_video_stream(normalized_metadata)
    reporter.log_event(
        "normalize",
        "Video normalization completed",
        output_path=str(output_video),
        output_width=normalized_stream.get("width"),
        output_height=normalized_stream.get("height"),
        output_duration=normalized_metadata.get("format", {}).get("duration"),
    )


def write_mock_gsplat_ply(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    properties = [
        "x",
        "y",
        "z",
        "scale_0",
        "scale_1",
        "scale_2",
        "rot_0",
        "rot_1",
        "rot_2",
        "rot_3",
        "opacity",
        "f_dc_0",
        "f_dc_1",
        "f_dc_2",
    ] + [f"f_rest_{index}" for index in range(45)]

    points = [
        (-0.18, -0.10, 0.00, 1.0, 0.2, 0.1),
        (-0.05, 0.12, 0.02, 0.8, 0.5, 0.1),
        (0.06, -0.04, -0.02, 0.2, 0.8, 0.3),
        (0.16, 0.10, 0.03, 0.1, 0.3, 0.9),
        (0.00, 0.00, 0.10, 0.9, 0.9, 0.2),
        (0.00, -0.16, -0.08, 0.8, 0.2, 0.8),
    ]

    header_lines = [
        "ply",
        "format binary_little_endian 1.0",
        f"element vertex {len(points)}",
    ]
    header_lines.extend(f"property float {name}" for name in properties)
    header_lines.append("end_header")
    header = ("\n".join(header_lines) + "\n").encode("ascii")

    with output_path.open("wb") as handle:
        handle.write(header)
        for x, y, z, r, g, b in points:
            values = [
                x,
                y,
                z,
                math.log(0.035),
                math.log(0.035),
                math.log(0.035),
                1.0,
                0.0,
                0.0,
                0.0,
                6.0,
                r,
                g,
                b,
            ]
            values.extend([0.0] * 45)
            handle.write(struct.pack("<59f", *values))


def find_latest_config(train_root: Path) -> Path:
    configs = sorted(train_root.glob("outputs/**/config.yml"))
    if not configs:
        raise RuntimeError("Could not find a nerfstudio config.yml after training.")
    return configs[-1]


def ensure_exported_model(model_dir: Path) -> Path:
    target = model_dir / "model.ply"
    preferred = model_dir / "splat.ply"
    if preferred.exists():
        source = preferred
    else:
        ply_files = sorted(
            model_dir.glob("*.ply"),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        if not ply_files:
            raise RuntimeError("No exported .ply file was produced.")
        source = ply_files[0]

    if source == target and not target.exists():
        raise RuntimeError("No exported .ply file was produced.")

    target = model_dir / "model.ply"
    if source != target:
        target.write_bytes(source.read_bytes())
    return target


def resolve_splat_transform_command() -> list[str] | None:
    binary = shutil.which("splat-transform")
    if binary:
        return [binary]

    npx = shutil.which("npx")
    if npx:
        return [npx, "-y", "@playcanvas/splat-transform"]

    return None


def find_runtime_model(model_dir: Path) -> Path:
    sog_path = model_dir / "model.sog"
    if sog_path.exists():
        return sog_path
    return ensure_exported_model(model_dir)


def run_sog_export(model_dir: Path, reporter: PipelineReporter) -> Path:
    source_ply = ensure_exported_model(model_dir)
    output_sog = model_dir / "model.sog"
    output_sog.unlink(missing_ok=True)

    if not sog_export_enabled():
        reporter.log_event(
            "splat-transform",
            "SOG export skipped because it is disabled",
            level="INFO",
            source_ply=str(source_ply),
        )
        return source_ply

    command_prefix = resolve_splat_transform_command()
    if command_prefix is None:
        reporter.log_event(
            "splat-transform",
            "SOG export skipped because splat-transform is unavailable",
            level="WARN",
            source_ply=str(source_ply),
        )
        return source_ply

    iterations = sog_export_iterations()
    gpu = sog_export_gpu()
    command = [*command_prefix]
    if gpu:
        command.extend(["-g", gpu])
    command.extend([
        "-w",
        "-i",
        str(iterations),
        str(source_ply),
        str(output_sog),
    ])

    reporter.log_event(
        "splat-transform",
        "Starting PLY to SOG conversion",
        source_ply=str(source_ply),
        output_sog=str(output_sog),
        iterations=iterations,
        gpu=gpu or "default",
    )

    result = run_logged_streaming_command(
        reporter,
        "splat-transform",
        command,
        cwd=model_dir,
        on_line=lambda line: reporter.log(line, stage="splat-transform"),
    )
    if result.returncode != 0:
        reporter.log_event(
            "splat-transform",
            "SOG export failed, keeping PLY runtime model",
            level="WARN",
            returncode=result.returncode,
            source_ply=str(source_ply),
        )
        return source_ply

    if not output_sog.exists():
        reporter.log_event(
            "splat-transform",
            "SOG export produced no output file, keeping PLY runtime model",
            level="WARN",
            output_sog=str(output_sog),
        )
        return source_ply

    sog_size = output_sog.stat().st_size
    ply_size = source_ply.stat().st_size
    reduction_ratio = None
    if ply_size > 0:
        reduction_ratio = round((1 - (sog_size / ply_size)) * 100, 2)

    reporter.log_event(
        "splat-transform",
        "PLY converted to SOG",
        source_ply=str(source_ply),
        output_sog=str(output_sog),
        ply_size=ply_size,
        sog_size=sog_size,
        reduction_percent=reduction_ratio,
    )
    return output_sog


def find_latest_exported_ply(model_dir: Path, *, exclude_names: set[str] | None = None) -> Path:
    exclude_names = exclude_names or set()
    ply_files = sorted(
        (path for path in model_dir.glob("*.ply") if path.name not in exclude_names),
        key=lambda path: (path.stat().st_mtime_ns, 1 if path.name == "splat.ply" else 0),
        reverse=True,
    )
    if not ply_files:
        raise RuntimeError("No exported .ply file was produced.")
    return ply_files[0]


def ensure_viewer_metadata(model_dir: Path) -> Path:
    metadata_path = model_dir / "viewer.json"
    if metadata_path.exists():
        return metadata_path

    payload = {
        "model_rotation_deg": [0, 0, 0],
        "model_translation": [0, 0, 0],
        "model_scale": 1.0,
        "camera_rotation_deg": [-18, 26, 0],
        "camera_distance": 1.6,
    }
    metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata_path


def analyze_registered_images(model_dir: Path, reporter: PipelineReporter) -> int:
    result = run_logged_command(
        reporter,
        "colmap-model-select",
        [
            "colmap",
            "model_analyzer",
            "--path",
            str(model_dir),
        ],
    )
    if result.returncode != 0:
        reporter.log_event("colmap-model-select", "COLMAP model analysis failed", level="WARN", model_dir=str(model_dir))
        return 0

    match = re.search(r"Registered images:\s+(\d+)", combined_command_output(result))
    if match is None:
        reporter.log_event("colmap-model-select", "COLMAP registered image count was not found", level="WARN", model_dir=str(model_dir))
        return 0
    registered_images = int(match.group(1))
    reporter.log_event(
        "colmap-model-select",
        "COLMAP model analyzed",
        model_dir=str(model_dir),
        registered_images=registered_images,
    )
    return registered_images


def count_transform_frames(transforms_path: Path) -> int:
    if not transforms_path.exists():
        return 0

    payload = json.loads(transforms_path.read_text(encoding="utf-8"))
    return len(payload.get("frames", []))


def read_image_dimensions(image_path: Path) -> tuple[int | None, int | None]:
    if image_path.suffix.lower() == ".png":
        try:
            with image_path.open("rb") as handle:
                header = handle.read(24)
            if header.startswith(b"\x89PNG\r\n\x1a\n") and len(header) >= 24:
                width, height = struct.unpack(">II", header[16:24])
                return int(width), int(height)
        except OSError:
            return None, None

    if image_path.suffix.lower() in {".jpg", ".jpeg"}:
        try:
            with image_path.open("rb") as handle:
                if handle.read(2) != b"\xff\xd8":
                    return None, None
                while True:
                    marker_start = handle.read(1)
                    if not marker_start:
                        return None, None
                    if marker_start != b"\xff":
                        continue
                    marker = handle.read(1)
                    while marker == b"\xff":
                        marker = handle.read(1)
                    if marker in {b"\xc0", b"\xc1", b"\xc2", b"\xc3"}:
                        handle.read(3)
                        height, width = struct.unpack(">HH", handle.read(4))
                        return int(width), int(height)
                    length = struct.unpack(">H", handle.read(2))[0]
                    handle.seek(length - 2, os.SEEK_CUR)
        except (OSError, struct.error):
            return None, None

    return None, None


def select_mask_prompt_frame(dataset_dir: Path, quality_profile: QualityProfile, reporter: PipelineReporter) -> Path:
    images_dir = dataset_dir / "images"
    image_paths = sorted(path for path in images_dir.iterdir() if path.is_file())
    if not image_paths:
        raise RuntimeError("No extracted images are available for mask prompting.")

    prompt_name = image_paths[0].name
    preview_factor = quality_profile.train_downscale_factor or 1
    preview_dir = dataset_dir / ("images" if preview_factor == 1 else f"images_{preview_factor}")
    preview_path = preview_dir / prompt_name
    if not preview_path.exists():
        preview_path = images_dir / prompt_name

    width, height = read_image_dimensions(preview_path)
    reporter.set_status(
        status="awaiting_mask_prompt",
        progress=54,
        message="COLMAP 与 transforms.json 已完成，请在第一帧点选商品并生成分割预览，确认后继续训练",
        mask_prompt_frame_rel_path=path_to_storage_url(preview_path),
        mask_prompt_frame_name=prompt_name,
        mask_prompt_frame_width=width,
        mask_prompt_frame_height=height,
        mask_preview_rel_path=None,
        pipeline_pid=None,
    )
    reporter.log_event(
        "mask-prompt",
        "Pipeline paused for mask prompt",
        prompt_frame=str(preview_path),
        prompt_frame_name=prompt_name,
        width=width,
        height=height,
        force=True,
    )
    return preview_path


def inject_mask_paths_into_transforms(dataset_dir: Path, quality_profile: QualityProfile, reporter: PipelineReporter) -> int:
    transforms_path = dataset_dir / "transforms.json"
    if not transforms_path.exists():
        raise RuntimeError("transforms.json does not exist, cannot inject mask_path entries.")

    payload = json.loads(transforms_path.read_text(encoding="utf-8"))
    frames = payload.get("frames") or []
    if not frames:
        raise RuntimeError("transforms.json has no frames, cannot inject mask_path entries.")

    expected_factor = quality_profile.train_downscale_factor or 1
    expected_mask_dir = dataset_dir / ("masks" if expected_factor == 1 else f"masks_{expected_factor}")
    missing: list[str] = []

    for frame in frames:
        frame_name = Path(frame["file_path"]).name
        frame["mask_path"] = f"masks/{frame_name}"
        if not (expected_mask_dir / frame_name).exists():
            missing.append(frame_name)

    if missing:
        preview = ", ".join(missing[:5])
        raise RuntimeError(f"SAM 2 did not produce masks for {len(missing)} transform frames. Missing: {preview}")

    atomic_write_json(transforms_path, payload)
    reporter.log_event(
        "mask-inject",
        "mask_path entries injected into transforms.json",
        frames=len(frames),
        expected_mask_dir=str(expected_mask_dir),
        force=True,
    )
    return len(frames)


def sam2_python_command_prefix() -> list[str]:
    override = os.getenv("SAM2_PYTHON")
    if override:
        override_path = Path(override)
        if override_path.exists():
            return [str(override_path)]
        raise RuntimeError(f"SAM2_PYTHON points to a missing file: {override}")

    env_name = os.getenv("SAM2_CONDA_ENV", "sam2_app")
    for candidate in (
        Path(r"D:\miniconda3\envs") / env_name / "python.exe",
        Path(r"C:\ProgramData\miniconda3\envs") / env_name / "python.exe",
        Path.home() / "miniconda3" / "envs" / env_name / ("python.exe" if os.name == "nt" else "bin/python"),
        Path.home() / "anaconda3" / "envs" / env_name / ("python.exe" if os.name == "nt" else "bin/python"),
    ):
        if candidate.exists():
            return [str(candidate)]

    conda = shutil.which("conda")
    if conda:
        if os.name == "nt":
            return ["cmd", "/c", "conda", "run", "-n", env_name, "python"]
        return [conda, "run", "-n", env_name, "python"]

    raise RuntimeError(
        "SAM 2 Python environment was not found. Create it from trainer/sam2_environment.yml "
        "or set SAM2_PYTHON to the sam2_app python executable."
    )


def python_has_modules(modules: tuple[str, ...]) -> bool:
    return all(importlib.util.find_spec(name) is not None for name in modules)


def pruning_python_command_prefix() -> list[str]:
    override = os.getenv("PRUNING_PYTHON")
    if override:
        override_path = Path(override)
        if override_path.exists():
            return [str(override_path)]
        raise RuntimeError(f"PRUNING_PYTHON points to a missing file: {override}")

    if python_has_modules(("numpy", "PIL")):
        return [sys.executable]

    env_name = os.getenv("PRUNING_CONDA_ENV", "3dgs_app")
    for candidate in (
        Path(r"D:\miniconda3\envs") / env_name / "python.exe",
        Path(r"C:\ProgramData\miniconda3\envs") / env_name / "python.exe",
        Path.home() / "miniconda3" / "envs" / env_name / ("python.exe" if os.name == "nt" else "bin/python"),
        Path.home() / "anaconda3" / "envs" / env_name / ("python.exe" if os.name == "nt" else "bin/python"),
    ):
        if candidate.exists():
            return [str(candidate)]

    conda = shutil.which("conda")
    if conda:
        if os.name == "nt":
            return ["cmd", "/c", "conda", "run", "-n", env_name, "python"]
        return [conda, "run", "-n", env_name, "python"]

    raise RuntimeError(
        "Object pruning Python environment was not found. "
        "Install numpy and pillow into the current environment, or set PRUNING_PYTHON, "
        "or create/select the conda env via PRUNING_CONDA_ENV (default: 3dgs_app)."
    )


def build_sam2_mask_command(dataset_dir: Path, prompts_path: Path, quality_profile: QualityProfile) -> list[str]:
    source_factor = quality_profile.train_downscale_factor or 1
    command = [
        *sam2_python_command_prefix(),
        "-m",
        "trainer.sam2_masking",
        "--dataset-dir",
        str(dataset_dir),
        "--prompts",
        str(prompts_path),
        "--source-factor",
        str(source_factor),
        "--num-downscales",
        str(quality_profile.process_num_downscales),
        "--model-id",
        os.getenv("SAM2_MODEL_ID", "facebook/sam2.1-hiera-small"),
    ]
    if os.getenv("SAM2_CHECKPOINT"):
        command.extend(["--checkpoint", os.environ["SAM2_CHECKPOINT"]])
    if os.getenv("SAM2_MODEL_CFG"):
        command.extend(["--model-cfg", os.environ["SAM2_MODEL_CFG"]])
    return command


def has_complete_training_masks(dataset_dir: Path, quality_profile: QualityProfile) -> bool:
    transforms_path = dataset_dir / "transforms.json"
    if not transforms_path.exists():
        return False

    try:
        payload = json.loads(transforms_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False

    frames = payload.get("frames") or []
    if not frames:
        return False

    expected_factor = quality_profile.train_downscale_factor or 1
    expected_mask_dir = dataset_dir / ("masks" if expected_factor == 1 else f"masks_{expected_factor}")
    if not expected_mask_dir.exists():
        return False

    return all((expected_mask_dir / Path(frame["file_path"]).name).exists() for frame in frames)


def build_sam2_preview_command(
    dataset_dir: Path,
    prompts_path: Path,
    quality_profile: QualityProfile,
    output_preview_dir: Path,
    output_preview_manifest_path: Path,
) -> list[str]:
    source_factor = quality_profile.train_downscale_factor or 1
    command = [
        *sam2_python_command_prefix(),
        "-m",
        "trainer.sam2_masking",
        "--dataset-dir",
        str(dataset_dir),
        "--prompts",
        str(prompts_path),
        "--source-factor",
        str(source_factor),
        "--num-downscales",
        str(quality_profile.process_num_downscales),
        "--model-id",
        os.getenv("SAM2_MODEL_ID", "facebook/sam2.1-hiera-small"),
        "--preview-output-dir",
        str(output_preview_dir),
        "--preview-manifest",
        str(output_preview_manifest_path),
    ]
    if os.getenv("SAM2_CHECKPOINT"):
        command.extend(["--checkpoint", os.environ["SAM2_CHECKPOINT"]])
    if os.getenv("SAM2_MODEL_CFG"):
        command.extend(["--model-cfg", os.environ["SAM2_MODEL_CFG"]])
    return command


def run_object_masking(dataset_dir: Path, quality_profile: QualityProfile, reporter: PipelineReporter) -> None:
    prompts_path = dataset_dir.parent / "mask_prompts.json"
    if not prompts_path.exists():
        raise RuntimeError("Mask prompts were not found. Submit prompts before resuming the masking pipeline.")

    if has_complete_training_masks(dataset_dir, quality_profile):
        reporter.set_status(status="masking", progress=55, message="复用预览阶段已生成的全帧 masks", force=True)
        reporter.log_event(
            "sam2-mask",
            "Reusing masks generated during preview",
            dataset_dir=str(dataset_dir),
            force=True,
        )
    else:
        reporter.set_status(status="masking", progress=55, message="正在调用 SAM 2 生成商品主体 masks", force=True)
        result = run_logged_streaming_command(
            reporter,
            "sam2-mask",
            build_sam2_mask_command(dataset_dir, prompts_path, quality_profile),
            cwd=REPO_ROOT,
            on_line=lambda line: reporter.log(line, stage="sam2-mask"),
        )
        if result.returncode != 0:
            raise RuntimeError(format_command_failure(result, "SAM 2 mask generation failed."))

    summary_path = dataset_dir / "mask_summary.json"
    update_task(
        reporter.task_id,
        mask_summary_rel_path=path_to_storage_url(summary_path) if summary_path.exists() else None,
    )
    transforms_path = dataset_dir / "transforms.json"
    frame_count = count_transform_frames(transforms_path)
    reporter.log_event(
        "sam2-mask",
        "SAM 2 masks prepared for post-training object extraction",
        transforms_path=str(transforms_path),
        frame_count=frame_count,
        force=True,
    )
    reporter.set_status(progress=55, message=f"SAM 2 masks 已生成，共 {frame_count} 帧；接下来训练完整场景并在导出后提取商品高斯", force=True)


def ensure_original_sparse_pointcloud(dataset_dir: Path, reporter: PipelineReporter) -> tuple[Path, Path]:
    transforms_path = dataset_dir / "transforms.json"
    if not transforms_path.exists():
        raise RuntimeError("transforms.json does not exist, cannot prepare sparse point cloud pruning.")

    payload = json.loads(transforms_path.read_text(encoding="utf-8"))
    original_path = dataset_dir / "sparse_pc_original.ply"
    configured_name = str(payload.get("original_ply_file_path") or payload.get("ply_file_path") or "sparse_pc.ply")
    configured_path = dataset_dir / configured_name
    if configured_path.name == "sparse_pc_masked.ply":
        fallback = dataset_dir / "sparse_pc.ply"
        if fallback.exists():
            configured_path = fallback
        elif original_path.exists():
            configured_path = original_path

    if not original_path.exists():
        if not configured_path.exists():
            raise RuntimeError(f"Sparse point cloud was not found for pruning: {configured_path}")
        shutil.copyfile(configured_path, original_path)
        payload["original_ply_file_path"] = original_path.name
        atomic_write_json(transforms_path, payload)
        reporter.log_event(
            "3d-prune-sparse",
            "Original sparse point cloud snapshot created",
            source_ply=str(configured_path),
            original_ply=str(original_path),
            force=True,
        )

    output_path = dataset_dir / "sparse_pc_masked.ply"
    return original_path, output_path


def set_transforms_ply_file(dataset_dir: Path, ply_filename: str, reporter: PipelineReporter) -> None:
    transforms_path = dataset_dir / "transforms.json"
    payload = json.loads(transforms_path.read_text(encoding="utf-8"))
    payload["ply_file_path"] = ply_filename
    atomic_write_json(transforms_path, payload)
    reporter.log_event(
        "3d-prune-sparse",
        "transforms.json updated to use filtered sparse point cloud",
        ply_file_path=ply_filename,
        force=True,
    )


def restore_full_scene_training_inputs(dataset_dir: Path, reporter: PipelineReporter) -> None:
    transforms_path = dataset_dir / "transforms.json"
    if not transforms_path.exists():
        raise RuntimeError("transforms.json does not exist, cannot restore full-scene training inputs.")

    payload = json.loads(transforms_path.read_text(encoding="utf-8"))
    changed = False

    original_ply_name = payload.get("original_ply_file_path")
    if original_ply_name:
        original_ply_path = dataset_dir / str(original_ply_name)
        if original_ply_path.exists() and payload.get("ply_file_path") != original_ply_path.name:
            payload["ply_file_path"] = original_ply_path.name
            changed = True
    else:
        default_sparse = dataset_dir / "sparse_pc.ply"
        if default_sparse.exists() and payload.get("ply_file_path") != default_sparse.name:
            payload["ply_file_path"] = default_sparse.name
            changed = True

    for frame in payload.get("frames") or []:
        if "mask_path" in frame:
            frame.pop("mask_path", None)
            changed = True

    if changed:
        atomic_write_json(transforms_path, payload)
        reporter.log_event(
            "full-scene-train",
            "Restored transforms.json for full-scene training",
            ply_file_path=payload.get("ply_file_path"),
            removed_mask_paths=True,
            force=True,
        )


def build_sparse_prune_command(
    dataset_dir: Path,
    quality_profile: QualityProfile,
    input_ply: Path,
    output_ply: Path,
    summary_path: Path,
) -> list[str]:
    return [
        *pruning_python_command_prefix(),
        "-m",
        "trainer.object_pruning",
        "sparse",
        "--dataset-dir",
        str(dataset_dir),
        "--input-ply",
        str(input_ply),
        "--output-ply",
        str(output_ply),
        "--summary-path",
        str(summary_path),
        "--mask-factor",
        str(quality_profile.train_downscale_factor or 1),
    ]


def build_gaussian_prune_command(
    dataset_dir: Path,
    quality_profile: QualityProfile,
    input_ply: Path,
    raw_output_ply: Path | None,
    output_ply: Path,
    summary_path: Path,
    dataparser_transforms_path: Path,
) -> list[str]:
    command = [
        *pruning_python_command_prefix(),
        "-m",
        "trainer.object_pruning",
        "gaussian",
        "--dataset-dir",
        str(dataset_dir),
        "--input-ply",
        str(input_ply),
        "--output-ply",
        str(output_ply),
        "--summary-path",
        str(summary_path),
        "--dataparser-transforms",
        str(dataparser_transforms_path),
        "--mask-factor",
        str(quality_profile.train_downscale_factor or 1),
        "--min-front-visible-views",
        "6",
        "--min-front-inside-views",
        "3",
        "--min-front-inside-ratio",
        "0.15",
        "--depth-margin-scale",
        "1.5",
        "--spatial-neighbor-threshold",
        "12",
        "--spatial-component-keep-ratio",
        "0.015",
    ]
    if raw_output_ply is not None:
        command.extend(["--raw-output-ply", str(raw_output_ply)])
    return command


def run_sparse_point_pruning(dataset_dir: Path, quality_profile: QualityProfile, reporter: PipelineReporter) -> Path:
    input_ply, output_ply = ensure_original_sparse_pointcloud(dataset_dir, reporter)
    summary_path = dataset_dir / "sparse_pruning_summary.json"
    reporter.set_status(progress=56, message="正在过滤 COLMAP 稀疏点云，只保留商品主体 seed points", force=True)
    result = run_logged_streaming_command(
        reporter,
        "3d-prune-sparse",
        build_sparse_prune_command(dataset_dir, quality_profile, input_ply, output_ply, summary_path),
        cwd=REPO_ROOT,
        on_line=lambda line: reporter.log(line, stage="3d-prune-sparse"),
    )
    if result.returncode != 0:
        raise RuntimeError(format_command_failure(result, "3D sparse point pruning failed."))

    set_transforms_ply_file(dataset_dir, output_ply.name, reporter)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    reporter.log_event(
        "3d-prune-sparse",
        "Sparse point cloud pruning completed",
        input_points=summary.get("input_points"),
        kept_points=summary.get("kept_points"),
        keep_ratio=summary.get("keep_ratio"),
        summary_path=str(summary_path),
        output_ply=str(output_ply),
        force=True,
    )
    reporter.set_status(
        progress=57,
        message=f"3D 稀疏点裁剪完成，保留 {summary.get('kept_points')} / {summary.get('input_points')} 个 seed points",
        force=True,
    )
    return output_ply


def run_gaussian_pruning(
    dataset_dir: Path,
    model_dir: Path,
    quality_profile: QualityProfile,
    dataparser_transforms_path: Path,
    reporter: PipelineReporter,
) -> Path:
    export_source = find_latest_exported_ply(
        model_dir,
        exclude_names={
            "model.ply",
            "model_full.ply",
            "splat_unpruned.ply",
            "splat_full.ply",
            "splat_object_raw.ply",
            "splat_object_clean.ply",
        },
    )
    full_backup = model_dir / "splat_full.ply"
    raw_output = model_dir / "splat_object_raw.ply"
    clean_output = model_dir / "splat_object_clean.ply"
    legacy_unpruned_backup = model_dir / "splat_unpruned.ply"
    summary_path = model_dir / "object_extraction_summary.json"

    shutil.copyfile(export_source, full_backup)
    shutil.copyfile(export_source, legacy_unpruned_backup)
    (model_dir / "model_full.ply").write_bytes(full_backup.read_bytes())

    reporter.set_status(progress=92, message="正在基于 SAM 2 masks 提取商品高斯，保留完整场景训练结果作为备份", force=True)
    result = run_logged_streaming_command(
        reporter,
        "3d-object-extract",
        build_gaussian_prune_command(
            dataset_dir,
            quality_profile,
            full_backup,
            raw_output,
            clean_output,
            summary_path,
            dataparser_transforms_path,
        ),
        cwd=REPO_ROOT,
        on_line=lambda line: reporter.log(line, stage="3d-object-extract"),
    )
    if result.returncode != 0:
        raise RuntimeError(format_command_failure(result, "3D object extraction failed."))

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    final_output = model_dir / "splat.ply"
    shutil.copyfile(clean_output, final_output)
    reporter.log_event(
        "3d-object-extract",
        "Object-only Gaussian extraction completed",
        input_gaussians=summary.get("input_gaussians"),
        raw_gaussians=summary.get("raw_gaussians"),
        clean_gaussians=summary.get("clean_gaussians"),
        clean_keep_ratio=summary.get("clean_keep_ratio"),
        summary_path=str(summary_path),
        full_backup=str(full_backup),
        raw_output=str(raw_output),
        clean_output=str(clean_output),
        legacy_unpruned_backup=str(legacy_unpruned_backup),
        force=True,
    )
    reporter.set_status(
        progress=94,
        message=(
            f"商品高斯提取完成，raw {summary.get('raw_gaussians')} / {summary.get('input_gaussians')}，"
            f"clean {summary.get('clean_gaussians')} / {summary.get('input_gaussians')}"
        ),
        force=True,
    )
    return final_output


def extract_eta_from_train_line(line: str) -> str | None:
    time_matches = re.findall(r"(\d+h|\d+m|\d+s)", line)
    if time_matches:
        return " ".join(time_matches[-3:])
    return None


def handle_preprocess_line(task_id: str, reporter: PipelineReporter, line: str) -> None:
    reporter.log(line, stage="ns-process-data")
    if "Done converting video to images" in line:
        reporter.set_status(progress=35, message="视频抽帧完成，开始 COLMAP 特征提取")
    elif "Done extracting COLMAP features" in line:
        reporter.set_status(progress=40, message="COLMAP 特征提取完成，开始特征匹配")
    elif "Done matching COLMAP features" in line:
        reporter.set_status(progress=45, message="COLMAP 特征匹配完成，开始位姿恢复")
    elif "Done COLMAP bundle adjustment" in line:
        reporter.set_status(progress=50, message="COLMAP 位姿恢复完成，正在做束调整")
    elif "Done refining intrinsics." in line:
        reporter.set_status(progress=52, message="相机内参优化完成，正在生成 transforms.json")
    else:
        match = re.search(r"Colmap matched (\d+) images", line)
        if match:
            reporter.set_status(message=f"COLMAP 已匹配 {match.group(1)} 张图像")


def handle_train_line(task_id: str, reporter: PipelineReporter, line: str, train_max_steps: int) -> None:
    reporter.log(line, stage="ns-train")
    if "Saving config to:" in line:
        reporter.set_status(message="Splatfacto 初始化中，正在写入训练配置")
        return
    if "Caching / undistorting eval images" in line:
        reporter.set_status(progress=57, message="训练初始化中，正在缓存评估图像")
        return
    if "Caching / undistorting train images" in line:
        reporter.set_status(progress=58, message="训练初始化中，正在缓存训练图像")
        return
    if "No Nerfstudio checkpoint to load" in line:
        reporter.set_status(message="未发现历史 checkpoint，从头开始训练")
        return

    match = re.match(r"^(\d+)\s+\(([\d.]+)%\)", line)
    if match:
        step = int(match.group(1))
        eta = extract_eta_from_train_line(line)
        reporter.update_training_step(step, train_max_steps, eta=eta)


def handle_export_line(task_id: str, reporter: PipelineReporter, line: str) -> None:
    reporter.log(line, stage="ns-export")
    if "Exporting" in line or "writing" in line.lower():
        reporter.set_status(progress=90, message="正在导出高斯点云模型")


def rebuild_transforms_with_best_model(dataset_dir: Path, colmap_cmd: str, reporter: PipelineReporter) -> None:
    sparse_root = dataset_dir / "colmap" / "sparse"
    if not sparse_root.exists():
        raise RuntimeError("COLMAP sparse output directory was not created.")

    best_model: Path | None = None
    best_registered_images = -1
    for candidate in sorted(path for path in sparse_root.iterdir() if path.is_dir()):
        registered_images = analyze_registered_images(candidate, reporter)
        if registered_images > best_registered_images:
            best_registered_images = registered_images
            best_model = candidate

    if best_model is None:
        raise RuntimeError("COLMAP did not produce any sparse model.")

    reporter.set_status(
        progress=53,
        message=f"已选择 COLMAP 最佳模型 sparse/{best_model.name}，注册图像 {best_registered_images} 张",
    )

    current_frames = count_transform_frames(dataset_dir / "transforms.json")
    if best_model.name == "0" and current_frames >= best_registered_images:
        return

    result = run_logged_command(
        reporter,
        "transforms-rebuild",
        [
            "ns-process-data",
            "images",
            "--data",
            str(dataset_dir / "images"),
            "--output-dir",
            str(dataset_dir),
            "--skip-image-processing",
            "--skip-colmap",
            "--colmap-model-path",
            f"colmap/sparse/{best_model.name}",
            "--colmap-cmd",
            colmap_cmd,
        ],
        cwd=dataset_dir.parent,
        log_output_on_success=True,
    )
    if result.returncode != 0:
        raise RuntimeError(format_command_failure(result, "Failed to rebuild transforms from the best COLMAP model."))

    final_frames = count_transform_frames(dataset_dir / "transforms.json")
    if final_frames <= 2:
        raise RuntimeError(
            f"COLMAP reconstruction is too small for training. Best sparse model '{best_model.name}' only yielded {final_frames} frames."
        )

    reporter.set_status(progress=54, message=f"transforms.json 已生成，共 {final_frames} 帧")


def build_train_command(dataset_dir: Path, quality_profile: QualityProfile, train_max_steps: int) -> list[str]:
    command = [
        "ns-train",
        "splatfacto",
        "--max-num-iterations",
        str(train_max_steps),
        "--vis",
        "tensorboard",
        "--logging.local-writer.max-log-size",
        "0",
        "--logging.steps-per-log",
        "10",
        "--pipeline.datamanager.cache-images",
        "cpu",
        "--pipeline.model.num-downscales",
        str(quality_profile.model_num_downscales),
        "nerfstudio-data",
        "--data",
        str(dataset_dir),
    ]
    if quality_profile.train_downscale_factor is not None:
        command.extend(["--downscale-factor", str(quality_profile.train_downscale_factor)])
    return command


def run_preprocess_pipeline(
    task_id: str,
    normalized_video: Path,
    processed_dir: Path,
    quality_profile: QualityProfile,
    reporter: PipelineReporter,
) -> tuple[Path, str]:
    for command in ("ffmpeg", "ffprobe", "colmap", "ns-process-data", "ns-train", "ns-export"):
        require_command(command)
        reporter.log_event("preflight", "Required command found", command=command, path=shutil.which(command))

    dataset_dir = processed_dir / "dataset"
    colmap_compat = REPO_ROOT / "trainer" / "colmap_compat.py"
    colmap_cmd = f'"{sys.executable}" "{colmap_compat}"'

    reporter.set_status(
        status="preprocessing",
        progress=30,
        message="预处理完成，开始运行 ns-process-data",
        processed_rel_path=path_to_storage_url(processed_dir),
        force=True,
    )

    preprocess_result = run_logged_streaming_command(
        reporter,
        "ns-process-data",
        [
            "ns-process-data",
            "video",
            "--data",
            str(normalized_video),
            "--output-dir",
            str(dataset_dir),
            "--num-downscales",
            str(quality_profile.process_num_downscales),
            "--colmap-cmd",
            colmap_cmd,
        ],
        cwd=processed_dir,
        on_line=lambda line: handle_preprocess_line(task_id, reporter, line),
    )
    if preprocess_result.returncode != 0:
        raise RuntimeError(format_command_failure(preprocess_result, "ns-process-data failed."))

    rebuild_transforms_with_best_model(dataset_dir, colmap_cmd, reporter)
    return dataset_dir, colmap_cmd


def run_training_export_pipeline(
    task_id: str,
    processed_dir: Path,
    model_dir: Path,
    dataset_dir: Path,
    quality_profile: QualityProfile,
    train_max_steps: int,
    reporter: PipelineReporter,
    *,
    post_export_gaussian_pruning: bool = False,
) -> Path:
    for command in ("ns-train", "ns-export"):
        require_command(command)
        reporter.log_event("preflight", "Required command found", command=command, path=shutil.which(command))

    reporter.set_status(
        status="training",
        progress=55,
        message="3DGS 训练初始化中",
        processed_rel_path=path_to_storage_url(processed_dir),
        train_step=0,
        train_total_steps=train_max_steps,
        train_eta=None,
        force=True,
    )

    train_result = run_logged_streaming_command(
        reporter,
        "ns-train",
        wrap_with_msvc(build_train_command(dataset_dir, quality_profile, train_max_steps)),
        cwd=processed_dir,
        on_line=lambda line: handle_train_line(task_id, reporter, line, train_max_steps),
    )
    if train_result.returncode != 0:
        raise RuntimeError(format_command_failure(train_result, "ns-train splatfacto failed."))

    config_path = find_latest_config(processed_dir)

    reporter.set_status(status="exporting", progress=85, message="训练完成，开始导出 Gaussian Splat 模型", force=True)

    export_result = run_logged_streaming_command(
        reporter,
        "ns-export",
        wrap_with_msvc([
            "ns-export",
            "gaussian-splat",
            "--load-config",
            str(config_path),
            "--output-dir",
            str(model_dir),
        ]),
        cwd=processed_dir,
        on_line=lambda line: handle_export_line(task_id, reporter, line),
    )
    if export_result.returncode != 0:
        raise RuntimeError(format_command_failure(export_result, "ns-export gaussian-splat failed."))

    if post_export_gaussian_pruning:
        dataparser_transforms_path = config_path.parent / "dataparser_transforms.json"
        if not dataparser_transforms_path.exists():
            raise RuntimeError(f"dataparser_transforms.json was not found after training: {dataparser_transforms_path}")
        run_gaussian_pruning(dataset_dir, model_dir, quality_profile, dataparser_transforms_path, reporter)

    ensure_exported_model(model_dir)
    return run_sog_export(model_dir, reporter)


def run_real_pipeline(
    task_id: str,
    normalized_video: Path,
    processed_dir: Path,
    model_dir: Path,
    quality_profile: QualityProfile,
    train_max_steps: int,
    reporter: PipelineReporter,
) -> Path:
    dataset_dir, _ = run_preprocess_pipeline(task_id, normalized_video, processed_dir, quality_profile, reporter)
    return run_training_export_pipeline(
        task_id,
        processed_dir,
        model_dir,
        dataset_dir,
        quality_profile,
        train_max_steps,
        reporter,
        post_export_gaussian_pruning=False,
    )


def run_task(
    task_id: str,
    input_video: Path,
    *,
    mock: bool = False,
    quality_profile_name: str | None = None,
    train_max_steps: int | None = None,
    object_masking: bool = False,
    resume_after_mask: bool = False,
) -> Path | None:
    ensure_layout()
    task = get_task(task_id)
    if task is None:
        raise RuntimeError(f"Task '{task_id}' not found.")

    requested_quality_profile = resolve_quality_profile(quality_profile_name)
    quality_profile = requested_quality_profile
    if object_masking and requested_quality_profile.name == "raw":
        raise RuntimeError("Object masking is disabled for the raw profile in the MVP.")
    train_max_steps = resolve_train_max_steps(train_max_steps)
    processed_dir = task_processed_dir(task_id)
    model_dir = task_model_dir(task_id)
    processed_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    reporter = PipelineReporter(task_id, processed_dir, reset_log=not resume_after_mask)

    try:
        reporter.log_event(
            "task",
            "Pipeline task resumed after mask prompt" if resume_after_mask else "Pipeline task started",
            task_id=task_id,
            input_video=str(input_video),
            mock=mock,
            object_masking=object_masking,
            resume_after_mask=resume_after_mask,
            quality_profile=requested_quality_profile.name,
            quality_profile_config=serialize_quality_profile(requested_quality_profile),
            repo_root=str(REPO_ROOT),
            python=sys.executable,
            force=True,
            train_max_steps=train_max_steps,
        )

        if resume_after_mask:
            if not object_masking:
                raise RuntimeError("--resume-after-mask requires --object-masking.")
            dataset_dir = processed_dir / "dataset"
            if not dataset_dir.exists():
                raise RuntimeError("Processed dataset directory was not found for mask resume.")
            metadata = task.get("video_metadata") if isinstance(task.get("video_metadata"), dict) else None
            if metadata is None and input_video.exists():
                metadata = probe_video(input_video, reporter)
            restored_profile = restore_effective_quality_profile(task, requested_quality_profile)
            if restored_profile is not None:
                quality_profile = restored_profile
            elif metadata is not None:
                quality_profile = adapt_quality_profile_to_video(metadata, requested_quality_profile)
            log_effective_quality_profile(
                reporter,
                requested_profile=requested_quality_profile,
                effective_profile=quality_profile,
                metadata=metadata,
                restored_from_task=restored_profile is not None,
            )
            reporter.set_status(
                status="masking",
                progress=55,
                message="Mask 提示已收到，开始生成 SAM 2 masks",
                force=True,
                error_message=None,
                log_rel_path=path_to_storage_url(reporter.log_path),
                object_masking=object_masking,
                quality_profile=requested_quality_profile.name,
                train_max_steps=train_max_steps,
                pipeline_pid=os.getpid(),
                effective_train_downscale_factor=quality_profile.train_downscale_factor,
                effective_model_num_downscales=quality_profile.model_num_downscales,
                effective_quality_profile_config=serialize_quality_profile(quality_profile),
            )
            run_object_masking(dataset_dir, quality_profile, reporter)
            restore_full_scene_training_inputs(dataset_dir, reporter)
            output_model = run_training_export_pipeline(
                task_id,
                processed_dir,
                model_dir,
                dataset_dir,
                quality_profile,
                train_max_steps,
                reporter,
                post_export_gaussian_pruning=True,
            )
        elif mock:
            reporter.set_status(
                status="preprocessing",
                progress=10,
                message="mock 流水线初始化中",
                force=True,
                error_message=None,
                mock_mode=mock,
                train_step=None,
                train_total_steps=None,
                train_eta=None,
                log_rel_path=path_to_storage_url(reporter.log_path),
                object_masking=object_masking,
                quality_profile=quality_profile.name,
                train_max_steps=train_max_steps,
                pipeline_pid=os.getpid(),
            )
            if object_masking:
                reporter.log_event("mock", "Object masking is skipped in mock mode", force=True)
            reporter.set_status(status="training", progress=55, message="mock 训练中", force=True)
            reporter.set_status(status="exporting", progress=85, message="mock 导出中", force=True)
            output_model = model_dir / "model.ply"
            write_mock_gsplat_ply(output_model)
            reporter.log_event("mock", "Mock PLY written", output_model=str(output_model))
        else:
            reporter.set_status(
                status="preprocessing",
                progress=10,
                message="正在检查视频元数据",
                force=True,
                error_message=None,
                mock_mode=mock,
                train_step=None,
                train_total_steps=None,
                train_eta=None,
                log_rel_path=path_to_storage_url(reporter.log_path),
                object_masking=object_masking,
                quality_profile=requested_quality_profile.name,
                train_max_steps=train_max_steps,
                pipeline_pid=os.getpid(),
            )

            metadata = probe_video(input_video, reporter)
            quality_profile = adapt_quality_profile_to_video(metadata, requested_quality_profile)
            update_task(
                task_id,
                video_metadata=metadata,
                progress=15,
                status_message="视频元数据检查完成",
                effective_train_downscale_factor=quality_profile.train_downscale_factor,
                effective_model_num_downscales=quality_profile.model_num_downscales,
                effective_quality_profile_config=serialize_quality_profile(quality_profile),
            )
            reporter.log_event("probe", "Video metadata persisted", progress=15)
            log_effective_quality_profile(
                reporter,
                requested_profile=requested_quality_profile,
                effective_profile=quality_profile,
                metadata=metadata,
            )

            normalized_video = processed_dir / "normalized.mp4"
            normalize_video(input_video, normalized_video, metadata, quality_profile, reporter)

            reporter.set_status(
                progress=30,
                message="视频转码完成，准备开始 SfM 与 3DGS 流水线",
                processed_rel_path=path_to_storage_url(processed_dir),
                force=True,
            )

            if object_masking:
                dataset_dir, _ = run_preprocess_pipeline(
                    task_id,
                    normalized_video,
                    processed_dir,
                    quality_profile,
                    reporter,
                )
                select_mask_prompt_frame(dataset_dir, quality_profile, reporter)
                return None

            output_model = run_real_pipeline(
                task_id,
                normalized_video,
                processed_dir,
                model_dir,
                quality_profile,
                train_max_steps,
                reporter,
            )

        ensure_viewer_metadata(model_dir)
        reporter.log_event("viewer", "Viewer metadata ensured", metadata_path=str(model_dir / "viewer.json"))
        runtime_model = find_runtime_model(model_dir)
        model_ply_path = model_dir / "model.ply"
        model_sog_path = model_dir / "model.sog"
        model_format = runtime_model.suffix.lower().lstrip(".") or "ply"

        reporter.set_status(
            status="ready",
            progress=100,
            message="模型已生成，可以在 Viewer 中查看",
            force=True,
            model_rel_path=path_to_storage_url(runtime_model),
            model_ply_rel_path=path_to_storage_url(model_ply_path) if model_ply_path.exists() else None,
            model_sog_rel_path=path_to_storage_url(model_sog_path) if model_sog_path.exists() else None,
            model_format=model_format,
            error_message=None,
            pipeline_pid=None,
            train_step=train_max_steps,
            train_total_steps=train_max_steps,
            train_eta="0s",
        )
        reporter.log_event(
            "task",
            "Pipeline task completed",
            output_model=str(runtime_model),
            output_model_size=runtime_model.stat().st_size if runtime_model.exists() else None,
            model_ply=str(model_ply_path) if model_ply_path.exists() else None,
            model_sog=str(model_sog_path) if model_sog_path.exists() else None,
            model_format=model_format,
            force=True,
        )
        return runtime_model
    except Exception as exc:
        reporter.set_status(
            status="failed",
            progress=100,
            message="流水线执行失败",
            error_message=str(exc),
            pipeline_pid=None,
            force=True,
        )
        reporter.log_event("task", "Pipeline task failed", level="ERROR", error=str(exc), force=True)
        raise


def main() -> int:
    args = parse_args()
    input_video = Path(args.input_video).resolve()
    if not input_video.exists():
        print(f"Input video not found: {input_video}")
        return 1

    try:
        output_model = run_task(
            args.task_id,
            input_video,
            mock=args.mock,
            quality_profile_name=args.quality_profile,
            train_max_steps=args.train_max_steps,
            object_masking=args.object_masking,
            resume_after_mask=args.resume_after_mask,
        )
        if output_model is None:
            print(f"Task {args.task_id} paused and is awaiting mask prompt.")
        else:
            print(f"Task {args.task_id} completed successfully.")
        return 0
    except Exception as exc:
        update_task(
            args.task_id,
            status="failed",
            progress=100,
            error_message=str(exc),
            status_message="流水线执行失败",
        )
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
