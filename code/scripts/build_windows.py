#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


def overlap(start: float, end: float, intervals: list[tuple[float, float]]) -> float:
    return sum(max(0.0, min(end, right) - max(start, left)) for left, right in intervals)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build fixed windows after split assignment.")
    parser.add_argument("--fold-manifest", type=Path, required=True)
    parser.add_argument("--pose-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--window-seconds", type=float, default=1.0)
    parser.add_argument("--stride-seconds", type=float, default=0.2)
    parser.add_argument("--timesteps", type=int, default=30)
    parser.add_argument("--positive-overlap", type=float, default=0.5)
    parser.add_argument("--exclude-after-fall", action="store_true")
    args = parser.parse_args()
    segments = pd.read_csv(args.fold_manifest, dtype={"video_id": str, "subject": str, "view": str})
    pose_index = pd.read_csv(args.pose_index, dtype={"video_id": str})
    cache_by_video = dict(zip(pose_index.video_id, pose_index.cache_path))
    rows: list[dict[str, object]] = []
    for video_id, group in segments.groupby("video_id", sort=False):
        cache_path = cache_by_video.get(str(video_id))
        if not cache_path or not Path(cache_path).exists():
            raise FileNotFoundError(f"Missing pose cache for {video_id}: {cache_path}")
        with np.load(cache_path, allow_pickle=False) as cache:
            timestamps = cache["timestamps"]
            duration = float(timestamps[-1]) if len(timestamps) else 0.0
        falls = [(float(row.start) if pd.notna(row.start) else 0.0,
                  float(row.end) if pd.notna(row.end) else duration)
                 for row in group.itertuples() if str(row.label) == "fall"]
        ignored = [(float(row.start) if pd.notna(row.start) else 0.0,
                    float(row.end) if pd.notna(row.end) else duration)
                   for row in group.itertuples() if str(row.label) == "ignore"]
        final_start = max(0.0, duration - args.window_seconds)
        for start in np.arange(0.0, final_start + 1e-8, args.stride_seconds):
            end = float(start + args.window_seconds)
            positive_fraction = overlap(float(start), end, falls) / args.window_seconds
            if 0 < positive_fraction < args.positive_overlap:
                continue
            if overlap(float(start), end, ignored) > 0:
                continue
            if args.exclude_after_fall and falls and start >= max(item[1] for item in falls):
                continue
            label = int(positive_fraction >= args.positive_overlap)
            identity = f"{video_id}|{start:.6f}|{end:.6f}"
            first = group.iloc[0]
            rows.append({
                "window_id": hashlib.sha1(identity.encode()).hexdigest()[:16],
                "cache_path": str(Path(cache_path).resolve()),
                "video_id": str(video_id), "dataset": first.dataset,
                "subject": first.subject, "view": first["view"],
                "split": first.split, "start": float(start), "end": end,
                "label": label, "timesteps": args.timesteps,
            })
    output = pd.DataFrame(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    print(f"windows={len(output)} labels={output.label.value_counts().to_dict()} "
          f"splits={output.split.value_counts().to_dict()}")


if __name__ == "__main__":
    main()
