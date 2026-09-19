#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


LABELS = {
    0: "walk", 1: "fall", 2: "fallen", 3: "sit_down", 4: "sitting",
    5: "lie_down", 6: "lying", 7: "stand_up", 8: "standing",
    9: "other", 10: "kneel_down", 11: "kneeling", 12: "squat_down",
    13: "squatting", 14: "crawl", 15: "jump",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert OmniFall labels to the project contract.")
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--path-mapping", type=Path, required=True,
                        help="CSV columns: path,video_path")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset", help="Override/assign dataset name if absent")
    args = parser.parse_args()
    labels = pd.read_csv(args.labels, dtype={"path": str, "subject": str, "cam": str})
    mapping = pd.read_csv(args.path_mapping, dtype=str)
    if not {"path", "video_path"}.issubset(mapping.columns):
        raise ValueError("path mapping requires columns: path,video_path")
    required = {"path", "label", "start", "end"}
    if not required.issubset(labels.columns):
        raise ValueError(f"OmniFall labels missing: {sorted(required - set(labels.columns))}")
    merged = labels.merge(mapping[["path", "video_path"]], on="path", how="left", validate="many_to_one")
    missing = merged[merged.video_path.isna()].path.unique()
    if len(missing):
        raise ValueError(f"{len(missing)} label paths are unmapped; first values: {missing[:10].tolist()}")
    if pd.api.types.is_numeric_dtype(merged.label):
        merged["label"] = merged.label.map(LABELS)
    else:
        as_number = pd.to_numeric(merged.label, errors="coerce")
        merged.loc[as_number.notna(), "label"] = as_number[as_number.notna()].astype(int).map(LABELS)
    if merged.label.isna().any():
        raise ValueError("Unknown labels remain after OmniFall conversion")
    dataset = (merged["dataset"].astype(str) if "dataset" in merged.columns
               else pd.Series(args.dataset or "unknown", index=merged.index))
    subject = (merged["subject"].fillna("unknown").astype(str)
               if "subject" in merged.columns else pd.Series("unknown", index=merged.index))
    view = (merged["cam"].fillna("").astype(str)
            if "cam" in merged.columns else pd.Series("", index=merged.index))
    output = pd.DataFrame({
        "video_id": dataset + ":" + merged.path.astype(str),
        "path": merged.video_path.astype(str), "dataset": dataset,
        "subject": subject, "view": view, "label": merged.label,
        "start": merged.start, "end": merged.end,
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    print(f"rows={len(output)} videos={output.video_id.nunique()} datasets={output.dataset.unique().tolist()}")


if __name__ == "__main__":
    main()

