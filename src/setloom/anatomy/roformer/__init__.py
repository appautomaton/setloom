# SPDX-License-Identifier: AGPL-3.0-only
"""Vendored BS-RoFormer separation model and Setloom's inference wrapper.

`bs_roformer.py` and `attend.py` are vendored MIT-licensed code (see their
headers); `infer.py` is Setloom code. This package is the only place the
53-stem model framework exists in the tree — nothing outside
``setloom.anatomy.layers`` should import it, and everything here is
torch-heavy by nature, so imports must stay lazy upstream.
"""
