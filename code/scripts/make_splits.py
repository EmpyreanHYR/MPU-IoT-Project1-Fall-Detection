#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit, KFold, StratifiedKFold


def main() -> None:
    parser = argparse.ArgumentParser(description="Create frozen group-disjoint folds.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--strategy", choices=("subject", "video"), default="subject")
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    table = pd.read_csv(args.manifest, dtype={"video_id": str, "subject": str, "view": str})
    group_column = "subject" if args.strategy == "subject" else "video_id"
    groups = table.groupby(group_column, dropna=False).agg(
        has_fall=("label", lambda values: int((values == "fall").any()))).reset_index()
    if len(groups) < args.folds:
        raise ValueError(f"Need at least {args.folds} groups, found {len(groups)}")
    if groups.has_fall.nunique() > 1 and groups.has_fall.value_counts().min() >= args.folds:
        splitter = StratifiedKFold(args.folds, shuffle=True, random_state=args.seed)
        test_splits = splitter.split(groups, groups.has_fall)
    else:
        splitter = KFold(args.folds, shuffle=True, random_state=args.seed)
        test_splits = splitter.split(groups)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for fold, (_, test_index) in enumerate(test_splits):
        test_groups = set(groups.iloc[test_index][group_column].astype(str))
        remaining = groups[~groups[group_column].astype(str).isin(test_groups)]
        validation_size = max(1, round(len(remaining) * args.validation_fraction))
        validation_size = min(validation_size, len(remaining) - 1)
        group_split = GroupShuffleSplit(
            n_splits=1, test_size=validation_size, random_state=args.seed + fold)
        train_index, val_index = next(group_split.split(
            remaining, groups=remaining[group_column]))
        train_groups = set(remaining.iloc[train_index][group_column].astype(str))
        val_groups = set(remaining.iloc[val_index][group_column].astype(str))
        output = table.copy()
        values = output[group_column].astype(str)
        output["fold"] = fold
        output["split"] = "train"
        output.loc[values.isin(val_groups), "split"] = "val"
        output.loc[values.isin(test_groups), "split"] = "test"
        if not set(output.loc[values.isin(train_groups), "split"]) == {"train"}:
            raise AssertionError("Training group assignment failed")
        output.to_csv(args.output_dir / f"fold_{fold}.csv", index=False)
        print(f"fold={fold} train_groups={len(train_groups)} val_groups={len(val_groups)} "
              f"test_groups={len(test_groups)}")


if __name__ == "__main__":
    main()
