from __future__ import annotations

import math
from typing import Any

import torch
from torch import nn
from torch.nn.utils.parametrizations import weight_norm


class Chomp1d(nn.Module):
    def __init__(self, size: int) -> None:
        super().__init__()
        self.size = size

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x if self.size == 0 else x[:, :, :-self.size].contiguous()


class TemporalBlock(nn.Module):
    def __init__(self, input_size: int, output_size: int, kernel_size: int,
                 dilation: int, dropout: float) -> None:
        super().__init__()
        padding = (kernel_size - 1) * dilation
        self.layers = nn.Sequential(
            weight_norm(nn.Conv1d(input_size, output_size, kernel_size,
                                  padding=padding, dilation=dilation)),
            Chomp1d(padding), nn.ReLU(), nn.Dropout(dropout),
            weight_norm(nn.Conv1d(output_size, output_size, kernel_size,
                                  padding=padding, dilation=dilation)),
            Chomp1d(padding), nn.ReLU(), nn.Dropout(dropout),
        )
        self.residual = (nn.Conv1d(input_size, output_size, 1)
                         if input_size != output_size else nn.Identity())
        self.activation = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.activation(self.layers(x) + self.residual(x))


class TemporalConvNet(nn.Module):
    def __init__(self, input_size: int, channels: list[int], kernel_size: int,
                 dropout: float) -> None:
        super().__init__()
        self.output_size = channels[-1]
        self.network = nn.Sequential(*[
            TemporalBlock(input_size if index == 0 else channels[index - 1],
                          output, kernel_size, 2 ** index, dropout)
            for index, output in enumerate(channels)
        ])

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x.transpose(1, 2)).transpose(1, 2)


class LearnedPositionEncoding(nn.Module):
    def __init__(self, dimension: int, max_length: int = 512) -> None:
        super().__init__()
        self.encoding = nn.Parameter(torch.zeros(1, max_length, dimension))
        nn.init.trunc_normal_(self.encoding, std=0.02)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.encoding[:, :x.shape[1]]


