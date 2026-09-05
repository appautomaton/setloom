# SPDX-License-Identifier: AGPL-3.0-only
"""BS-RoFormer (Band-Split RoFormer) for music source separation, in MLX.

A clean, single-path implementation of the band-split RoFormer used for stem
separation, running natively on Apple Silicon via MLX. The architecture follows
lucidrains' BS-RoFormer (MIT); the MLX port references ssmall256's
mlx-audio-separator (MIT). See LICENSES/NOTICE. The STFT/iSTFT pair comes from
``mlx-spectro`` so the spectral front end matches the training-time PyTorch
transform exactly.

Module and parameter names mirror the upstream PyTorch checkpoint layout (after
the rename in :mod:`setloom.anatomy.roformer.weights`), so a converted state dict
loads by name with no per-tensor surgery here.
"""

from __future__ import annotations

import math

import mlx.core as mx
import mlx.nn as nn
from mlx_spectro import get_transform_mlx

# Default band layout (sums to 1025 = n_fft//2 + 1 for n_fft=2048); configs override it.
DEFAULT_FREQS_PER_BANDS = (
    *([2] * 24), *([4] * 12), *([12] * 8), *([24] * 8), *([48] * 8), 128, 129,
)


class L2Norm(nn.Module):
    """RMS-style norm matching the PyTorch reference: x / max(||x||, eps) * sqrt(dim) * weight."""

    def __init__(self, dim: int, eps: float = 1e-12):
        super().__init__()
        self.eps = eps
        self.scale = dim**0.5
        self.weight = mx.ones((dim,))

    def __call__(self, x: mx.array) -> mx.array:
        norm = mx.sqrt(mx.sum(x * x, axis=-1, keepdims=True))
        return (x / mx.maximum(norm, self.eps)) * self.scale * self.weight


class ExactGELU(nn.Module):
    """erf-based GELU, matching PyTorch's default (not the tanh approximation)."""

    def __call__(self, x: mx.array) -> mx.array:
        return 0.5 * x * (1.0 + mx.erf(x / math.sqrt(2.0)))


class FeedForward(nn.Module):
    """Norm -> Linear -> GELU -> Linear, held in a Sequential for name parity (net.layers.N)."""

    def __init__(self, dim: int, mult: int = 4, dropout: float = 0.0):
        super().__init__()
        inner = int(dim * mult)
        self.net = nn.Sequential(
            L2Norm(dim),
            nn.Linear(dim, inner),
            ExactGELU(),
            nn.Dropout(dropout),
            nn.Linear(inner, dim),
            nn.Dropout(dropout),
        )

    def __call__(self, x: mx.array) -> mx.array:
        return self.net(x)


class Attention(nn.Module):
    """Multi-head attention with rotary embeddings and per-head sigmoid gating."""

    def __init__(self, dim: int, heads: int = 8, dim_head: int = 64, dropout: float = 0.0):
        super().__init__()
        self.heads = heads
        self.dim_head = dim_head
        self.scale = dim_head**-0.5
        inner = heads * dim_head
        self.norm = L2Norm(dim)
        self.to_qkv = nn.Linear(dim, inner * 3, bias=False)
        self.to_gates = nn.Linear(dim, heads)
        self.to_out = nn.Sequential(nn.Linear(inner, dim, bias=False), nn.Dropout(dropout))

    def __call__(self, x: mx.array) -> mx.array:
        b, n, _ = x.shape
        x = self.norm(x)

        qkv = self.to_qkv(x).reshape(b, n, 3, self.heads, self.dim_head)
        qkv = qkv.transpose(2, 0, 3, 1, 4)  # (3, b, h, n, d)
        q, k, v = qkv[0], qkv[1], qkv[2]

        # traditional=True matches PyTorch's RotaryEmbedding interleaving exactly.
        q = mx.fast.rope(q, self.dim_head, traditional=True, base=10000.0, scale=1.0, offset=0)
        k = mx.fast.rope(k, self.dim_head, traditional=True, base=10000.0, scale=1.0, offset=0)

        out = mx.fast.scaled_dot_product_attention(q, k, v, scale=self.scale)

        gates = mx.sigmoid(self.to_gates(x))  # (b, n, h)
        out = out * gates.transpose(0, 2, 1)[..., None]  # (b, h, n, 1)

        out = out.transpose(0, 2, 1, 3).reshape(b, n, self.heads * self.dim_head)
        return self.to_out(out)


