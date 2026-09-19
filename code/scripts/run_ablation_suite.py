#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from fallbench.config import deep_update, load_config, save_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run declared MaskedBiMamba ablations.")
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--ablations", type=Path, required=True)
    parser.add_argument("--fold-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device")
    parser.add_argument("--max-parallel", type=int, default=1)
    args = parser.parse_args()
    base = load_config(args.base_config)
    suite = load_config(args.ablations)
    root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root / "src") + os.pathsep + environment.get("PYTHONPATH", "")
    for variant, options in suite["variants"].items():
        model_options = {key: value for key, value in options.items() if key != "include_confidence"}
        data_options = ({"include_confidence": options["include_confidence"]}
                        if "include_confidence" in options else {})
        resolved = deep_update(base, {
            "experiment": {"name": f"ablation_{variant}", "models": ["masked_bimamba"],
                           "seeds": suite["experiment"]["seeds"]},
            "model": model_options, "data": data_options,
        })
        config_path = args.output_dir / "_configs" / f"{variant}.yaml"
        save_config(resolved, config_path)
        command = [sys.executable, str(root / "scripts" / "run_suite.py"),
                   "--config", str(config_path), "--fold-dir", str(args.fold_dir),
                   "--output-dir", str(args.output_dir / variant)]
        if args.device:
            command += ["--device", args.device]
        command += ["--max-parallel", str(args.max_parallel)]
        subprocess.run(command, check=True, env=environment)


if __name__ == "__main__":
    main()
