#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize completed fold/seed metrics without inventing missing runs.")
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows: list[dict[str, object]] = []
    for path in sorted(args.runs.glob("**/metrics.json")):
        relative = path.relative_to(args.runs).parts
        with path.open("r", encoding="utf-8") as handle:
            metrics = json.load(handle)
        row: dict[str, object] = {"run": str(path.parent.relative_to(args.runs))}
        if len(relative) >= 5:
            row.update({"variant": relative[0], "model": relative[1],
                        "fold": relative[2], "seed": relative[3]})
        elif len(relative) >= 4:
            row.update({"model": relative[0], "fold": relative[1], "seed": relative[2]})
        for level in ("window", "video", "event"):
            row.update({f"{level}_{key}": value for key, value in metrics[level].items()})
        row["best_epoch"] = metrics["best_epoch"]
        rows.append(row)
    if not rows:
        raise FileNotFoundError(f"No metrics.json files under {args.runs}")
    table = pd.DataFrame(rows)
    numeric = [column for column in table.columns
               if column.startswith(("window_", "video_", "event_")) and table[column].dtype.kind in "fi"]
    grouping = [column for column in ("variant", "model") if column in table]
    summary = table.groupby(grouping)[numeric].agg(["mean", "std", "count"]) if grouping else table[numeric].agg(["mean", "std", "count"])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output_dir / "all_runs.csv", index=False)
    summary.to_csv(args.output_dir / "summary.csv")
    print(summary.to_string())


if __name__ == "__main__":
    main()
