# GMDCSA-24 GPU experiment run

Status recorded on 2026-09-17 (Asia/Shanghai). This file records the frozen
execution contract and artifact locations; it is not a result table.

## Frozen inputs

- Primary data: 100 CAUCAFall videos plus 160 GMDCSA-24 videos.
- External data: 190 Le2i videos; no Le2i window is used for model fitting.
- Primary manifest: four subject-disjoint fold files, each with 7,869 fixed
  windows (1,371 fall and 6,498 non-fall).
- Groups: 14 dataset-prefixed subject groups; every train, validation and test
  split contains both primary datasets without subject overlap.
- Pose cache: 450 unique NPZ files, all checked for expected shapes and finite
  values.

## Execution matrix

1. Main comparison: TCN, TE, TCNTE, UniMamba and MaskedBiMamba; four folds;
   seeds 42, 3407 and 2026; 100 epochs without early stopping. Expected:
   60 `metrics.json` files.
2. Paired ablations: canonical seed 42 on all four folds. Ten variants remove
   bidirectionality, attention, quality pooling, masking or confidence; remove
   confidence and quality jointly; and test mask ratios 0.05, 0.10, 0.20 and
   0.30. Expected: 40 `metrics.json` files. The full 0.15 model is reused from
   the main matrix.
3. Robustness: TCNTE and MaskedBiMamba checkpoints under joint drop, frame
   drop, confidence noise and complete lower-body loss. Expected: 24
   `robustness.json` files.
4. External Le2i evaluation: the same two model families and 24 checkpoints.
   Expected: 24 `robustness.json` files.

## Workspace artifacts

- Project: `$FALLGUARD_CODE_DIR` (defaults to this repository's `code/` directory)
- Work data: `$FALLGUARD_WORK_DIR` (defaults to the parent of `code/`)
- Main results: `outputs/gmdcsa24_main_v1`
- Ablations: `outputs/gmdcsa24_ablations_v1`
- Robustness: `outputs/gmdcsa24_robustness_v1`
- External Le2i: `outputs/gmdcsa24_external_le2i_v1`
- Main log: `logs/gmdcsa24_gpu/main_suite.log`
- Pipeline log: `logs/gmdcsa24_gpu/extended_pipeline.log`
- Pipeline state: `logs/gmdcsa24_gpu/extended_pipeline.status`

The extended pipeline waits for all 60 main results, audits the expected count,
then launches ablations, robustness and external evaluation. A stage failure
writes `FAILED:<code>` instead of silently continuing. Numeric report cells
remain blank until their stage is complete and its expected artifact count is
verified.