class TransformerLayer(nn.Module):
    """Pre-norm attention then feed-forward, each residual."""

    def __init__(self, attn: Attention, ff: FeedForward):
        super().__init__()
        self.attn = attn
        self.ff = ff

    def __call__(self, x: mx.array) -> mx.array:
        x = self.attn(x) + x
        return self.ff(x) + x


class Transformer(nn.Module):
    """Stack of transformer layers registered as layers_0, layers_1, ... for name parity."""

    def __init__(self, *, dim: int, depth: int, dim_head: int, heads: int, ff_mult: int,
                 attn_dropout: float = 0.0, ff_dropout: float = 0.0, norm_output: bool = False):
        super().__init__()
        self.depth = depth
        for i in range(depth):
            attn = Attention(dim, heads=heads, dim_head=dim_head, dropout=attn_dropout)
            ff = FeedForward(dim, mult=ff_mult, dropout=ff_dropout)
            setattr(self, f"layers_{i}", TransformerLayer(attn, ff))
        self.norm = L2Norm(dim) if norm_output else nn.Identity()

    def __call__(self, x: mx.array) -> mx.array:
        for i in range(self.depth):
            x = getattr(self, f"layers_{i}")(x)
        return self.norm(x)


class BandSplitModule(nn.Module):
    """Per-band norm then linear projection into the model dimension."""

    def __init__(self, dim_in: int, dim_out: int):
        super().__init__()
        self.norm = L2Norm(dim_in)
        self.linear = nn.Linear(dim_in, dim_out)

    def __call__(self, x: mx.array) -> mx.array:
        return self.linear(self.norm(x))


class BandSplit(nn.Module):
    """Split frequency bins into bands and project each to the feature dimension."""

    def __init__(self, dim: int, dim_inputs: tuple[int, ...]):
        super().__init__()
        self.dim_inputs = dim_inputs
        # mx.split takes split points (cumulative band widths, last omitted).
        points, acc = [], 0
        for d in dim_inputs[:-1]:
            acc += d
            points.append(acc)
        self.split_points = points
        for i, dim_in in enumerate(dim_inputs):
            setattr(self, f"to_features_{i}", BandSplitModule(dim_in, dim))

    def __call__(self, x: mx.array) -> mx.array:
        splits = mx.split(x, self.split_points, axis=-1)
        outs = [getattr(self, f"to_features_{i}")(s) for i, s in enumerate(splits)]
        return mx.stack(outs, axis=-2)  # (b, t, bands, dim)


def _mlp(dim_in: int, dim_out: int, dim_hidden: int, depth: int) -> nn.Sequential:
    """Linear/Tanh MLP held in a Sequential (layers.N) for name parity."""
    dims = (dim_in, *([dim_hidden] * (depth - 1)), dim_out)
    layers: list[nn.Module] = []
    for j, (a, b) in enumerate(zip(dims[:-1], dims[1:])):
        layers.append(nn.Linear(a, b))
        if j < len(dims) - 2:
            layers.append(nn.Tanh())
    return nn.Sequential(*layers)


