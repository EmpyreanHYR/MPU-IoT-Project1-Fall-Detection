#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import DataLoader

from fallbench.data import PoseWindowDataset
from fallbench.engine import aggregate_video_metrics, event_metrics, run_epoch
from fallbench.losses import WeightedFocalLoss
from fallbench.models import build_model
from fallbench.reproducibility import write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate one checkpoint under deterministic corruptions.")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--clean-only", action="store_true",
                        help="Evaluate only the uncorrupted test split (for external datasets).")
    args = parser.parse_args()
    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=False)
    config = checkpoint["config"]
    model = build_model(checkpoint["model_name"], checkpoint["pose_size"],
                        checkpoint["quality_size"], config["model"]).to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    criterion = WeightedFocalLoss(None, float(config["training"]["focal_gamma"]))
    threshold = float(config["evaluation"].get("threshold", 0.5))
    conditions: list[tuple[str | None, float]] = [(None, 0.0)]
    if not args.clean_only:
        for name, severities in config["evaluation"].get("robustness", {}).items():
            conditions.extend((name, float(value)) for value in severities)
    rows: list[dict[str, object]] = []
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for corruption, severity in conditions:
        dataset = PoseWindowDataset(args.windows, config["data"], "test",
                                    corruption, severity, args.seed)
        loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False,
                            num_workers=args.workers, pin_memory=device.type == "cuda")
        with torch.no_grad():
            window, predictions = run_epoch(loader, model, criterion, device, threshold)
        video = aggregate_video_metrics(predictions, threshold)
        events = event_metrics(predictions, threshold)
        row: dict[str, object] = {"condition": corruption or "clean", "severity": severity}
        row.update({f"window_{key}": value for key, value in window.items()})
        row.update({f"video_{key}": value for key, value in video.items()})
        row.update(events)
        rows.append(row)
        print(row["condition"], severity, "window_f1", window["f1"])
    pd.DataFrame(rows).to_csv(args.output_dir / "robustness.csv", index=False)
    write_json(rows, args.output_dir / "robustness.json")


if __name__ == "__main__":
    main()
