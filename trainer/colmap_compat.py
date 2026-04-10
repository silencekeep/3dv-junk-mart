from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


OPTION_REWRITES = {
    "--SiftExtraction.use_gpu": "--FeatureExtraction.use_gpu",
    "--SiftMatching.use_gpu": "--FeatureMatching.use_gpu",
}
LOG_NAME = "colmap_compat.log"


def resolve_colmap_executable() -> str:
    override = os.getenv("COLMAP_COMPAT_REAL_EXE")
    if override:
        return override

    resolved = shutil.which("colmap")
    if resolved:
        return resolved

    fallback = Path(r"D:\colmap-x64-windows-cuda\bin\colmap.exe")
    if fallback.exists():
        return str(fallback)

    raise FileNotFoundError("Could not resolve the real COLMAP executable.")


def rewrite_args(args: list[str]) -> list[str]:
    rewritten: list[str] = []
    for arg in args:
        if "=" in arg:
            option, value = arg.split("=", 1)
            rewritten.append(f"{OPTION_REWRITES.get(option, option)}={value}")
        else:
            rewritten.append(OPTION_REWRITES.get(arg, arg))
    return rewritten


def emit_diagnostic(message: str) -> None:
    line = f"{datetime.now().astimezone().isoformat(timespec='seconds')} [colmap_compat] {message}"
    print(line, file=sys.stderr, flush=True)
    try:
        with (Path.cwd() / LOG_NAME).open("a", encoding="utf-8") as file:
            file.write(f"{line}\n")
    except OSError:
        pass


def main() -> int:
    colmap_exe = resolve_colmap_executable()
    command = [colmap_exe, *rewrite_args(sys.argv[1:])]
    emit_diagnostic(f"Executing {subprocess.list2cmdline(command)}")
    completed = subprocess.run(command, check=False)
    emit_diagnostic(f"Finished returncode={completed.returncode}")
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
