from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
from pathlib import Path

import numpy as np
from PIL import Image
import torch

from trainer.sam2_masking import image_dir_for_factor, load_prompts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a single-frame SAM 2 preview overlay.")
    parser.add_argument("--dataset-dir", required=True, help="Nerfstudio dataset directory containing images.")
    parser.add_argument("--prompts", required=True, help="Path to mask_prompts.json.")
    parser.add_argument("--source-factor", type=int, default=2, help="Image pyramid factor used as SAM 2 input.")
    parser.add_argument("--model-id", default="facebook/sam2.1-hiera-small", help="SAM 2 Hugging Face model id.")
    parser.add_argument("--checkpoint", default=None, help="Optional local SAM 2 checkpoint path.")
    parser.add_argument("--model-cfg", default=None, help="Optional local SAM 2 model config path.")
    parser.add_argument("--output-preview", required=True, help="Output path for the composited preview image.")
    return parser.parse_args()


def build_predictor(args: argparse.Namespace, device: str):
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    if args.checkpoint or args.model_cfg:
        if not args.checkpoint or not args.model_cfg:
            raise RuntimeError("Both --checkpoint and --model-cfg are required when using local SAM 2 files.")
        from sam2.build_sam import build_sam2

        model = build_sam2(args.model_cfg, args.checkpoint, device=device)
        return SAM2ImagePredictor(model)

    try:
        return SAM2ImagePredictor.from_pretrained(args.model_id, device=device)
    except TypeError:
        predictor = SAM2ImagePredictor.from_pretrained(args.model_id)
        if hasattr(predictor, "model"):
            predictor.model.to(device)
        return predictor


def choose_mask(masks: np.ndarray, scores: np.ndarray) -> np.ndarray:
    if masks.ndim == 2:
        return masks.astype(bool)

    best_index = int(np.argmax(scores)) if scores.size else 0
    return masks[best_index].astype(bool)


def render_preview(image: Image.Image, mask: np.ndarray) -> Image.Image:
    base = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    tint = np.zeros_like(base)
    tint[mask, 0] = 34
    tint[mask, 1] = 197
    tint[mask, 2] = 94
    tint[mask, 3] = 110
    preview = Image.alpha_composite(Image.fromarray(base, mode="RGBA"), Image.fromarray(tint, mode="RGBA"))
    return preview.convert("RGB")


def main() -> int:
    args = parse_args()
    dataset_dir = Path(args.dataset_dir).resolve()
    prompts_path = Path(args.prompts).resolve()
    output_preview_path = Path(args.output_preview).resolve()
    prompts = load_prompts(prompts_path)

    source_dir = image_dir_for_factor(dataset_dir, args.source_factor)
    prompt_frame_name = prompts.get("prompt_frame_name")
    if not prompt_frame_name:
        raise RuntimeError("mask_prompts.json does not contain prompt_frame_name.")

    prompt_frame_path = source_dir / prompt_frame_name
    if not prompt_frame_path.exists():
        raise RuntimeError(f"Prompt frame {prompt_frame_name!r} was not found in {source_dir}")

    with Image.open(prompt_frame_path) as prompt_image:
        prompt_rgb = prompt_image.convert("RGB")
        prompt_width, prompt_height = prompt_rgb.size
        prompt_array = np.asarray(prompt_rgb).copy()

    points = np.array(
        [[float(point["x"]) * prompt_width, float(point["y"]) * prompt_height] for point in prompts["points"]],
        dtype=np.float32,
    )
    labels = np.array([int(point["label"]) for point in prompts["points"]], dtype=np.int32)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    use_bf16 = device == "cuda" and torch.cuda.is_bf16_supported()
    print(
        json.dumps(
            {
                "event": "sam2_preview_start",
                "device": device,
                "use_bf16_autocast": use_bf16,
                "model_id": args.model_id,
                "prompt_frame": prompt_frame_name,
                "prompt_points": len(points),
                "source_dir": str(source_dir),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )

    autocast_context = torch.autocast("cuda", dtype=torch.bfloat16) if use_bf16 else nullcontext()
    with torch.inference_mode(), autocast_context:
        predictor = build_predictor(args, device)
        predictor.set_image(prompt_array)
        masks, scores, _ = predictor.predict(
            point_coords=points,
            point_labels=labels,
            multimask_output=len(points) <= 1,
        )

    best_mask = choose_mask(masks, scores)
    preview_image = render_preview(prompt_rgb, best_mask)
    output_preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_image.save(output_preview_path)

    summary = {
        "event": "sam2_preview_done",
        "device": device,
        "use_bf16_autocast": use_bf16,
        "model_id": args.model_id,
        "prompt_frame_name": prompt_frame_name,
        "positive_points": int((labels == 1).sum()),
        "negative_points": int((labels == 0).sum()),
        "mask_coverage": float(best_mask.mean()),
        "output_preview": str(output_preview_path),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