class SinusoidalPositionEncoding(nn.Module):
    def __init__(self, dimension: int, max_length: int = 512) -> None:
        super().__init__()
        positions = torch.arange(max_length, dtype=torch.float32).unsqueeze(1)
        frequencies = torch.exp(torch.arange(0, dimension, 2, dtype=torch.float32)
                                * (-math.log(10000.0) / dimension))
        encoding = torch.zeros(max_length, dimension)
        encoding[:, 0::2] = torch.sin(positions * frequencies)
        encoding[:, 1::2] = torch.cos(
            positions * frequencies[:encoding[:, 1::2].shape[1]])
        self.register_buffer("encoding", encoding.unsqueeze(0), persistent=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.encoding[:, :x.shape[1]]


def _position(kind: str, dimension: int) -> nn.Module:
    if kind == "learned":
        return LearnedPositionEncoding(dimension)
    if kind == "sinusoidal":
        return SinusoidalPositionEncoding(dimension)
    raise ValueError(f"Unknown position encoding: {kind}")


class TCNClassifier(nn.Module):
    def __init__(self, input_size: int, cfg: dict[str, Any]) -> None:
        super().__init__()
        self.tcn = TemporalConvNet(input_size, cfg["tcn_channels"],
                                   cfg["tcn_kernel_size"], cfg["tcn_dropout"])
        self.classifier = nn.Linear(self.tcn.output_size, 2)

    def forward(self, pose: torch.Tensor, **_: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.tcn(pose).mean(dim=1))


class TransformerClassifier(nn.Module):
    def __init__(self, input_size: int, cfg: dict[str, Any]) -> None:
        super().__init__()
        dimension = cfg["tcn_channels"][-1]
        self.projection = nn.Linear(input_size, dimension)
        self.position = _position(cfg["position_encoding"], dimension)
        layer = nn.TransformerEncoderLayer(
            d_model=dimension, nhead=cfg["transformer_heads"],
            dim_feedforward=cfg["transformer_ffn"],
            dropout=cfg["transformer_dropout"], batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, cfg["transformer_layers"])
        self.classifier = nn.Linear(dimension, 2)

    def forward(self, pose: torch.Tensor, **_: torch.Tensor) -> torch.Tensor:
        encoded = self.encoder(self.position(self.projection(pose)))
        return self.classifier(encoded.mean(dim=1))


class TCNTransformer(nn.Module):
    def __init__(self, input_size: int, cfg: dict[str, Any]) -> None:
        super().__init__()
        self.tcn = TemporalConvNet(input_size, cfg["tcn_channels"],
                                   cfg["tcn_kernel_size"], cfg["tcn_dropout"])
        dimension = self.tcn.output_size
        self.position = _position(cfg["position_encoding"], dimension)
        layer = nn.TransformerEncoderLayer(
            d_model=dimension, nhead=cfg["transformer_heads"],
            dim_feedforward=cfg["transformer_ffn"],
            dropout=cfg["transformer_dropout"], batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, cfg["transformer_layers"])
        self.classifier = nn.Linear(dimension, 2)

    def forward(self, pose: torch.Tensor, **_: torch.Tensor) -> torch.Tensor:
        encoded = self.encoder(self.position(self.tcn(pose)))
        return self.classifier(encoded.mean(dim=1))


class MaskedBiMamba(nn.Module):
    """Skeleton Mamba inspired by Fall-Mamba; not an exact RGB-audio replica."""

    def __init__(self, input_size: int, quality_size: int,
                 cfg: dict[str, Any]) -> None:
        super().__init__()
        try:
            from mamba_ssm import Mamba
        except ImportError as exc:
            raise RuntimeError(
                "masked_bimamba requires a CUDA-compatible mamba-ssm install") from exc
        hidden = int(cfg["mamba_hidden_size"])
        self.frame_mask_ratio = float(cfg.get("frame_mask_ratio", 0.0))
        self.bidirectional = bool(cfg.get("bidirectional", True))
        self.use_attention = bool(cfg.get("temporal_attention", True))
        self.use_quality = bool(cfg.get("quality_weighted_pooling", True))
        self.projection = nn.Linear(input_size, hidden)
        self.position = LearnedPositionEncoding(hidden)
        if self.use_attention:
            heads = int(cfg.get("transformer_heads", 4))
            self.attention = nn.MultiheadAttention(hidden, heads, batch_first=True)
            self.attention_norm = nn.LayerNorm(hidden)

        def stack() -> nn.ModuleList:
            return nn.ModuleList([
                Mamba(d_model=hidden, d_state=int(cfg["mamba_state_size"]),
                      d_conv=int(cfg["mamba_conv_size"]),
                      expand=int(cfg["mamba_expand"]))
                for _ in range(int(cfg["mamba_layers"]))
            ])

        self.forward_layers = stack()
        self.backward_layers = stack() if self.bidirectional else None
        self.direction_fusion = nn.Linear(hidden * 2, hidden) if self.bidirectional else nn.Identity()
        self.norm = nn.LayerNorm(hidden)
        self.quality_gate = nn.Sequential(
            nn.Linear(quality_size, hidden // 2), nn.ReLU(),
            nn.Linear(hidden // 2, 1), nn.Sigmoid())
        self.classifier = nn.Linear(hidden, 2)

    def _mask_frames(self, x: torch.Tensor) -> torch.Tensor:
        if not self.training or self.frame_mask_ratio <= 0:
            return x
        mask = torch.rand(x.shape[:2], device=x.device) < self.frame_mask_ratio
        all_masked = mask.all(dim=1)
        if all_masked.any():
            mask[all_masked, 0] = False
        return x.masked_fill(mask.unsqueeze(-1), 0.0)

    @staticmethod
    def _run_stack(x: torch.Tensor, layers: nn.ModuleList) -> torch.Tensor:
        for layer in layers:
            x = x + layer(x)
        return x

    def forward(self, pose: torch.Tensor, quality: torch.Tensor,
                **_: torch.Tensor) -> torch.Tensor:
        hidden = self.position(self.projection(self._mask_frames(pose)))
        if self.use_attention:
            attended, _ = self.attention(hidden, hidden, hidden, need_weights=False)
            hidden = self.attention_norm(hidden + attended)
        forward = self._run_stack(hidden, self.forward_layers)
        if self.backward_layers is not None:
            backward = self._run_stack(torch.flip(hidden, dims=[1]),
                                       self.backward_layers)
            backward = torch.flip(backward, dims=[1])
            hidden = self.direction_fusion(torch.cat((forward, backward), dim=-1))
        else:
            hidden = forward
        hidden = self.norm(hidden)
        if self.use_quality:
            weights = self.quality_gate(quality).clamp_min(1e-6)
            pooled = (hidden * weights).sum(dim=1) / weights.sum(dim=1)
        else:
            pooled = hidden.mean(dim=1)
        return self.classifier(pooled)


def build_model(name: str, pose_size: int, quality_size: int,
                cfg: dict[str, Any]) -> nn.Module:
    if name == "tcn":
        return TCNClassifier(pose_size, cfg)
    if name == "te":
        return TransformerClassifier(pose_size, cfg)
    if name == "tcnte":
        return TCNTransformer(pose_size, cfg)
    if name in {"unimamba", "masked_bimamba"}:
        effective = dict(cfg)
        if name == "unimamba":
            effective.update({"bidirectional": False, "temporal_attention": False,
                              "quality_weighted_pooling": False,
                              "frame_mask_ratio": 0.0})
        return MaskedBiMamba(pose_size, quality_size, effective)
    raise ValueError(f"Unknown model: {name}")