class MaskEstimator(nn.Module):
    """Per-band MLP producing a gated (GLU) complex mask for one stem."""

    def __init__(self, dim: int, dim_inputs: tuple[int, ...], depth: int, mlp_expansion_factor: int = 4):
        super().__init__()
        self.dim_inputs = dim_inputs
        hidden = dim * mlp_expansion_factor
        for i, dim_in in enumerate(dim_inputs):
            setattr(self, f"to_freqs_{i}", _mlp(dim, dim_in * 2, hidden, depth))

    def __call__(self, x: mx.array) -> mx.array:
        outs = []
        for i in range(x.shape[-2]):
            out = getattr(self, f"to_freqs_{i}")(x[..., i, :])
            value, gate = mx.split(out, 2, axis=-1)
            outs.append(value * mx.sigmoid(gate))
        return mx.concatenate(outs, axis=-1)


class BSRoformerBlock(nn.Module):
    """Container for one block's transformers; the iteration logic lives in the model."""

    def __init__(self, time_transformer: Transformer, freq_transformer: Transformer,
                 linear_transformer: Transformer | None = None):
        super().__init__()
        self.has_linear = linear_transformer is not None
        if linear_transformer is not None:
            self.linear_transformer = linear_transformer
        self.time_transformer = time_transformer
        self.freq_transformer = freq_transformer


