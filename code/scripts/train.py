#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from fallbench.config import load_config, save_config
from fallbench.data import PoseWindowDataset
from fallbench.engine import (aggregate_video_metrics, append_history,
                              event_metrics, run_epoch, save_predictions)
from fallbench.losses import WeightedFocalLoss, class_weights
from fallbench.models import build_model
from fallbench.reproducibility import (environment_record, seed_everything,
                                       worker_seed, write_json)


def make_loader(dataset: PoseWindowDataset, batch_size: int, workers: int,
                shuffle: bool, seed: int, pin_memory: bool) -> DataLoader:
    generator = torch.Generator().manual_seed(seed)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle,
                      num_workers=workers, pin_memory=pin_memory,
                      worker_init_fn=worker_seed, generator=generator,
                      persistent_workers=workers > 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train one frozen fold and seed for 100 full epochs.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--model", choices=("tcn", "te", "tcnte", "unimamba", "masked_bimamba"), required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device")
    args = parser.parse_args()
    config = load_config(args.config)
    if config["training"].get("early_stopping") is not False:
        raise ValueError("The frozen protocol requires early_stopping: false")
    args.output.mkdir(parents=True, exist_ok=True)
    # This trainer does not implement checkpoint resume. If a previous process
    # stopped before metrics.json was committed, restart the run cleanly so a
    # stale history is never mixed with a new 100-epoch trajectory.
    if not (args.output / "metrics.json").exists():
        for name in ("history.csv", "best.pt", "last.pt", "test_predictions.csv",
                     "resolved_config.yaml", "environment.json"):
            (args.output / name).unlink(missing_ok=True)
    seed_everything(args.seed, bool(config["training"].get("deterministic", True)))
    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    datasets = {split: PoseWindowDataset(
                    args.windows, config["data"], split,
                    include_metadata=split == "test")
                for split in ("train", "val", "test")}
    training = config["training"]
    loaders = {
        split: make_loader(dataset, int(training["batch_size"]),
                           int(training["workers"]), split == "train",
                           args.seed, device.type == "cuda")
        for split, dataset in datasets.items()
    }
    model = build_model(args.model, datasets["train"].pose_size,
                        datasets["train"].quality_size, config["model"]).to(device)
    weights = class_weights(datasets["train"].labels, training["class_weights"]).to(device)
    criterion = WeightedFocalLoss(weights, float(training["focal_gamma"]))
    optimizer_name = str(training["optimizer"]).lower()
    optimizer_type = {"adam": torch.optim.Adam, "adamw": torch.optim.AdamW}.get(optimizer_name)
    if optimizer_type is None:
        raise ValueError(f"Unsupported optimizer: {optimizer_name}")
    optimizer = optimizer_type(model.parameters(), lr=float(training["learning_rate"]),
                               weight_decay=float(training["weight_decay"]))
    amp_enabled = bool(training.get("amp", True)) and device.type == "cuda"
    scaler = torch.cuda.amp.GradScaler(enabled=amp_enabled)
    threshold = float(config["evaluation"].get("threshold", 0.5))
    resolved = dict(config)
    resolved["run"] = {"model": args.model, "seed": args.seed,
                       "windows": str(args.windows.resolve()), "device": str(device)}
    save_config(resolved, args.output / "resolved_config.yaml")
    project_root = Path(__file__).resolve().parents[1]
    write_json(environment_record(project_root), args.output / "environment.json")
    best_f1 = float("-inf")
    epochs = int(training["epochs"])
    history_path = args.output / "history.csv"
    for epoch in range(1, epochs + 1):
        train_metrics, _ = run_epoch(
            loaders["train"], model, criterion, device, threshold,
            optimizer=optimizer, scaler=scaler,
            gradient_clip_norm=training.get("gradient_clip_norm"),
            collect_predictions=False)
        with torch.no_grad():
            val_metrics, _ = run_epoch(
                loaders["val"], model, criterion, device, threshold,
                collect_predictions=False)
        row = {"epoch": epoch}
        row.update({f"train_{key}": value for key, value in train_metrics.items()})
        row.update({f"val_{key}": value for key, value in val_metrics.items()})
        append_history(history_path, row)
        checkpoint = {
            "model_state": model.state_dict(), "model_name": args.model,
            "pose_size": datasets["train"].pose_size,
            "quality_size": datasets["train"].quality_size,
            "config": config, "seed": args.seed, "epoch": epoch,
            "validation_metrics": val_metrics,
        }
        torch.save(checkpoint, args.output / "last.pt")
        if float(val_metrics["f1"]) > best_f1:
            best_f1 = float(val_metrics["f1"])
            torch.save(checkpoint, args.output / "best.pt")
        print(f"epoch={epoch:03d}/{epochs} train_loss={train_metrics['loss']:.5f} "
              f"val_loss={val_metrics['loss']:.5f} val_f1={val_metrics['f1']:.5f}")
    best = torch.load(args.output / "best.pt", map_location=device, weights_only=False)
    model.load_state_dict(best["model_state"])
    with torch.no_grad():
        test_metrics, predictions = run_epoch(
            loaders["test"], model, criterion, device, threshold)
    video_metrics = aggregate_video_metrics(predictions, threshold)
    events = event_metrics(predictions, threshold)
    save_predictions(predictions, args.output / "test_predictions.csv")
    write_json({"best_epoch": best["epoch"], "window": test_metrics,
                "video": video_metrics, "event": events}, args.output / "metrics.json")
    print(f"test_window_f1={test_metrics['f1']:.5f} test_video_f1={video_metrics['f1']:.5f}")


if __name__ == "__main__":
    main()
