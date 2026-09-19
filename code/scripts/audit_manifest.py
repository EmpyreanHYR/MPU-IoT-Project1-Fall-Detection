#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


REQUIRED = ["video_id", "path", "dataset", "subject", "view", "label", "start", "end"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a fall segment manifest.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--video-root", type=Path)
    args = parser.parse_args()
    table = pd.read_csv(args.manifest, dtype={"video_id": str, "subject": str, "view": str})
    missing = set(REQUIRED) - set(table.columns)
    if missing:
        raise SystemExit(f"Missing required columns: {sorted(missing)}")
    if table["video_id"].isna().any() or table["path"].isna().any():
        raise SystemExit("video_id and path cannot be empty")
    problems: list[str] = []
    missing_files: list[str] = []
    for video_id, rows in table.groupby("video_id", sort=False):
        for column in ("path", "dataset", "subject"):
            if rows[column].astype(str).nunique(dropna=False) != 1:
                problems.append(f"{video_id}: inconsistent {column}")
        intervals = rows.dropna(subset=["start", "end"]).sort_values("start")
        if (intervals["start"] < 0).any() or (intervals["end"] <= intervals["start"]).any():
            problems.append(f"{video_id}: invalid interval")
        source = Path(str(rows.iloc[0]["path"]))
        if not source.is_absolute() and args.video_root:
            source = args.video_root / source
        if not source.exists():
            missing_files.append(str(source))
    print(f"rows={len(table)} videos={table.video_id.nunique()} datasets={table.dataset.nunique()}")
    print("labels=" + str(table.label.value_counts(dropna=False).to_dict()))
    print(f"missing_files={len(missing_files)} structural_problems={len(problems)}")
    for message in problems[:50]:
        print("ERROR", message)
    for path in missing_files[:50]:
        print("MISSING", path)
    if problems or missing_files:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

