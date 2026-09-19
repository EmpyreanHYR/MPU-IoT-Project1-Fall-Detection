# Result templates

All cells stay `TBD` until generated from `metrics.json` files with the matching
protocol. Window and video/event metrics are never mixed.

## Main subject-independent comparison

| Method | Confidence input | Parameters | Window F1 | Video/event F1 | Recall | Specificity | AUROC |
|---|---:|---:|---:|---:|---:|---:|---:|
| TCN | ✓ | TBD | TBD | TBD | TBD | TBD | TBD |
| TE | ✓ | TBD | TBD | TBD | TBD | TBD | TBD |
| TCNTE | ✓ | TBD | TBD | TBD | TBD | TBD | TBD |
| UniMamba | ✓ | TBD | TBD | TBD | TBD | TBD | TBD |
| MaskedBiMamba | ✓ | TBD | TBD | TBD | TBD | TBD | TBD |

## Mechanism ablation

| Variant | Bi-directional | Temporal attention | Quality pooling | Frame masking | Confidence | Event F1 |
|---|:---:|:---:|:---:|:---:|:---:|---:|
| Full | ✓ | ✓ | ✓ | ✓ | ✓ | TBD |
| No bidirectional branch |  | ✓ | ✓ | ✓ | ✓ | TBD |
| No temporal attention | ✓ |  | ✓ | ✓ | ✓ | TBD |
| No quality pooling | ✓ | ✓ |  | ✓ | ✓ | TBD |
| No frame masking | ✓ | ✓ | ✓ |  | ✓ | TBD |
| No confidence input | ✓ | ✓ | ✓ | ✓ |  | TBD |
| No confidence or quality pooling | ✓ | ✓ |  | ✓ |  | TBD |
| Mask ratio 0.05 | ✓ | ✓ | ✓ | 0.05 | ✓ | TBD |
| Mask ratio 0.10 | ✓ | ✓ | ✓ | 0.10 | ✓ | TBD |
| Mask ratio 0.20 | ✓ | ✓ | ✓ | 0.20 | ✓ | TBD |
| Mask ratio 0.30 | ✓ | ✓ | ✓ | 0.30 | ✓ | TBD |

## Robustness

| Method | Clean | Joint drop 10% | Joint drop 30% | Frame drop 30% | Lower body missing | Confidence noise 30% |
|---|---:|---:|---:|---:|---:|---:|
| TCNTE | TBD | TBD | TBD | TBD | TBD | TBD |
| MaskedBiMamba | TBD | TBD | TBD | TBD | TBD | TBD |

## Cross-dataset generalization

| Training data | Held-out dataset | TCNTE event F1 | MaskedBiMamba event F1 | Domain notes |
|---|---|---:|---:|---|
| CAUCAFall + GMDCSA-24 | Le2i | TBD | TBD | low resolution and scene shift; external test only |
