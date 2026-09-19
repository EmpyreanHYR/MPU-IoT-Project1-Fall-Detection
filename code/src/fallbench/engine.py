from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader

from .metrics import binary_metrics


def move_batch(batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
    return {key: value.to(device, non_blocking=True)
            if isinstance(value, torch.Tensor) else value
            for key, value in batch.items()}


def run_epoch(loader: DataLoader, model: nn.Module, criterion: nn.Module,
              device: torch.device, threshold: float,
              optimizer: torch.optim.Optimizer | None = None,
              scaler: torch.cuda.amp.GradScaler | None = None,
              gradient_clip_norm: float | None = None,
              collect_predictions: bool = True) -> tuple[dict[str, float | int], list[dict[str, Any]]]:
    training = optimizer is not None
    model.train(training)
    targets: list[int] = []
    probabilities: list[float] = []
    predictions: list[dict[str, Any]] = []
    total_loss = 0.0
    total_count = 0
    for batch in loader:
        batch = move_batch(batch, device)
        if training:
            optimizer.zero_grad(set_to_none=True)
        amp_enabled = scaler is not None and scaler.is_enabled()
        with torch.autocast(device_type=device.type, enabled=amp_enabled):
            logits = model(pose=batch["pose"], quality=batch["quality"])
            loss = criterion(logits, batch["label"])
        if training:
            if scaler is not None:
                scaler.scale(loss).backward()
                if gradient_clip_norm:
                    scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(model.parameters(), gradient_clip_norm)
                scaler.step(optimizer)
                scaler.update()
            else:
                loss.backward()
                if gradient_clip_norm:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), gradient_clip_norm)
                optimizer.step()
        probability = logits.softmax(dim=1)[:, 1].detach().cpu().numpy()
        label = batch["label"].detach().cpu().numpy()
        total_loss += float(loss.detach()) * len(label)
        total_count += len(label)
        targets.extend(label.tolist())
        probabilities.extend(probability.tolist())
        if collect_predictions:
            for index in range(len(label)):
                predictions.append({
                    "window_id": batch["window_id"][index],
                    "video_id": batch["video_id"][index],
                    "start": float(batch["start"][index]),
                    "end": float(batch["end"][index]),
                    "target": int(label[index]),
                    "probability": float(probability[index]),
                })
    metrics = binary_metrics(targets, probabilities, threshold)
    metrics["loss"] = total_loss / max(total_count, 1)
    return metrics, predictions


def append_history(path: Path, row: dict[str, Any]) -> None:
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def save_predictions(rows: list[dict[str, Any]], path: Path) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def aggregate_video_metrics(predictions: list[dict[str, Any]],
                            threshold: float) -> dict[str, float | int]:
    """TCNTE-compatible file metric: any positive window makes a fall file."""
    table = pd.DataFrame(predictions)
    grouped = table.groupby("video_id").agg(
        target=("target", "max"), probability=("probability", "max"))
    return binary_metrics(grouped.target.tolist(), grouped.probability.tolist(), threshold)


def _merge_intervals(intervals: list[tuple[float, float]],
                     tolerance: float = 1e-6) -> list[tuple[float, float]]:
    merged: list[list[float]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1] + tolerance:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(item[0], item[1]) for item in merged]


def event_metrics(predictions: list[dict[str, Any]],
                  threshold: float) -> dict[str, float | int]:
    """Match contiguous predicted and target intervals within each video."""
    table = pd.DataFrame(predictions)
    true_events = 0
    detected_events = 0
    false_alarms = 0
    delays: list[float] = []
    total_hours = 0.0
    for _, rows in table.groupby("video_id"):
        rows = rows.sort_values("start")
        total_hours += max(0.0, float(rows.end.max() - rows.start.min())) / 3600.0
        truth = _merge_intervals([
            (float(row.start), float(row.end)) for row in rows.itertuples()
            if int(row.target) == 1])
        predicted = _merge_intervals([
            (float(row.start), float(row.end)) for row in rows.itertuples()
            if float(row.probability) >= threshold])
        true_events += len(truth)
        used_predictions: set[int] = set()
        for true_start, true_end in truth:
            matches = [index for index, (pred_start, pred_end) in enumerate(predicted)
                       if index not in used_predictions
                       and min(true_end, pred_end) > max(true_start, pred_start)]
            if matches:
                match = matches[0]
                used_predictions.add(match)
                detected_events += 1
                delays.append(predicted[match][0] - true_start)
        false_alarms += len(predicted) - len(used_predictions)
    recall = detected_events / true_events if true_events else 0.0
    return {
        "event_recall": float(recall),
        "detected_events": detected_events,
        "total_events": true_events,
        "false_alarms": false_alarms,
        "false_alarms_per_hour": float(false_alarms / total_hours) if total_hours else 0.0,
        "mean_detection_delay_seconds": float(sum(delays) / len(delays)) if delays else float("nan"),
    }
