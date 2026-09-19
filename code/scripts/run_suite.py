#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections import deque
from pathlib import Path

from fallbench.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a resumable model/fold/seed matrix.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--fold-dir", type=Path, required=True,
                        help="Directory containing fold_*_windows.csv files")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--models", nargs="+")
    parser.add_argument("--seeds", nargs="+", type=int)
    parser.add_argument("--device")
    parser.add_argument("--max-parallel", type=int, default=1,
                        help="Maximum concurrent training processes (default: 1)")
    args = parser.parse_args()
    if args.max_parallel < 1:
        parser.error("--max-parallel must be at least 1")
    config = load_config(args.config)
    models = args.models or config["experiment"]["models"]
    seeds = args.seeds or config["experiment"]["seeds"]
    folds = sorted(args.fold_dir.glob("fold_*_windows.csv"))
    if not folds:
        raise FileNotFoundError(f"No fold_*_windows.csv files in {args.fold_dir}")
    root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    source_path = str(root / "src")
    environment["PYTHONPATH"] = source_path + os.pathsep + environment.get("PYTHONPATH", "")
    train_script = root / "scripts" / "train.py"
    commands: list[tuple[list[str], Path]] = []
    for model in models:
        for fold_path in folds:
            fold_name = fold_path.stem.replace("_windows", "")
            for seed in seeds:
                output = args.output_dir / str(model) / fold_name / f"seed_{seed}"
                metrics = output / "metrics.json"
                if metrics.exists():
                    print(f"skip completed: {metrics}")
                    continue
                command = [sys.executable, str(train_script), "--config", str(args.config),
                           "--windows", str(fold_path), "--model", str(model),
                           "--seed", str(seed), "--output", str(output)]
                if args.device:
                    command += ["--device", args.device]
                commands.append((command, output))

    pending = deque(commands)
    active: list[tuple[subprocess.Popen, object, Path]] = []
    try:
        while pending or active:
            while pending and len(active) < args.max_parallel:
                command, output = pending.popleft()
                output.mkdir(parents=True, exist_ok=True)
                log_handle = (output / "train.log").open("a", buffering=1)
                print("run", " ".join(command), flush=True)
                process = subprocess.Popen(
                    command, env=environment, stdout=log_handle,
                    stderr=subprocess.STDOUT,
                )
                active.append((process, log_handle, output))

            process, log_handle, output = active.pop(0)
            return_code = process.wait()
            log_handle.close()
            if return_code != 0:
                for other, other_log, _ in active:
                    other.terminate()
                    other_log.close()
                raise subprocess.CalledProcessError(return_code, process.args)
            print(f"completed: {output / 'metrics.json'}", flush=True)
    except BaseException:
        for process, log_handle, _ in active:
            if process.poll() is None:
                process.terminate()
            log_handle.close()
        raise


if __name__ == "__main__":
    main()
