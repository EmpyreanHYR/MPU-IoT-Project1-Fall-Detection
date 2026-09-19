"""Export fixed-length FallGuard Mamba checkpoints to portable CPU ONNX.

The training model uses mamba-ssm CUDA kernels.  This exporter implements the
official reference selective scan with ordinary PyTorch operations and unrolls
the fixed 30-frame sequence, so ONNX Runtime does not require CUDA extensions.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import onnx
import onnxruntime as ort
import torch
from torch import nn
from torch.nn import functional as F


class LearnedPositionEncoding(nn.Module):
    def __init__(self, dimension: int, max_length: int = 512) -> None:
        super().__init__()
        self.encoding = nn.Parameter(torch.zeros(1, max_length, dimension))

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return value + self.encoding[:, : value.shape[1]]


class PortableMamba(nn.Module):
    """Mamba v1 block matching mamba-ssm 2.2.2 reference inference."""

    def __init__(self, dimension: int, state_size: int, conv_size: int,
                 expand: int) -> None:
        super().__init__()
        self.inner = dimension * expand
        self.state_size = state_size
        self.rank = (dimension + 15) // 16
        self.in_proj = nn.Linear(dimension, self.inner * 2, bias=False)
        self.conv1d = nn.Conv1d(self.inner, self.inner, conv_size,
                                groups=self.inner, padding=conv_size - 1)
        self.x_proj = nn.Linear(self.inner, self.rank + state_size * 2, bias=False)
        self.dt_proj = nn.Linear(self.rank, self.inner, bias=True)
        self.A_log = nn.Parameter(torch.empty(self.inner, state_size))
        self.D = nn.Parameter(torch.empty(self.inner))
        self.out_proj = nn.Linear(self.inner, dimension, bias=False)

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        length = hidden.shape[1]
        projected = self.in_proj(hidden).transpose(1, 2)
        value, gate = projected.chunk(2, dim=1)
        value = F.silu(self.conv1d(value)[..., :length])
        mixed = self.x_proj(value.transpose(1, 2))
        delta_raw = mixed[..., : self.rank]
        input_b = mixed[..., self.rank:self.rank + self.state_size]
        input_c = mixed[..., self.rank + self.state_size:]
        delta = F.softplus(F.linear(delta_raw, self.dt_proj.weight,
                                   self.dt_proj.bias))
        transition = -torch.exp(self.A_log)
        state = torch.zeros(value.shape[0], self.inner, self.state_size,
                            dtype=value.dtype, device=value.device)
        outputs: list[torch.Tensor] = []
        value_steps = value.transpose(1, 2)
        gate_steps = gate.transpose(1, 2)
        for index in range(length):
            step = delta[:, index]
            current = value_steps[:, index]
            state = (torch.exp(step.unsqueeze(-1) * transition.unsqueeze(0)) * state
                     + step.unsqueeze(-1) * input_b[:, index].unsqueeze(1)
                     * current.unsqueeze(-1))
            scanned = (state * input_c[:, index].unsqueeze(1)).sum(dim=-1)
            scanned = (scanned + self.D * current) * F.silu(gate_steps[:, index])
            outputs.append(scanned)
        return self.out_proj(torch.stack(outputs, dim=1))


class PortableFallMamba(nn.Module):
    def __init__(self, model_name: str, pose_size: int, quality_size: int,
                 config: dict[str, Any]) -> None:
        super().__init__()
        hidden = int(config["mamba_hidden_size"])
        self.bidirectional = model_name == "masked_bimamba"
        self.use_attention = self.bidirectional and bool(config.get("temporal_attention", True))
        self.use_quality = self.bidirectional and bool(config.get("quality_weighted_pooling", True))
        self.projection = nn.Linear(pose_size, hidden)
        self.position = LearnedPositionEncoding(hidden)
        if self.use_attention:
            self.attention = nn.MultiheadAttention(
                hidden, int(config.get("transformer_heads", 4)), batch_first=True)
            self.attention_norm = nn.LayerNorm(hidden)

        def stack() -> nn.ModuleList:
            return nn.ModuleList([
                PortableMamba(hidden, int(config["mamba_state_size"]),
                              int(config["mamba_conv_size"]), int(config["mamba_expand"]))
                for _ in range(int(config["mamba_layers"]))
            ])

        self.forward_layers = stack()
        self.backward_layers = stack() if self.bidirectional else None
        self.direction_fusion = (nn.Linear(hidden * 2, hidden)
                                 if self.bidirectional else nn.Identity())
        self.norm = nn.LayerNorm(hidden)
        self.quality_gate = nn.Sequential(
            nn.Linear(quality_size, hidden // 2), nn.ReLU(),
            nn.Linear(hidden // 2, 1), nn.Sigmoid())
        self.classifier = nn.Linear(hidden, 2)

    @staticmethod
    def run_stack(value: torch.Tensor, layers: nn.ModuleList) -> torch.Tensor:
        for layer in layers:
            value = value + layer(value)
        return value

    @staticmethod
    def quality_from_pose(pose: torch.Tensor) -> torch.Tensor:
        confidence = pose[..., 2::3].clamp(0, 1)
        mean_confidence = confidence.mean(dim=-1, keepdim=True)
        visible = (confidence >= 0.2).to(pose.dtype).mean(dim=-1, keepdim=True)
        return torch.cat((mean_confidence, visible, mean_confidence), dim=-1)

    def forward(self, pose: torch.Tensor) -> torch.Tensor:
        hidden = self.position(self.projection(pose))
        if self.use_attention:
            attended, _ = self.attention(hidden, hidden, hidden, need_weights=False)
            hidden = self.attention_norm(hidden + attended)
        forward = self.run_stack(hidden, self.forward_layers)
        if self.backward_layers is not None:
            backward = self.run_stack(torch.flip(hidden, dims=[1]), self.backward_layers)
            backward = torch.flip(backward, dims=[1])
            hidden = self.direction_fusion(torch.cat((forward, backward), dim=-1))
        else:
            hidden = forward
        hidden = self.norm(hidden)
        if self.use_quality:
            weights = self.quality_gate(self.quality_from_pose(pose)).clamp_min(1e-6)
            pooled = (hidden * weights).sum(dim=1) / weights.sum(dim=1)
        else:
            pooled = hidden.mean(dim=1)
        return self.classifier(pooled)


def export(checkpoint: Path, destination: Path) -> None:
    saved = torch.load(checkpoint, map_location="cpu", weights_only=False)
    model = PortableFallMamba(saved["model_name"], int(saved["pose_size"]),
                              int(saved["quality_size"]), saved["config"]["model"])
    missing, unexpected = model.load_state_dict(saved["model_state"], strict=False)
    if missing or unexpected:
        raise RuntimeError(f"checkpoint mismatch: missing={missing}, unexpected={unexpected}")
    model.eval()
    generator = torch.Generator().manual_seed(20260916)
    sample = torch.rand((1, 30, int(saved["pose_size"])), generator=generator)
    sample[..., 2::3] = torch.rand((1, 30, int(saved["pose_size"]) // 3), generator=generator)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with torch.no_grad():
        expected = model(sample).numpy()
    torch.onnx.export(model, (sample,), destination, input_names=["pose"],
                      output_names=["logits"], opset_version=17,
                      dynamic_axes={"pose": {0: "batch"}, "logits": {0: "batch"}},
                      dynamo=False)
    onnx.checker.check_model(onnx.load(destination))
    session = ort.InferenceSession(str(destination), providers=["CPUExecutionProvider"])
    actual = session.run(["logits"], {"pose": sample.numpy()})[0]
    difference = float(np.max(np.abs(expected - actual)))
    if difference > 2e-4:
        raise RuntimeError(f"ONNX parity failed: max_abs_diff={difference}")
    print(f"{checkpoint.name} -> {destination.name}; max_abs_diff={difference:.8f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    export(args.checkpoint, args.destination)


if __name__ == "__main__":
    main()
