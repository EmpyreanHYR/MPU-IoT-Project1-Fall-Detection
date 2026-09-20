# Aggregate experiment results

This directory contains compact CSV summaries used by the final report. It excludes model checkpoints, raw datasets, pose caches, full training logs, and per-window prediction archives.

| Directory | Evidence |
| --- | --- |
| `main/` | Five-model CAUCAFall--GMDCSA-24 comparison. |
| `ablations/` | MaskedBiMamba mechanism and mask-ratio ablations. |
| `robustness/` | Missing-observation evaluations. |
| `external-le2i/` | External Le2i evaluations. |
| `tcnte-reproduction/` | Le2i TCNTE reproduction. |
| `verification/` | Independently recomputed compact verification summary. |

Each experiment folder contains `all_runs.csv` and/or `summary.csv`. See [`manuscripts/final-report/RESULTS_PROVENANCE.md`](../manuscripts/final-report/RESULTS_PROVENANCE.md) for interpretation limits and completeness counts.


The [`edge/`](edge/) folder adds measured local-inference, synthetic-clip, short-session stability and cloud-delivery evidence. These are system measurements with their own sample sizes and must not be pooled with model cross-validation results.
