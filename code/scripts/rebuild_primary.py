#!/usr/bin/env python3
"""Recover known test folds; rebuild NEW validation folds and window manifests."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys

import pandas as pd


def assign_folds(manifest: pd.DataFrame, frozen: pd.DataFrame, seed: int,
                 validation_fraction: float) -> list[pd.DataFrame]:
    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction must be between zero and one")
    if not {"video_id", "dataset", "subject", "path", "label", "start", "end", "view"}.issubset(manifest.columns):
        raise ValueError("Input must satisfy the segment manifest contract")
    manifest = manifest.copy()
    if manifest[["video_id", "dataset", "subject"]].isna().any().any():
        raise ValueError("Missing video, dataset or subject identity")
    if manifest.subject.astype(str).str.split(":").str[-1].str.lower().isin(["unknown", "", "nan"]).any():
        raise ValueError("Primary subject folds require known subject identities")
    # Subject 1 in one dataset is independent of Subject 1 in another.
    manifest["subject"] = [s if s.startswith(d + ":") else d + ":" + s
                           for d, s in zip(manifest.dataset.astype(str), manifest.subject.astype(str))]
    if frozen.video_id.duplicated().any():
        raise ValueError("Duplicate frozen video assignment")
    actual, expected = set(manifest.video_id), set(frozen.video_id)
    if actual != expected:
        raise ValueError(f"Video identity mismatch: missing={len(expected-actual)}, extra={len(actual-expected)}")
    for key in ("dataset", "subject", "path"):
        if (manifest.groupby("video_id")[key].nunique() != 1).any():
            raise ValueError(f"Inconsistent {key} for one video")
    assignment = frozen.set_index("video_id").test_fold
    manifest["test_fold"] = manifest.video_id.map(assignment)
    if (manifest.groupby("subject").test_fold.nunique() != 1).any():
        raise ValueError("A subject crosses recovered test folds")
    fold_ids = sorted(frozen.test_fold.unique())
    if fold_ids != [0, 1, 2, 3]:
        raise ValueError("Expected recovered test folds 0 through 3")
    output = []
    for fold in fold_ids:
        table = manifest.drop(columns="test_fold").copy()
        table["fold"] = int(fold)
        table["split"] = "train"
        table.loc[manifest.test_fold == fold, "split"] = "test"
        # Validation is rebuilt separately within each dataset. This is a new
        # protocol; it must not be represented as the original validation split.
        for _, group in manifest.loc[manifest.test_fold != fold].groupby("dataset"):
            subjects = sorted(set(group.subject))
            if len(subjects) < 2:
                raise ValueError("Need at least two remaining subjects per dataset")
            random.Random(seed + int(fold)).shuffle(subjects)
            count = min(len(subjects)-1, max(1, round(len(subjects)*validation_fraction)))
            table.loc[table.subject.isin(subjects[:count]), "split"] = "val"
        if (table.groupby("subject").split.nunique() != 1).any():
            raise AssertionError("Subject leakage")
        output.append(table)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--pose-index", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--test-folds", type=Path,
                        default=Path(__file__).resolve().parents[2]/"datasets/primary_test_folds.csv")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error("Use a new or empty output directory to preserve frozen artifacts")
    manifest = pd.read_csv(args.manifest, dtype={"video_id": str, "dataset": str, "subject": str})
    frozen = pd.read_csv(args.test_folds, dtype={"video_id": str})
    folds = assign_folds(manifest, frozen, args.seed, args.validation_fraction)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metadata = {"protocol": "rebuilt-validation-v1", "original_test_folds": True,
                "original_validation_folds": False, "seed": args.seed,
                "validation_fraction": args.validation_fraction,
                "input_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for name, path in [("manifest",args.manifest),("pose_index",args.pose_index),
                                       ("test_folds",args.test_folds)]}}
    (args.output_dir/"REBUILT.json").write_text(json.dumps(metadata, indent=2)+"\n")
    for fold, table in enumerate(folds):
        manifest_path = args.output_dir/f"fold_{fold}.csv"
        table.to_csv(manifest_path, index=False)
        subprocess.run([sys.executable, str(Path(__file__).with_name("build_windows.py")),
            "--fold-manifest", str(manifest_path), "--pose-index", str(args.pose_index),
            "--output", str(args.output_dir/f"fold_{fold}_windows.csv"),
            "--window-seconds", "1", "--stride-seconds", "0.2", "--timesteps", "30",
            "--positive-overlap", "0.5", "--exclude-after-fall"], check=True)


if __name__ == "__main__":
    main()
