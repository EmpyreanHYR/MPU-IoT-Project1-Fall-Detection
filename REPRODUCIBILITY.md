# Reproduce inference and rebuild experiments

## What is now available

| Artifact | Availability and scope |
| --- | --- |
| Selected MaskedBiMamba checkpoint and two-input ONNX | Included in [`artifacts/models/`](artifacts/models/), with checksums and validation-only selection evidence. |
| Offline edge and cloud code | Included with a [local launcher, configuration and Linux service templates](deployment/README.md). |
| Primary test folds | [`260 video assignments`](datasets/primary_test_folds.csv) recovered from saved predictions and cross-checked across all 60 primary runs. |
| Original training/validation folds | Not recovered locally. The rebuild command creates a **new** validation protocol, labeled `rebuilt-validation-v1`. |
| Original pose caches and full window manifests | Not included. Regenerate them from the authorized videos; detector/version differences can change the samples and results. |
| Aggregate reported results | Included under [`results/`](results/); no new experiment scores are substituted. |
| Other 59 primary checkpoints and ablation checkpoints | Not part of this small inference release; regenerate through the experiment code. |

The included checkpoint supports deployment without retraining. It is the
validation-selected `masked_bimamba/fold_3/seed_3407`, epoch 41. Its single-model
validation F1 0.7087378641 is **not** the reported cross-fold test performance.
See its [model card](artifacts/models/README.md) for the input contract and limits.

## Obtain source data and annotations

Use the original data publishers and the versions in
[`DATASET_PROVENANCE_AND_USAGE.md`](datasets/DATASET_PROVENANCE_AND_USAGE.md).
The primary experiment uses CAUCAFall v5 (100 videos) and GMDCSA-24 v2.1
(160 videos). Le2i (190 videos) is the external test set and the separate TCNTE
reproduction track. Do not add Le2i to primary fitting.

The recorded OmniFall annotation revision is
`83572a37b9e3081df8c06a56874b1d1f2a19386c`. Download `labels/caucafall.csv`,
`labels/GMDCSA24.csv` and, for the external track, `labels/le2i.csv` from
[that revision](https://huggingface.co/datasets/simplexsigil2/omnifall/tree/83572a37b9e3081df8c06a56874b1d1f2a19386c/labels).
The [mapping templates](datasets/mapping_templates/) already list all 450
annotation video paths; fill the blank `video_path` cells with your authorized
local files. Source URLs, counts and hashes are recorded in
[`annotation_sources.json`](datasets/annotation_sources.json). This explicit mapping avoids silently selecting an
unrelated similarly named video. Example schema:

```csv
path,video_path
publisher-relative-video-id,/absolute/path/to/authorized/video.avi
```

Raw video, pose caches, absolute local paths and generated weights stay in your
work directory. Data rights remain with the respective publishers. Neither the
project license nor this reconstruction entry grants rights to redistribute
the Le2i mirror or other third-party videos.

## Rebuild the primary experiment inputs

Install the experiment package in a separate environment; GPU Mamba training
requires the validated CUDA environment described in `code/docs/GMDCSA24_GPU_RUN.md`.
The portable CPU deployment environment alone does not provide the CUDA scan. The recorded training environment used Python 3.10.8,
PyTorch 2.1.2+cu121 and an RTX 3090. In a compatible CUDA training environment,
install the extension pins listed in `code/requirements.txt` before running the
Mamba suites:

```sh
python -m pip install transformers==4.44.2
python -m pip install causal-conv1d==1.4.0 mamba-ssm==2.2.2 --no-build-isolation
```

These extensions are unnecessary for the included portable inference model.
Use an absolute `FALLGUARD_WORK_DIR` for your authorized data and outputs.

```sh
python -m pip install -r code/requirements.txt
python -m pip install -e code
export FALLGUARD_WORK_DIR=/absolute/path/to/your/fallguard-work

python code/scripts/prepare_omnifall_manifest.py \
  --labels "$FALLGUARD_WORK_DIR/labels/caucafall.csv" \
  --path-mapping "$FALLGUARD_WORK_DIR/caucafall_mapping.csv" \
  --dataset caucafall --output "$FALLGUARD_WORK_DIR/caucafall_segments.csv"
python code/scripts/prepare_omnifall_manifest.py \
  --labels "$FALLGUARD_WORK_DIR/labels/GMDCSA24.csv" \
  --path-mapping "$FALLGUARD_WORK_DIR/gmdcsa24_mapping.csv" \
  --dataset GMDCSA24 --output "$FALLGUARD_WORK_DIR/gmdcsa24_segments.csv"
python - <<'PY'
import os
from pathlib import Path
import pandas as pd
work=Path(os.environ['FALLGUARD_WORK_DIR'])
table=pd.concat([pd.read_csv(work/name,dtype={'subject':str})
                 for name in ('caucafall_segments.csv','gmdcsa24_segments.csv')],ignore_index=True)
table.to_csv(work/'primary_segments.csv',index=False)
PY

python code/scripts/audit_manifest.py --manifest "$FALLGUARD_WORK_DIR/primary_segments.csv"
python code/scripts/extract_pose.py \
  --manifest "$FALLGUARD_WORK_DIR/primary_segments.csv" \
  --output-dir "$FALLGUARD_WORK_DIR/poses" --model yolov8s-pose.pt --device 0
python code/scripts/rebuild_primary.py \
  --manifest "$FALLGUARD_WORK_DIR/primary_segments.csv" \
  --pose-index "$FALLGUARD_WORK_DIR/poses/index.csv" \
  --output-dir "$FALLGUARD_WORK_DIR/rebuilt-validation-v1"

python code/scripts/run_suite.py --config code/configs/main_protocol.yaml \
  --fold-dir "$FALLGUARD_WORK_DIR/rebuilt-validation-v1" \
  --output-dir "$FALLGUARD_WORK_DIR/outputs/rebuilt-validation-v1"
```

The builder checks video identity, adds dataset prefixes to subject groups,
preserves the recovered test fold, allocates new validation subjects within
each dataset, and writes all four segment/window manifests plus `REBUILT.json`.
Windows use 1 second, 0.2-second stride, 30 steps, at least 50% dynamic-fall
overlap, and exclusion after the final fall. The destination must be new/empty.
Missing identities or caches stop the pipeline. The rebuilt results must be
reported separately; they cannot validate an exact reproduction of the original
training run until the original validation assignments and caches are recovered.

## Verification and remaining handover

[`verify.yml`](.github/workflows/verify.yml) verifies asset hashes, real local
HTTP synchronization, transaction rollback, restart persistence, timestamp
preservation, classifier preprocessing, portable PyTorch/ONNX parity and subject
isolation. These software fixtures are not additional accuracy experiments.
Verification details are recorded in [`verification.json`](artifacts/models/verification.json).
Physical Hailo and multi-host production behavior remain the historical tests
documented in [`results/edge/`](results/edge/).

## Course submission version

The report and individual contributions are separate IEEE two-column documents.
All five contributions are consolidated from the team's supplied Word records;
[SUBMISSION.md](SUBMISSION.md) lists the report, appendix, presentation and fixed
repository version. The main demonstration can be run with the included selected
model and the deployment instructions above.

For exact repetition of the historical training scores, retain or recover the
original training/validation manifests and pose caches. The rebuilt-validation
commands provide a clearly named new protocol when those artifacts are unavailable.
The course submission package contains the meeting record document; the student
adds the school's similarity report separately.
