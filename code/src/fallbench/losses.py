from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F


class WeightedFocalLoss(nn.Module):
    """Focal loss on raw logits with optional per-class weights."""

    def __init__(self, weights: torch.Tensor | None = None,
                 gamma: float = 3.0) -> None:
        super().__init__()
        self.gamma = float(gamma)
        self.register_buffer("weights", None if weights is None else weights.float())

    def forward(self, logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        log_prob = F.log_softmax(logits, dim=1)
        prob = log_prob.exp()
        selected_log_prob = log_prob.gather(1, target[:, None]).squeeze(1)
        selected_prob = prob.gather(1, target[:, None]).squeeze(1)
        loss = -((1.0 - selected_prob) ** self.gamma) * selected_log_prob
        if self.weights is not None:
            loss = loss * self.weights[target]
        return loss.mean()


def class_weights(labels: list[int], setting: object) -> torch.Tensor:
    if isinstance(setting, list):
        if len(setting) != 2:
            raise ValueError("Binary class_weights must contain two values")
        return torch.tensor(setting, dtype=torch.float32)
    if setting != "auto":
        raise ValueError("class_weights must be 'auto' or a two-value list")
    counts = torch.bincount(torch.tensor(labels, dtype=torch.long), minlength=2).float()
    if (counts == 0).any():
        raise ValueError(f"Both classes are required in training data; counts={counts.tolist()}")
    return counts.sum() / (2.0 * counts)

