# FallBench: reproducible fall-detection experiments

This is the clean experiment workspace for the new study. Previous results and
run directories are intentionally excluded. The old modified project and the
downloaded TCNTE archive are reference material only.

The repository supports two explicitly separated tracks:

1. **TCNTE reproduction**: paper-aligned 12-joint input, 1 s windows, 0.2 s
   stride, 100 epochs, Adam, and weighted focal loss.
2. **Main paper protocol**: leakage-free group splits, a train-only validation
   split, three seeds, 100 epochs without early stopping, TCN/TE/TCNTE
   baselines, and the proposed quality-aware MaskedBiMamba model.

The test split is evaluated only after all 100 epochs. `best.pt` is selected by
validation F1; `last.pt` is always retained. This is checkpoint selection, not
early stopping.

## Directory layout

```text
code/
├── configs/                 # immutable experiment specifications
├── docs/                    # experiment plan and data contract
├── scripts/                 # command-line entry points
├── src/fallbench/           # datasets, models, training and evaluation
├── third_party/             # provenance notes for external implementations
├── requirements.txt
└── README.md
```

Raw videos, pose caches, weights and results must live outside the repository.
Recommended workspace layout (set `FALLGUARD_WORK_DIR` to this directory):

```text
$FALLGUARD_WORK_DIR/
├── code/
├── data/raw/
├── data/manifests/
├── data/poses/
└── outputs/
```

## Pipeline

All commands are run from the `code` directory.

```bash
export PYTHONPATH="$PWD/src"

# 1. Validate a segment manifest before expensive preprocessing.
python scripts/audit_manifest.py --manifest data/manifests/segments.csv

# 2. Extract YOLOv8-pose + BoT-SORT tracks once per video.
python scripts/extract_pose.py \
  --manifest data/manifests/segments.csv \
  --output-dir data/poses --model yolov8s-pose.pt

# 3. Create subject/video-grouped train/validation/test folds.
python scripts/make_splits.py \
  --manifest data/manifests/segments.csv \
  --output-dir data/manifests/folds --folds 4 --strategy subject

# 4. Convert segment annotations and pose tracks into fixed windows.
python scripts/build_windows.py \
  --fold-manifest data/manifests/folds/fold_0.csv \
  --pose-index data/poses/index.csv \
  --output data/manifests/fold_0_windows.csv \
  --window-seconds 1.0 --stride-seconds 0.2 --timesteps 30 \
  --positive-overlap 0.5 --exclude-after-fall

# 5. Train one fold/seed. No early stopping is implemented.
python scripts/train.py \
  --config configs/main_protocol.yaml \
  --windows data/manifests/fold_0_windows.csv \
  --model tcnte --seed 42 --output outputs/main/tcnte/fold_0/seed_42

# 6. Run the declared model/fold/seed matrix with resumable jobs.
python scripts/run_suite.py \
  --config configs/main_protocol.yaml \
  --fold-dir data/manifests/folds_windows \
  --output-dir outputs/main
```

`configs/tcnte_reproduction.yaml` records the published TCNTE settings.
`configs/main_protocol.yaml` is the primary publication protocol. Never combine
their numbers in one table without identifying the protocol.

## Dataset manifest contract

Segment manifests are UTF-8 CSV files with these columns:

```text
video_id,path,dataset,subject,view,label,start,end
```

- `path` is an absolute path or is resolved relative to `--video-root`.
- `label` uses `fall` for the dynamic fall interval. `fallen` and `lying` are
  distinct and are not silently mapped to `fall`.
- `start` and `end` are seconds. Empty values mean the full video.
- every row for one `video_id` must have the same path, dataset and subject.

See [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md) for the pose-cache and
window-manifest schemas.

## Reproducibility rules

- Split videos/subjects before making overlapping windows.
- Never tune thresholds or checkpoints on the test split.
- Keep the same folds, input representation and seeds for close baselines.
- Report every fold and seed, then mean, standard deviation and confidence
  intervals where appropriate.
- Report window-level and event/file-level metrics separately.
- Record the config file, command, package versions, GPU and git commit in every
  output directory.
- Missing results remain `TBD`; old runs are not copied into this repository.
