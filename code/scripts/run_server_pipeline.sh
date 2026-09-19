#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE="${FALLGUARD_CODE_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
WORK="${FALLGUARD_WORK_DIR:-$(cd "$CODE/.." && pwd)}"
MANIFESTS="$WORK/data/manifests"
POSES="$WORK/data/poses/real_combined"
export POSES
OUTPUTS="$WORK/outputs"
LOGS="$WORK/logs"
POSE_STATUS="$LOGS/pose_real.status"
PIPELINE_STATUS="$LOGS/experiment_pipeline.status"

mkdir -p "$MANIFESTS" "$OUTPUTS" "$LOGS"
printf 'RUNNING\n' > "$PIPELINE_STATUS"
trap 'code=$?; printf "%s\n" "$code" > "$PIPELINE_STATUS"' EXIT
cd "$CODE"
export PYTHONPATH="$CODE/src"
export OMP_NUM_THREADS=8
export CUBLAS_WORKSPACE_CONFIG=:4096:8

while [[ ! -f "$POSE_STATUS" ]]; do
  sleep 30
done
if [[ "$(tr -d '[:space:]' < "$POSE_STATUS")" != "0" ]]; then
  echo "Pose extraction failed; refusing to start formal experiments." >&2
  exit 1
fi

python3 - <<'PY'
import os
from pathlib import Path
import pandas as pd

index = Path(os.environ["POSES"]) / "index.csv"
table = pd.read_csv(index)
if len(table) != 290 or table.video_id.nunique() != 290:
    raise RuntimeError(f"Expected 290 pose caches, found rows={len(table)} unique={table.video_id.nunique()}")
missing = [path for path in table.cache_path if not Path(path).is_file()]
if missing:
    raise FileNotFoundError(f"Missing {len(missing)} pose caches; first={missing[:3]}")
print("pose index verified: 290 videos")
PY

rm -rf "$MANIFESTS/tcnte_folds" "$MANIFESTS/tcnte_windows"
python3 scripts/make_splits.py \
  --manifest "$MANIFESTS/le2i_segments.csv" \
  --output-dir "$MANIFESTS/tcnte_folds" --folds 3 --strategy video \
  --validation-fraction 0.15 --seed 2026
mkdir -p "$MANIFESTS/tcnte_windows"
for fold in "$MANIFESTS"/tcnte_folds/fold_*.csv; do
  name="$(basename "$fold" .csv)"
  python3 scripts/build_windows.py --fold-manifest "$fold" \
    --pose-index "$POSES/index.csv" \
    --output "$MANIFESTS/tcnte_windows/${name}_windows.csv" \
    --window-seconds 1.0 --stride-seconds 0.2 --timesteps 30 \
    --positive-overlap 0.5 --exclude-after-fall
done
python3 scripts/run_suite.py --config configs/tcnte_reproduction.yaml \
  --fold-dir "$MANIFESTS/tcnte_windows" \
  --output-dir "$OUTPUTS/tcnte_reproduction" --device cuda
python3 scripts/summarize_results.py --runs "$OUTPUTS/tcnte_reproduction" \
  --output-dir "$OUTPUTS/tcnte_reproduction/summary"

rm -rf "$MANIFESTS/main_folds" "$MANIFESTS/main_windows"
python3 scripts/make_splits.py \
  --manifest "$MANIFESTS/real_combined_segments.csv" \
  --output-dir "$MANIFESTS/main_folds" --folds 4 --strategy subject \
  --validation-fraction 0.20 --seed 2026
mkdir -p "$MANIFESTS/main_windows"
for fold in "$MANIFESTS"/main_folds/fold_*.csv; do
  name="$(basename "$fold" .csv)"
  python3 scripts/build_windows.py --fold-manifest "$fold" \
    --pose-index "$POSES/index.csv" \
    --output "$MANIFESTS/main_windows/${name}_windows.csv" \
    --window-seconds 1.0 --stride-seconds 0.2 --timesteps 30 \
    --positive-overlap 0.5 --exclude-after-fall
done
python3 scripts/run_suite.py --config configs/main_protocol.yaml \
  --fold-dir "$MANIFESTS/main_windows" --output-dir "$OUTPUTS/main" \
  --device cuda --max-parallel 1
python3 scripts/summarize_results.py --runs "$OUTPUTS/main" \
  --output-dir "$OUTPUTS/main/summary"

# The course deliverable only requires the reproducible main comparison and
# deployed edge-cloud system. Extended ablations/robustness are opt-in so a
# normal rerun does not schedule another 84 training jobs.
if [[ "${RUN_EXTENDED_EXPERIMENTS:-0}" != "1" ]]; then
  echo "Course-scope experiments completed. Set RUN_EXTENDED_EXPERIMENTS=1 to run ablations and robustness."
  exit 0
fi

python3 scripts/run_ablation_suite.py --base-config configs/main_protocol.yaml \
  --ablations configs/ablation_suite.yaml --fold-dir "$MANIFESTS/main_windows" \
  --output-dir "$OUTPUTS/ablations" --device cuda --max-parallel 1
python3 scripts/summarize_results.py --runs "$OUTPUTS/ablations" \
  --output-dir "$OUTPUTS/ablations/summary"

for checkpoint in "$OUTPUTS"/main/masked_bimamba/fold_*/seed_*/best.pt; do
  run_dir="$(dirname "$checkpoint")"
  fold="$(basename "$(dirname "$run_dir")")"
  seed="$(basename "$run_dir")"
  python3 scripts/evaluate_robustness.py --checkpoint "$checkpoint" \
    --windows "$MANIFESTS/main_windows/${fold}_windows.csv" \
    --output-dir "$OUTPUTS/robustness/$fold/$seed" --device cuda
done

echo "All scheduled experiments completed successfully."
