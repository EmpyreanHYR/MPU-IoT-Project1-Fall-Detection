from __future__ import annotations

from typing import Iterable

import numpy as np
from sklearn.metrics import confusion_matrix, roc_auc_score


def binary_metrics(targets: Iterable[int], probabilities: Iterable[float],
                   threshold: float = 0.5) -> dict[str, float | int]:
    y_true = np.asarray(list(targets), dtype=np.int64)
    y_prob = np.asarray(list(probabilities), dtype=np.float64)
    y_pred = (y_prob >= threshold).astype(np.int64)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    safe = lambda numerator, denominator: float(numerator / denominator) if denominator else 0.0
    precision = safe(tp, tp + fp)
    recall = safe(tp, tp + fn)
    specificity = safe(tn, tn + fp)
    f1 = safe(2 * precision * recall, precision + recall)
    try:
        auroc = float(roc_auc_score(y_true, y_prob))
    except ValueError:
        auroc = float("nan")
    return {
        "accuracy": safe(tp + tn, tp + tn + fp + fn),
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "auroc": auroc,
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }

