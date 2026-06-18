# SPDX-License-Identifier: AGPL-3.0-only
"""Reference-track anatomy: measurement, transcription, and diagnostics.

Import layering contract: `analysis` and `corpus` are pure numpy math and
stay cheap to import. `layers` owns the active 53-stem reference lens.
`pipeline` orchestrates and loads audio via librosa/soundfile. This package
is opt-in: only the `anatomize` and `score` CLI commands import it.
"""
