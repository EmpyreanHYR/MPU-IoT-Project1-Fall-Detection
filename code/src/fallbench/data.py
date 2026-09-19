from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset


BODY12 = np.asarray([5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16])


@lru_cache(maxsize=64)
def load_pose_cache(path: str) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def interpolate(values: np.ndarray, timestamps: np.ndarray,
                target: np.ndarray) -> np.ndarray:
    flat = values.reshape(values.shape[0], -1)
    output = np.empty((len(target), flat.shape[1]), dtype=np.float32)
    for feature in range(flat.shape[1]):
        output[:, feature] = np.interp(
            target, timestamps, flat[:, feature],
            left=flat[0, feature], right=flat[-1, feature])
    return output.reshape((len(target),) + values.shape[1:])


def normalize_xy(xy: np.ndarray, method: str) -> np.ndarray:
    result = xy.astype(np.float32, copy=True)
    if method == "per_frame_minmax":
        for axis in range(2):
            values = result[:, :, axis]
            lower = values.min(axis=1, keepdims=True)
            upper = values.max(axis=1, keepdims=True)
            result[:, :, axis] = (values - lower) / np.maximum(upper - lower, 1e-4)
        return result
    if method == "per_window_minmax":
        for axis in range(2):
            values = result[:, :, axis]
            lower, upper = values.min(), values.max()
            result[:, :, axis] = (values - lower) / max(float(upper - lower), 1e-4)
        return result
    if method == "none":
        return result
    raise ValueError(f"Unknown normalization: {method}")


class PoseWindowDataset(Dataset):
    """Load fixed windows from immutable pose caches."""

    def __init__(self, windows: str | Path | pd.DataFrame,
                 data_config: dict[str, Any], split: str,
                 corruption: str | None = None, severity: float = 0.0,
                 corruption_seed: int = 0,
                 include_metadata: bool = True) -> None:
        source_path = None if isinstance(windows, pd.DataFrame) else Path(windows).resolve()
        table = pd.read_csv(windows) if source_path is not None else windows.copy()
        required = {"cache_path", "video_id", "split", "start", "end", "label"}
        missing = required - set(table.columns)
        if missing:
            raise ValueError(f"Window manifest missing columns: {sorted(missing)}")
        self.rows = table[table["split"] == split].reset_index(drop=True)
        if self.rows.empty:
            raise ValueError(f"No rows for split={split}")
        self.timesteps = int(data_config["timesteps"])
        self.include_confidence = bool(data_config.get("include_confidence", False))
        self.normalization = str(data_config.get("normalization", "per_frame_minmax"))
        if data_config.get("joints", "body12") != "body12":
            raise ValueError("Current frozen protocols require joints=body12")
        self.joints = BODY12
        self.corruption = corruption
        self.severity = float(severity)
        self.corruption_seed = int(corruption_seed)
        self.include_metadata = bool(include_metadata)
        # Materialising each fixed window once avoids repeating pose-cache I/O,
        # interpolation and normalisation in every epoch.  The returned tensors
        # are never mutated by the trainer, so DataLoader workers can safely
        # share the precomputed samples.  This is a performance-only option:
        # values are produced by the same code path as lazy loading.
        self.preload_windows = bool(data_config.get("preload_windows", False))
        self._materialized = None
        if self.preload_windows:
            materialized_path = self._materialized_path(source_path, split)
            if materialized_path is not None and materialized_path.exists():
                self._materialized = torch.load(materialized_path, weights_only=False)
            else:
                self._materialized = [self._build_item(index) for index in range(len(self.rows))]
                if materialized_path is not None:
                    materialized_path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = materialized_path.with_suffix(
                        f".{os.getpid()}.tmp")
                    torch.save(self._materialized, temporary)
                    os.replace(temporary, materialized_path)

    def _materialized_path(self, source_path: Path | None,
                           split: str) -> Path | None:
        if source_path is None:
            return None
        signature = {
            "schema": 1,
            "manifest_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "split": split,
            "timesteps": self.timesteps,
            "include_confidence": self.include_confidence,
            "normalization": self.normalization,
            "joints": self.joints.tolist(),
            "corruption": self.corruption,
            "severity": self.severity,
            "corruption_seed": self.corruption_seed,
            "include_metadata": self.include_metadata,
        }
        digest = hashlib.sha256(
            json.dumps(signature, sort_keys=True).encode()).hexdigest()[:20]
        return source_path.parent / ".window_tensor_cache" / f"{digest}.pt"

    @property
    def labels(self) -> list[int]:
        return self.rows["label"].astype(int).tolist()

    @property
    def pose_size(self) -> int:
        return len(self.joints) * (3 if self.include_confidence else 2)

    @property
    def quality_size(self) -> int:
        return 3

    def __len__(self) -> int:
        return len(self.rows)

    def _corrupt(self, keypoints: np.ndarray, bbox: np.ndarray,
                 index: int) -> tuple[np.ndarray, np.ndarray]:
        if not self.corruption or self.severity <= 0:
            return keypoints, bbox
        keypoints = keypoints.copy()
        bbox = bbox.copy()
        rng = np.random.default_rng(self.corruption_seed + index)
        if self.corruption == "random_joint_drop":
            keypoints[rng.random(keypoints.shape[:2]) < self.severity] = 0
        elif self.corruption == "frame_drop":
            mask = rng.random(keypoints.shape[0]) < self.severity
            keypoints[mask] = 0
            bbox[mask] = 0
        elif self.corruption == "confidence_noise":
            noise = rng.normal(0, self.severity, keypoints.shape[:2])
            keypoints[:, :, 2] = np.clip(keypoints[:, :, 2] + noise, 0, 1)
        elif self.corruption == "lower_body_missing":
            keypoints[:, 6:12] = 0
        else:
            raise ValueError(f"Unknown corruption: {self.corruption}")
        return keypoints, bbox

    def _build_item(self, index: int) -> dict[str, torch.Tensor | str | float]:
        row = self.rows.iloc[index]
        cache = load_pose_cache(str(Path(row.cache_path).resolve()))
        timestamps = cache["timestamps"].astype(np.float64)
        target = np.linspace(float(row.start), float(row.end), self.timesteps,
                             endpoint=False, dtype=np.float64)
        keypoints = interpolate(cache["keypoints"], timestamps, target)[:, self.joints]
        bbox = interpolate(cache["bbox"], timestamps, target)
        keypoints, bbox = self._corrupt(keypoints, bbox, index)
        confidence = np.clip(keypoints[:, :, 2], 0, 1).astype(np.float32)
        xy = normalize_xy(keypoints[:, :, :2], self.normalization)
        pose = np.concatenate((xy, confidence[:, :, None]), axis=2) \
            if self.include_confidence else xy
        visible = (confidence >= 0.2).mean(axis=1, keepdims=True).astype(np.float32)
        quality = np.concatenate((confidence.mean(axis=1, keepdims=True),
                                  visible, bbox[:, 4:5].astype(np.float32)), axis=1)
        item: dict[str, torch.Tensor | str | float] = {
            "pose": torch.from_numpy(pose.reshape(self.timesteps, -1).astype(np.float32)),
            "quality": torch.from_numpy(quality),
            "label": torch.tensor(int(row.label), dtype=torch.long),
        }
        if self.include_metadata:
            item.update({
                "window_id": str(row.get("window_id", index)),
                "video_id": str(row.video_id),
                "start": float(row.start), "end": float(row.end),
            })
        return item

    def __getitem__(self, index: int) -> dict[str, torch.Tensor | str | float]:
        if self._materialized is not None:
            return self._materialized[index]
        return self._build_item(index)
