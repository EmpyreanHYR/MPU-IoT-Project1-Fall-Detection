# Experiment-result provenance for the final report

Updated: 2026-09-18

This file records the local evidence used to update `IEEE-conference-main.tex` and its included section files. It is an audit aid, not part of the rendered paper.

## Completed evidence sets

| Evidence ID | Report use | Source | Completeness |
|---|---|---|---|
| R-MAIN | CAUCAFall--GMDCSA-24 five-model comparison | `../../results/main/summary.csv` | 60/60 training runs: 5 models × 4 folds × 3 seeds |
| R-ABL | MaskedBiMamba mechanism and mask-ratio ablations | `../../results/ablations/summary.csv` | 120/120 training runs: 10 variants × 4 folds × 3 seeds |
| R-ROB | Missing-observation tests on the primary protocol | `../../results/robustness/summary.csv` | 24/24 checkpoint evaluations: 2 models × 4 folds × 3 seeds |
| R-EXT | External Le2i evaluation and perturbations | `../../results/external-le2i/summary.csv` | 24/24 checkpoint evaluations: 2 models × 4 folds × 3 seeds |
| R-REP | Le2i TCNTE reproduction | `../../results/tcnte-reproduction/summary.csv` | 9/9 training runs: 3 models × 3 folds × seed 42 |

All reported summary values are arithmetic means and sample standard deviations produced by the experiment aggregation scripts. The paper reports descriptive results only; no formal paired hypothesis test or multiple-comparison correction was prespecified.

## Interpretation boundaries

- The earlier Le2i--CAUCAFall table is retained for auditability and is not the primary GMDCSA-24 result.
- Le2i is external test data for the primary checkpoints and is not used for their fitting.
- Robustness conditions are applied to selected checkpoints without refitting.
- Blank edge--cloud deployment cells remain unmeasured and are not inferred from offline model experiments.
- Small differences between means are not described as statistically significant.

## Independent report review (2026-09-19)

The revision recomputed all window-, video-, and event-level statistics from 249 training-run prediction files (629,595 rows): 60 primary, 120 ablation, 9 reproduction, and 60 earlier-protocol runs. All checked values matched the saved metrics. All 249 histories contain epochs 1--100, and selected epochs match the first maximum validation F1. All six summary sets match their constituent records using arithmetic means and sample standard deviations. The manuscript tables and retained historical supplement contain 201 mean/SD pairs (402 scalar values), with no mismatches. The compact public verification output is `../../results/verification/verified_summary.csv`; the much larger raw prediction archive remains outside Git.

Robustness and external archives each contain 24 checkpoint evaluations with 11 conditions (264 condition rows each). Their confusion matrices and summaries are consistent, but no per-window prediction files were saved for these evaluations; AUROC and event sequences therefore cannot be independently reconstructed from those archives.

Metric definitions were corrected against `code/src/fallbench/engine.py`:

- Reference events are merged positive target windows, not raw annotation intervals.
- False-alarm exposure is the sum over evaluated videos of max(window end) minus min(window start), including positive and negative videos. It is not negative-only monitoring time. The four primary test folds cover 1,827.4 seconds under this definition.
- Delay is a signed difference between matched predicted/reference interval starts, not end-to-end system latency. The dashboard state machine is not applied in the offline metric.
- The primary TCNTE test window F1 is 0.6254; the independent clean robustness rerun is 0.6255, with one target-positive window changing prediction in fold 2 / seed 3407. Both archived values are retained; the underlying numerical cause was not established by this audit.
- Under evaluation-window labels, external Le2i has 130 positive and 60 negative videos. The all-positive video baseline has F1 0.8125. Clean video specificities are 0.1958 (MaskedBiMamba) and 0.1736 (TCNTE); F1 near 0.83 does not alone establish strong cross-dataset discrimination.

The four primary test sets reconstruct 7,869 distinct windows, 1,371 positives, 260 videos and 14 dataset-prefixed subject groups. Test windows, videos and inferred subject groups do not overlap across folds, and the same test definitions are used across all models/seeds. Original train/validation manifests and raw pose caches were not present locally, so this does not independently verify the entire training/validation separation or pose extraction.

Current deployment catalog entries belong to September 16, not the September 18 primary protocol. Live adapters accumulate 30 received frames without timestamp resampling; Pi's 5 Hz publication ceiling implies at least 5.8 seconds between first and last frame. This differs from the one-second offline windows. The ONNX wrapper also substitutes mean joint confidence for detector-box confidence. See `model_audit.md` and `ui_audit.md` for exact code locators.

Figure 1 is drawn from the implementation and all 12 primary MaskedBiMamba configurations. Figure 2 is an actual local idle-state screenshot. The additional brief screenshot shows an explicitly labeled synthetic application test. Local API/SSE/storage/acknowledgement were exercised; remote cloud operation, camera inference, latency, power and accuracy were not remeasured.

The old full Le2i--CAUCAFall result table and the superseded report snapshot remain in the private review archive rather than the public repository, keeping the A4 report and public source tree focused on the reviewed final version.

## Current edge deployment evidence

The current source includes the completed Raspberry Pi and cloud results. Public values and protocol definitions are available in [`results/edge/`](../../results/edge/). There are 39 classified clips out of 40, with 20 TP, 11 TN, 8 FP and one no-output clip. The paired Hailo/CPU throughput comparison, 603.8-second replay, writer recovery and deployed cloud retry/outage observations are summarized separately from the model cross-validation experiments. Source figures use PNG for this repository's source-only distribution.