class BSRoformer(nn.Module):
    """Band-Split RoFormer: STFT -> band split -> time/freq transformers -> per-stem masks -> iSTFT."""

    def __init__(self, dim: int, *, depth: int, stereo: bool = False, num_stems: int = 1,
                 time_transformer_depth: int = 2, freq_transformer_depth: int = 2,
                 linear_transformer_depth: int = 0,
                 freqs_per_bands: tuple[int, ...] = DEFAULT_FREQS_PER_BANDS,
                 dim_head: int = 64, heads: int = 8, attn_dropout: float = 0.0,
                 ff_dropout: float = 0.0, ff_mult: int = 4, mlp_expansion_factor: int = 4,
                 mask_estimator_depth: int = 2, stft_n_fft: int = 2048,
                 stft_hop_length: int = 512, stft_win_length: int = 2048,
                 stft_normalized: bool = False, **_ignored):
        super().__init__()
        self.dim = dim
        self.depth = depth
        self.stereo = stereo
        self.audio_channels = 2 if stereo else 1
        self.num_stems = num_stems

        expected = stft_n_fft // 2 + 1
        if sum(freqs_per_bands) != expected:
            raise ValueError(f"freqs_per_bands must sum to {expected}, got {sum(freqs_per_bands)}")

        self._stft = get_transform_mlx(
            n_fft=stft_n_fft, hop_length=stft_hop_length, win_length=stft_win_length,
            window_fn="hann", window=None, periodic=True, center=True, normalized=stft_normalized,
        )

        # The transformer feed-forward expansion (ff_mult) is fixed by the architecture
        # and is independent of mlp_expansion_factor, which sizes only the mask-estimator
        # MLP. Conflating them breaks checkpoints where the two differ (e.g. the 53-stem).
        tkw = dict(dim=dim, heads=heads, dim_head=dim_head, ff_mult=ff_mult,
                   attn_dropout=attn_dropout, ff_dropout=ff_dropout, norm_output=False)
        for i in range(depth):
            linear = (Transformer(depth=linear_transformer_depth, **tkw)
                      if linear_transformer_depth > 0 else None)
            time = Transformer(depth=time_transformer_depth, **tkw)
            freq = Transformer(depth=freq_transformer_depth, **tkw)
            setattr(self, f"layers_{i}", BSRoformerBlock(time, freq, linear))
        self.final_norm = L2Norm(dim)

        # Each band carries real+imag for every audio channel.
        band_dims = tuple(2 * f * self.audio_channels for f in freqs_per_bands)
        self.band_split = BandSplit(dim=dim, dim_inputs=band_dims)
        for i in range(num_stems):
            setattr(self, f"mask_estimators_{i}",
                    MaskEstimator(dim, band_dims, mask_estimator_depth, mlp_expansion_factor))

    def _transformers(self, x: mx.array) -> mx.array:
        """Run each block: optional linear, then time, then frequency transformer."""
        for i in range(self.depth):
            block = getattr(self, f"layers_{i}")
            if block.has_linear:
                b, t, f, d = x.shape
                x = block.linear_transformer(x.reshape(b, t * f, d)).reshape(b, t, f, d)
            b, t, f, d = x.shape
            # Time: attend across t for each band.
            x = x.transpose(0, 2, 1, 3).reshape(b * f, t, d)
            x = block.time_transformer(x).reshape(b, f, t, d).transpose(0, 2, 1, 3)
            # Frequency: attend across bands for each time step.
            x = x.reshape(b * t, f, d)
            x = block.freq_transformer(x).reshape(b, t, f, d)
        return self.final_norm(x)

    @property
    def neural_dtype(self) -> mx.Dtype:
        """Precision of the dense stack, taken live from the loaded weights.

        The band-split, transformers, and mask estimators run in whatever dtype the
        weights carry (fp32 for an exact reference, bf16 for ~1.4x faster inference).
        The STFT/iSTFT always stay fp32: the FFT is weightless and gains nothing from
        bf16 while losing spectral accuracy, so precision here is "mixed" by design.
        """
        return self.band_split.to_features_0.linear.weight.dtype

    def _masks(self, stft_repr: mx.array) -> mx.array:
        """STFT representation (b, f*c, t, 2) -> complex masks (b, n, f*c, t, 2)."""
        b, fc, t, _ = stft_repr.shape
        x = stft_repr.transpose(0, 2, 1, 3).reshape(b, t, fc * 2)  # (b, t, f*c*2)
        x = x.astype(self.neural_dtype)  # run the dense stack in the weight precision
        x = self.band_split(x)
        x = self._transformers(x)
        masks = mx.stack([getattr(self, f"mask_estimators_{i}")(x) for i in range(self.num_stems)], axis=1)
        # (b, n, t, f*c*2) -> (b, n, f*c, t, 2); back to fp32 for the iSTFT
        return masks.reshape(b, self.num_stems, t, fc, 2).transpose(0, 1, 3, 2, 4).astype(mx.float32)

    def __call__(self, raw_audio: mx.array) -> mx.array:
        """(b, c, t) -> (b, num_stems, c, t) separated audio (or (b, c, t) when num_stems == 1)."""
        if raw_audio.ndim == 2:
            raw_audio = raw_audio[:, None, :]
        b, c, t = raw_audio.shape
        if c != self.audio_channels:
            raise ValueError(f"expected {self.audio_channels} channel(s), got {c}")

        spec = self._stft.stft(raw_audio.astype(mx.float32).reshape(b * c, t))  # fp32 STFT
        spec = mx.stack([spec.real, spec.imag], axis=-1)  # (b*c, F, N, 2)
        f, n = spec.shape[1], spec.shape[2]
        # (b*c, F, N, 2) -> (b, F*c, N, 2)
        spec = spec.reshape(b, c, f, n, 2).transpose(0, 2, 1, 3, 4).reshape(b, f * c, n, 2)

        masks = self._masks(spec)
        stft_c = spec[:, None, ..., 0] + 1j * spec[:, None, ..., 1]  # (b, 1, f*c, n)
        mask_c = masks[..., 0] + 1j * masks[..., 1]  # (b, n_stems, f*c, n)
        masked = stft_c * mask_c  # (b, n_stems, f*c, n)

        # (b, n, f*c, N) -> (b*n*c, F, N) for iSTFT
        masked = masked.reshape(b, self.num_stems, f, c, n).transpose(0, 1, 3, 2, 4)
        masked = masked.reshape(b * self.num_stems * c, f, n)
        audio = self._stft.istft(masked, length=t)  # (b*n*c, t)
        audio = audio.reshape(b, self.num_stems, c, t)
        return audio[:, 0] if self.num_stems == 1 else audio
