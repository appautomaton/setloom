#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Convert Spotify's ICASSP 2022 ONNX export to self-contained FP32 MLX assets.

No model execution or MLX import is needed. All tensor changes are lossless
layout permutations; the stored CQT filters and fused BN parameters are retained.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

SUPPORTED_SOURCE_SHA256 = "2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec"

HEADS = {
    "contour_features": ((8, 8, 3, 39), [1, 1], [1, 19, 1, 19]),
    "contour": ((1, 8, 5, 5), [1, 1], [2, 2, 2, 2]),
    "note_features": ((32, 1, 7, 7), [1, 3], [3, 2, 3, 2]),
    "note": ((1, 32, 7, 3), [1, 1], [3, 1, 3, 1]),
    "onset_features": ((32, 8, 5, 5), [1, 3], [2, 1, 2, 1]),
    "onset": ((1, 33, 3, 3), [1, 1], [1, 1, 1, 1]),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def convert(source: Path, output: Path) -> dict:
    import onnx
    from onnx import helper, numpy_helper
    from safetensors.numpy import load_file, save_file

    if sha256(source) != SUPPORTED_SOURCE_SHA256:
        raise ValueError(
            "Unsupported ONNX release: this converter targets the canonical "
            "Spotify ICASSP 2022 nmp.onnx; a different graph needs explicit port review"
        )
    model = onnx.load(str(source))
    onnx.checker.check_model(model)
    initializers = {
        tensor.name: numpy_helper.to_array(tensor) for tensor in model.graph.initializer
    }
    nodes = list(model.graph.node)
    counts = Counter(node.op_type for node in nodes)
    if counts["Conv"] != 32 or counts["Log"] != 1 or counts["Sigmoid"] != 3:
        raise ValueError("Source is not the supported ICASSP 2022 Basic Pitch architecture")
    input_shape = [dim.dim_value for dim in model.graph.input[0].type.tensor_type.shape.dim]
    if len(model.graph.input) != 1 or input_shape[-2:] != [43844, 1]:
        raise ValueError(f"Unexpected Basic Pitch input shape: {input_shape}")
    if {o.name for o in model.graph.output} != {f"StatefulPartitionedCall:{i}" for i in range(3)}:
        raise ValueError("Unexpected Basic Pitch output schema")
    weights, provenance = {}, {}

    def store(name, source_name, transform=None):
        value = initializers[source_name]
        if value.dtype != np.float32:
            raise ValueError(f"Expected original FP32 initializer: {source_name}")
        converted = value if transform is None else transform(value)
        weights[name] = np.ascontiguousarray(converted) if converted.ndim else converted.copy()
        provenance[name] = {
            "source_initializer": source_name,
            "source_shape": list(value.shape),
            "stored_shape": list(converted.shape),
            "dtype": "float32",
            "source_sha256": hashlib.sha256(value.tobytes()).hexdigest(),
            "stored_sha256": hashlib.sha256(converted.tobytes()).hexdigest(),
        }

    def unique(predicate):
        found = [node for node in nodes if predicate(node)]
        if len(found) != 1:
            raise ValueError(
                f"Unsupported source graph: expected one semantic node, found {len(found)}"
            )
        return found[0]

    convs = [n for n in nodes if n.op_type == "Conv"]
    config = {
        "architecture": "basic-pitch-icassp-2022-mlx-fp32-v1",
        "input_shape": [1, 43844, 1],
        "sample_rate": 22050,
        "output_shapes": {"note": [1, 172, 88], "onset": [1, 172, 88], "contour": [1, 172, 264]},
        "heads": {},
        "cqt": {
            "hops": [256, 128, 64, 32, 16, 8, 4, 2, 1],
            "bins": 309,
            "reflect_pad": 128,
            "downsample_pad": 127,
        },
        "harmonic_shifts": [-36, 0, 36, 57, 72, 84, 93, 101],
    }
    for name, (shape, strides, pads) in HEADS.items():
        node = unique(lambda n: n.op_type == "Conv" and initializers[n.input[1]].shape == shape)
        attrs = {a.name: helper.get_attribute_value(a) for a in node.attribute}
        if attrs.get("strides") != strides or attrs.get("pads") != pads:
            raise ValueError(f"Unexpected convolution padding/stride: {name}")
        if attrs.get("group", 1) != 1 or attrs.get("dilations", [1, 1]) != [1, 1]:
            raise ValueError(f"Unsupported convolution grouping/dilation: {name}")
        if initializers[node.input[2]].shape != (shape[0],):
            raise ValueError(f"Unexpected bias shape: {name}")
        store(f"{name}.weight", node.input[1], lambda a: a.transpose(0, 2, 3, 1))
        store(f"{name}.bias", node.input[2])
        config["heads"][name] = {"strides": strides, "pads": pads}
    for name, suffix in (("real", "/conv1d"), ("imag", "/conv1d_1"), ("lowpass", "/conv1d_2")):
        node = unique(lambda n: n.op_type == "Conv" and n.name.split(";")[0].endswith(suffix))
        expected = (1 if name == "lowpass" else 36, 1, 1, 256)
        if initializers[node.input[1]].shape != expected or np.any(initializers[node.input[2]]):
            raise ValueError(f"Unexpected CQT filter/bias: {name}")
        store(f"cqt.{name}", node.input[1], lambda a: a[:, 0, 0, :, None])
    cqt_convs = [n for n in convs if "cq_t2010v2" in n.name]
    for node in cqt_convs:
        attrs = {a.name: helper.get_attribute_value(a) for a in node.attribute}
        if attrs.get("kernel_shape") != [1, 256] or attrs.get("pads", [0] * 4) != [0] * 4:
            raise ValueError("Unexpected CQT convolution geometry")
        if node.input[1] not in {
            provenance[f"cqt.{key}"]["source_initializer"] for key in ("real", "imag", "lowpass")
        }:
            raise ValueError("CQT octaves must share the stored filters")
    prefix = "model_1/cq_t2010v2_1/Sqrt"
    store("cqt.scale", prefix + ";" + prefix, lambda a: a.reshape(1, 1, 309, 1))
    scalar_nodes = {
        "normalization.epsilon": ("Add", "model_1/normalized_log_1/add;"),
        "normalization.log_multiplier": ("Mul", "model_1/normalized_log_1/truediv;"),
        "normalization.db_multiplier": ("Mul", "model_1/normalized_log_1/mul;"),
        "cqt.bn_scale": ("Mul", "model_1/batch_normalization/FusedBatchNormV3;"),
        "cqt.bn_bias": ("Add", "model_1/batch_normalization/FusedBatchNormV3;"),
    }
    for name, (op, prefix) in scalar_nodes.items():
        node = unique(lambda n: n.op_type == op and n.name.startswith(prefix))
        store(name, node.input[1])
    output.mkdir(parents=True, exist_ok=True)
    save_file(dict(sorted(weights.items())), str(output / "model.safetensors"))
    # Verify serialization retains every FP32 bit, including signed zero.
    reloaded = load_file(str(output / "model.safetensors"))
    for key, value in weights.items():
        if reloaded[key].tobytes() != value.tobytes() or reloaded[key].shape != value.shape:
            raise RuntimeError(f"Lossless safetensors round-trip failed: {key}")
    (output / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    manifest = {
        "format_version": 1,
        "source": {
            "filename": source.name,
            "sha256": sha256(source),
            "producer": model.producer_name,
            "opset": [{"domain": o.domain, "version": o.version} for o in model.opset_import],
        },
        "conversion": "FP32 layout permutations only; no quantization",
        "files": {name: sha256(output / name) for name in ("config.json", "model.safetensors")},
        "tensors": provenance,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("models/basic-pitch-mlx/icassp_2022"))
    args = parser.parse_args()
    manifest = convert(args.source, args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "source_sha256": manifest["source"]["sha256"],
                "fp32_tensors": len(manifest["tensors"]),
            },
            indent=2,
        )
    )
