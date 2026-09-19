#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE="${FALLGUARD_CODE_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
WORK="${FALLGUARD_WORK_DIR:-$(cd "$CODE/.." && pwd)}"
MANIFESTS="$WORK/data/manifests"
OUTPUTS="$WORK/outputs"
export OUTPUTS
LOGS="$WORK/logs/gmdcsa24_gpu"
MAIN="$OUTPUTS/gmdcsa24_main_v1"
ABLATIONS="$OUTPUTS/gmdcsa24_ablations_v1"
ROBUSTNESS="$OUTPUTS/gmdcsa24_robustness_v1"
EXTERNAL="$OUTPUTS/gmdcsa24_external_le2i_v1"
STATUS="$LOGS/extended_pipeline.status"

mkdir -p "$LOGS" "$OUTPUTS"
printf 'WAITING_MAIN\n' > "$STATUS"
trap 'code=$?; if [[ $code -ne 0 ]]; then printf "FAILED:%s\n" "$code" > "$STATUS"; fi' EXIT

cd "$CODE"
export PYTHONPATH="$CODE/src"
export OMP_NUM_THREADS=2
export CUBLAS_WORKSPACE_CONFIG=:4096:8

main_pid="$(cat "$LOGS/main_suite.pid")"
while kill -0 "$main_pid" 2>/dev/null; do
  sleep 60
done

main_count="$(find "$MAIN" -name metrics.json | wc -l | tr -d ' ')"
if [[ "$main_count" != 60 ]]; then
  echo "Expected 60 main metrics, found $main_count" >&2
  exit 1
fi
python scripts/summarize_results.py --runs "$MAIN" --output-dir "$MAIN/summary"

printf 'RUNNING_ABLATIONS\n' > "$STATUS"
python scripts/run_ablation_suite.py --base-config configs/main_protocol.yaml \
  --ablations configs/ablation_suite.yaml \
  --fold-dir "$MANIFESTS/caucafall_gmdcsa24_windows" \
  --output-dir "$ABLATIONS" --device cuda --max-parallel 1

ablation_count="$(find "$ABLATIONS" -name metrics.json | wc -l | tr -d ' ')"
if [[ "$ablation_count" != 40 ]]; then
  echo "Expected 40 ablation metrics, found $ablation_count" >&2
  exit 1
fi
python scripts/summarize_results.py --runs "$ABLATIONS" --output-dir "$ABLATIONS/summary"

printf 'RUNNING_ROBUSTNESS\n' > "$STATUS"
for model in tcnte masked_bimamba; do
  for checkpoint in "$MAIN/$model"/fold_*/seed_*/best.pt; do
    run_dir="$(dirname "$checkpoint")"
    fold="$(basename "$(dirname "$run_dir")")"
    seed="$(basename "$run_dir")"
    destination="$ROBUSTNESS/$model/$fold/$seed"
    if [[ ! -f "$destination/robustness.json" ]]; then
      python scripts/evaluate_robustness.py --checkpoint "$checkpoint" \
        --windows "$MANIFESTS/caucafall_gmdcsa24_windows/${fold}_windows.csv" \
        --output-dir "$destination" --device cuda
    fi
  done
done

printf 'RUNNING_EXTERNAL_LE2I\n' > "$STATUS"
for model in tcnte masked_bimamba; do
  for checkpoint in "$MAIN/$model"/fold_*/seed_*/best.pt; do
    run_dir="$(dirname "$checkpoint")"
    fold="$(basename "$(dirname "$run_dir")")"
    seed="$(basename "$run_dir")"
    destination="$EXTERNAL/$model/$fold/$seed"
    if [[ ! -f "$destination/robustness.json" ]]; then
      python scripts/evaluate_robustness.py --checkpoint "$checkpoint" \
        --windows "$MANIFESTS/le2i_external_windows.csv" \
        --output-dir "$destination" --device cuda
    fi
  done
done

python - <<'PY'
import os
from pathlib import Path
import pandas as pd

work = Path(os.environ["OUTPUTS"])
for name in ("gmdcsa24_robustness_v1", "gmdcsa24_external_le2i_v1"):
    root = work / name
    rows = []
    for path in sorted(root.glob("*/*/*/robustness.csv")):
        model, fold, seed = path.relative_to(root).parts[:3]
        table = pd.read_csv(path)
        table.insert(0, "seed", seed)
        table.insert(0, "fold", fold)
        table.insert(0, "model", model)
        rows.append(table)
    if not rows:
        raise FileNotFoundError(f"No robustness results under {root}")
    result = pd.concat(rows, ignore_index=True)
    result.to_csv(root / "all_runs.csv", index=False)
    numeric = [column for column in result.columns if result[column].dtype.kind in "fi"]
    result.groupby(["model", "condition", "severity"])[numeric].agg(
        ["mean", "std", "count"]
    ).to_csv(root / "summary.csv")
PY

printf 'COMPLETE\n' > "$STATUS"
echo "GMDCSA24 main, ablation, robustness and external Le2i experiments completed."
