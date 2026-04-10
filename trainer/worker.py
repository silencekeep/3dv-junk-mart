from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.task_store import UPLOADS_ROOT, list_tasks
from trainer.pipeline import default_quality_profile_name, default_train_max_steps, run_task


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Poll uploaded tasks and run the pipeline.")
    parser.add_argument("--interval", type=int, default=5, help="Polling interval in seconds.")
    parser.add_argument("--once", action="store_true", help="Process current uploaded tasks once and exit.")
    parser.add_argument("--mock", action="store_true", help="Run the development mock pipeline.")
    parser.add_argument(
        "--quality-profile",
        default=default_quality_profile_name(),
        help="Training quality profile passed to trainer.pipeline.",
    )
    parser.add_argument(
        "--train-max-steps",
        type=int,
        default=default_train_max_steps(),
        help="Maximum splatfacto training iterations.",
    )
    parser.add_argument(
        "--object-masking",
        action="store_true",
        help="Enable SAM 2 object masking. Worker tasks will pause after COLMAP until prompts are submitted.",
    )
    return parser.parse_args()


def find_input_video(task_id: str) -> Path | None:
    upload_dir = UPLOADS_ROOT / task_id
    if not upload_dir.exists():
        return None

    for candidate in upload_dir.iterdir():
        if candidate.is_file():
            return candidate

    return None


def process_uploaded_tasks(mock: bool, quality_profile: str, train_max_steps: int, object_masking: bool) -> None:
    for task in list_tasks(statuses={"uploaded"}):
        input_video = find_input_video(task["task_id"])
        if input_video is None:
            continue

        run_task(
            task["task_id"],
            input_video,
            mock=mock,
            quality_profile_name=quality_profile,
            train_max_steps=train_max_steps,
            object_masking=object_masking,
        )


def main() -> int:
    args = parse_args()

    while True:
        process_uploaded_tasks(
            mock=args.mock,
            quality_profile=args.quality_profile,
            train_max_steps=args.train_max_steps,
            object_masking=args.object_masking,
        )
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
