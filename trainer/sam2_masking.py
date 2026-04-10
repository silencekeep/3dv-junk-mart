from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
import torch

from shared.task_store import path_to_storage_url


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate per-frame object masks with SAM 2.")
    parser.add_argument("--dataset-dir", required=True, help="Nerfstudio dataset directory containing images.")
    parser.add_argument("--prompts", required=True, help="Path to mask_prompts.json.")
    parser.add_argument("--source-factor", type=int, default=2, help="Image pyramid factor used as SAM 2 input.")
    parser.add_argument("--num-downscales", type=int, default=2, help="Number of nerfstudio image downscale levels.")
    parser.add_argument("--model-id", default="facebook/sam2.1-hiera-small", help="SAM 2 Hugging Face model id.")
    parser.add_argument("--checkpoint", default=None, help="Optional local SAM 2 checkpoint path.")
    parser.add_argument("--model-cfg", default=None, help="Optional local SAM 2 model config path.")
    parser.add_argument("--preview-output-dir", default=None, help="Optional directory to save per-frame preview overlays.")
    parser.add_argument("--preview-manifest", default=None, help="Optional JSON manifest path for preview overlays.")
    return parser.parse_args()


def image_dir_for_factor(dataset_dir: Path, factor: int) -> Path:
    return dataset_dir / ("images" if factor == 1 else f"images_{factor}")


def sorted_image_paths(image_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
    )


