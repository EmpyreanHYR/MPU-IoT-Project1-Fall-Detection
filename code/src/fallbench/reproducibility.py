from __future__ import annotations

import json
import os
import platform
import random
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch


def seed_everything(seed: int, deterministic: bool = True) -> None:
    if deterministic:
        # Required by CUDA >= 10.2 for deterministic cuBLAS reductions. This
        # must be set before the first CUDA operation in the process.
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if deterministic:
        torch.use_deterministic_algorithms(True, warn_only=True)
        torch.backends.cudnn.benchmark = False
        if torch.cuda.is_available():
            # The fused attention kernels are faster but explicitly
            # nondeterministic in this PyTorch release. The small temporal
            # windows make the deterministic math kernel an acceptable cost.
            torch.backends.cuda.enable_flash_sdp(False)
            torch.backends.cuda.enable_mem_efficient_sdp(False)
            torch.backends.cuda.enable_math_sdp(True)


def worker_seed(worker_id: int) -> None:
    seed = torch.initial_seed() % (2**32)
    np.random.seed(seed + worker_id)
    random.seed(seed + worker_id)


def _git_commit(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def environment_record(project_root: Path) -> dict[str, Any]:
    gpu = None
    if torch.cuda.is_available():
        gpu = {
            "name": torch.cuda.get_device_name(0),
            "cuda_runtime": torch.version.cuda,
            "device_count": torch.cuda.device_count(),
        }
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "torch": torch.__version__,
        "gpu": gpu,
        "git_commit": _git_commit(project_root),
        "command": sys.argv,
        "cwd": os.getcwd(),
    }


def write_json(value: Any, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
