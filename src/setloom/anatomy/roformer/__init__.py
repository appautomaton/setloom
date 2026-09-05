# SPDX-License-Identifier: AGPL-3.0-only
"""MLX BS-RoFormer separation model and Setloom's inference wrapper.

`model.py` is a native MLX reimplementation of the band-split RoFormer; `weights.py`
converts upstream PyTorch checkpoints into the MLX module tree (and caches the
result as safetensors); `separate.py` is the harness-facing config/build/infer API.
The architecture follows lucidrains' BS-RoFormer and the port references ssmall256's
mlx-audio-separator (both MIT; see LICENSES/NOTICE).

This package is the only place the 53-stem model framework exists in the tree.
Nothing outside ``setloom.anatomy.layers`` should import it, and the MLX and torch
backends are heavy, so imports must stay lazy upstream.
"""