def load_prompts(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    points = payload.get("points") or []
    if not points:
        raise RuntimeError("mask_prompts.json does not contain any points.")
    if not any(int(point.get("label", 0)) == 1 for point in points):
        raise RuntimeError("mask_prompts.json must contain at least one positive point.")
    return payload


def prepare_video_frames(source_paths: list[Path], output_dir: Path) -> None:
    expected_names = [f"{index:05d}.jpg" for index in range(len(source_paths))]
    if output_dir.exists():
        existing_paths = sorted(path for path in output_dir.iterdir() if path.is_file() and path.suffix.lower() == ".jpg")
        if [path.name for path in existing_paths] == expected_names:
            return
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for index, source_path in enumerate(source_paths):
        with Image.open(source_path) as image:
            image.convert("RGB").save(output_dir / f"{index:05d}.jpg", quality=95)


def build_predictor(args: argparse.Namespace, device: str):
    if args.checkpoint or args.model_cfg:
        if not args.checkpoint or not args.model_cfg:
            raise RuntimeError("Both --checkpoint and --model-cfg are required when using local SAM 2 files.")
        from sam2.build_sam import build_sam2_video_predictor

        return build_sam2_video_predictor(args.model_cfg, args.checkpoint, device=device)

    from sam2.sam2_video_predictor import SAM2VideoPredictor

    try:
        return SAM2VideoPredictor.from_pretrained(args.model_id, device=device)
    except TypeError:
        predictor = SAM2VideoPredictor.from_pretrained(args.model_id)
        if hasattr(predictor, "model"):
            predictor.model.to(device)
        return predictor


def init_video_state(predictor, video_dir: Path):
    try:
        return predictor.init_state(video_path=str(video_dir))
    except TypeError:
        return predictor.init_state(str(video_dir))


def add_prompt(predictor, state, frame_index: int, points: np.ndarray, labels: np.ndarray):
    try:
        return predictor.add_new_points_or_box(
            inference_state=state,
            frame_idx=frame_index,
            obj_id=1,
            points=points,
            labels=labels,
        )
    except AttributeError:
        return predictor.add_new_points(
            inference_state=state,
            frame_idx=frame_index,
            obj_id=1,
            points=points,
            labels=labels,
        )


def mask_from_logits(mask_logits) -> np.ndarray:
    mask = (mask_logits[0] > 0.0).detach().cpu().numpy()
    return np.squeeze(mask).astype(bool)


def save_mask_pyramid(
    dataset_dir: Path,
    frame_names: list[str],
    masks_by_index: dict[int, np.ndarray],
    num_downscales: int,
) -> list[float]:
    factors = [2**index for index in range(num_downscales + 1)]
    coverages: list[float] = []

    for factor in factors:
        output_dir = dataset_dir / ("masks" if factor == 1 else f"masks_{factor}")
        output_dir.mkdir(parents=True, exist_ok=True)

    for index, frame_name in enumerate(frame_names):
        mask = masks_by_index.get(index)
        if mask is None:
            raise RuntimeError(f"SAM 2 did not produce a mask for frame index {index} ({frame_name}).")
        coverages.append(float(mask.mean()))
        mask_image = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")

        for factor in factors:
            reference_dir = image_dir_for_factor(dataset_dir, factor)
            reference_path = reference_dir / frame_name
            if not reference_path.exists():
                continue
            output_dir = dataset_dir / ("masks" if factor == 1 else f"masks_{factor}")
            with Image.open(reference_path) as reference_image:
                target_size = reference_image.size
            output_image = mask_image
            if output_image.size != target_size:
                output_image = mask_image.resize(target_size, Image.Resampling.NEAREST)
            output_image.save(output_dir / frame_name)

    return coverages


def render_preview(image: Image.Image, mask: np.ndarray) -> Image.Image:
    base = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    tint = np.zeros_like(base)
    tint[mask, 0] = 34
    tint[mask, 1] = 197
    tint[mask, 2] = 94
    tint[mask, 3] = 110
    preview = Image.alpha_composite(Image.fromarray(base, mode="RGBA"), Image.fromarray(tint, mode="RGBA"))
    return preview.convert("RGB")


def storage_url_with_version(path: Path) -> str | None:
    rel_url = path_to_storage_url(path)
    if not rel_url:
        return None
    try:
        stat = path.stat()
    except OSError:
        return rel_url
    return f"{rel_url}?v={stat.st_mtime_ns}_{stat.st_size}"


def save_preview_outputs(
    source_paths: list[Path],
    frame_names: list[str],
    masks_by_index: dict[int, np.ndarray],
    output_dir: Path,
    manifest_path: Path | None,
    *,
    source_factor: int,
    prompt_frame_name: str,
    raw_preview_dir: Path | None,
) -> dict[str, Any]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    frames_payload: list[dict[str, Any]] = []
    frame_width = 0
    frame_height = 0

    for index, source_path in enumerate(source_paths):
        mask = masks_by_index.get(index)
        if mask is None:
            raise RuntimeError(f"SAM 2 did not produce a preview mask for frame index {index} ({frame_names[index]}).")

        with Image.open(source_path) as source_image:
            preview_image = render_preview(source_image.convert("RGB"), mask)
            if index == 0:
                frame_width, frame_height = preview_image.size
            output_path = output_dir / f"{source_path.stem}.jpg"
            preview_image.save(output_path, quality=88)

        raw_preview_url = path_to_storage_url(source_path)
        if raw_preview_dir is not None:
            raw_preview_path = raw_preview_dir / f"{index:05d}.jpg"
            if raw_preview_path.exists():
                raw_preview_url = storage_url_with_version(raw_preview_path)

        frames_payload.append(
            {
                "index": index,
                "name": frame_names[index],
                "image_rel_url": raw_preview_url,
                "preview_rel_url": storage_url_with_version(output_path),
                "mask_coverage": float(mask.mean()),
            }
        )

    manifest = {
        "source_factor": source_factor,
        "frame_count": len(frame_names),
        "prompt_frame_name": prompt_frame_name,
        "prompt_frame_index": frame_names.index(prompt_frame_name),
        "frame_width": frame_width,
        "frame_height": frame_height,
        "frames": frames_payload,
    }
    if manifest_path is not None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    args = parse_args()
    dataset_dir = Path(args.dataset_dir).resolve()
    prompts_path = Path(args.prompts).resolve()
    preview_output_dir = Path(args.preview_output_dir).resolve() if args.preview_output_dir else None
    preview_manifest_path = Path(args.preview_manifest).resolve() if args.preview_manifest else None
    if (preview_output_dir is None) != (preview_manifest_path is None):
        raise RuntimeError("--preview-output-dir and --preview-manifest must be provided together.")
    source_dir = image_dir_for_factor(dataset_dir, args.source_factor)
    if not source_dir.exists():
        raise RuntimeError(f"SAM 2 source image directory does not exist: {source_dir}")

    prompts = load_prompts(prompts_path)
    source_paths = sorted_image_paths(source_dir)
    frame_names = [path.name for path in source_paths]
    if not frame_names:
        raise RuntimeError(f"No images found in {source_dir}")

    prompt_frame_name = prompts.get("prompt_frame_name")
    if prompt_frame_name not in frame_names:
        raise RuntimeError(f"Prompt frame {prompt_frame_name!r} was not found in {source_dir}")
    prompt_frame_index = frame_names.index(prompt_frame_name)

    prompt_frame_path = source_dir / prompt_frame_name
    with Image.open(prompt_frame_path) as prompt_image:
        prompt_width, prompt_height = prompt_image.size

    points = np.array(
        [[float(point["x"]) * prompt_width, float(point["y"]) * prompt_height] for point in prompts["points"]],
        dtype=np.float32,
    )
    labels = np.array([int(point["label"]) for point in prompts["points"]], dtype=np.int32)

    video_dir = dataset_dir / "_sam2_video_frames"
    prepare_video_frames(source_paths, video_dir)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    use_bf16 = device == "cuda" and torch.cuda.is_bf16_supported()
    print(
        json.dumps(
            {
                "event": "sam2_start",
                "device": device,
                "use_bf16_autocast": use_bf16,
                "model_id": args.model_id,
                "source_dir": str(source_dir),
                "frames": len(frame_names),
                "prompt_frame": prompt_frame_name,
                "prompt_points": len(points),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )

    autocast_context = torch.autocast("cuda", dtype=torch.bfloat16) if use_bf16 else nullcontext()
    masks_by_index: dict[int, np.ndarray] = {}
    with torch.inference_mode(), autocast_context:
        predictor = build_predictor(args, device)
        state = init_video_state(predictor, video_dir)
        prompt_output = add_prompt(predictor, state, prompt_frame_index, points, labels)
        if isinstance(prompt_output, tuple) and len(prompt_output) >= 3:
            masks_by_index[prompt_frame_index] = mask_from_logits(prompt_output[2])

        progress_interval = max(len(frame_names) // 10, 1)
        for out_frame_index, _out_obj_ids, out_mask_logits in predictor.propagate_in_video(state):
            masks_by_index[int(out_frame_index)] = mask_from_logits(out_mask_logits)
            processed = len(masks_by_index)
            if processed == len(frame_names) or processed % progress_interval == 0:
                print(
                    json.dumps(
                        {
                            "event": "sam2_progress",
                            "processed_frames": processed,
                            "total_frames": len(frame_names),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    flush=True,
                )

    coverages = save_mask_pyramid(dataset_dir, frame_names, masks_by_index, args.num_downscales)
    preview_manifest = None
    if preview_output_dir is not None and preview_manifest_path is not None:
        preview_manifest = save_preview_outputs(
            source_paths,
            frame_names,
            masks_by_index,
            preview_output_dir,
            preview_manifest_path,
            source_factor=args.source_factor,
            prompt_frame_name=prompt_frame_name,
            raw_preview_dir=video_dir,
        )

    summary = {
        "model_id": args.model_id,
        "checkpoint": args.checkpoint,
        "model_cfg": args.model_cfg,
        "device": device,
        "use_bf16_autocast": use_bf16,
        "source_factor": args.source_factor,
        "source_dir": str(source_dir),
        "frame_count": len(frame_names),
        "mask_count": len(masks_by_index),
        "prompt_frame_name": prompt_frame_name,
        "positive_points": int((labels == 1).sum()),
        "negative_points": int((labels == 0).sum()),
        "average_mask_coverage": sum(coverages) / max(len(coverages), 1),
        "min_mask_coverage": min(coverages) if coverages else None,
        "max_mask_coverage": max(coverages) if coverages else None,
        "preview_output_dir": str(preview_output_dir) if preview_output_dir else None,
        "preview_manifest_path": str(preview_manifest_path) if preview_manifest_path else None,
    }
    if preview_manifest is not None:
        summary["preview_frame_count"] = int(preview_manifest["frame_count"])
    summary_path = dataset_dir / "mask_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"event": "sam2_done", **summary}, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
