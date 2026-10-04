# Selected offline MaskedBiMamba model

This is the actual temporal classifier used by the offline edge pipeline.
The small public release includes its PyTorch weights, two-input ONNX graph,
validation-only selection record, file sizes and SHA-256 hashes.

| Field | Value |
| --- | --- |
| Training protocol | Primary CAUCAFall + GMDCSA-24 subject-disjoint four-fold protocol; Le2i excluded from fitting. |
| Selected run | `gmdcsa24_main_v1/masked_bimamba/fold_3/seed_3407`, epoch 41. |
| Selection | Maximum best-validation F1 across 12 MaskedBiMamba fold/seed candidates; see `deployment_selection.json`. |
| Selected validation F1 | 0.7087378641; not a test-set or ensemble metric. |
| Pose input | `pose`: float32 `[1,30,36]`, COCO joints 5–16 in index order; each joint contributes `(x,y,confidence)`. |
| Quality input | `quality`: float32 `[1,30,3]`: mean body-joint confidence, fraction with confidence ≥0.2, detector box confidence. |
| Coordinates | Per-frame min-max on the 12 retained joints, independently for x/y; range denominator at least 1e-4. |
| Window | 1.0 second, interpolated to 30 steps with the right endpoint excluded; decisions every 0.2 seconds. |
| Output | `logits`: `[1,2]`, non-fall then fall; softmax index 1 is the fall probability. |
| ONNX | Opset 17; portable CPU reference selective scan; no CUDA extension needed. |

The edge quality gate suppresses inference if fewer than half of the observed
frames have at least six body joints above 0.2 confidence. Non-monotonic
timestamps or a gap above 0.5 seconds reset the window. The local alert state
uses the existing fixed rules: suspicion at 0.65, confirmation after two high
readings with current probability at least 0.82, and clearance after two readings
at most 0.35. These thresholds are not clinically calibrated.

`masked_bimamba.pt` contains only the state dictionary, model name, dimensions
and architecture configuration needed for reconstruction. Optimizer state,
local paths and the original training environment are omitted. It loads with
`torch.load(..., weights_only=True)`. The ONNX binary is copied unchanged from
the offline deployment asset. No weights were retrained for this release.

```sh
python scripts/verify_assets.py
python code/scripts/export_mamba_onnx.py \
  artifacts/models/masked_bimamba.pt data/models/reexport.onnx --quality-input
```

The parity check compares portable PyTorch with ONNX CPU, using explicitly
supplied quality. It does not compare against the original CUDA selective-scan
kernel or reproduce held-out video accuracy. The public tests additionally
check deployment preprocessing against the training dataset implementation.

Use limits: single-person primary-pose prototype, simulated/staged fall datasets,
distribution shift, pose failure and substantial false-alert burden. A selected
single checkpoint does not represent the mean of the 12 evaluated models.
This artifact is for reproducibility and demonstration, not a validated care alarm.

The project's license applies to its own temporal model/code. YOLO pose weights,
Hailo runtimes and datasets are separate upstream assets with their own terms.
