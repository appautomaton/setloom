# SPDX-License-Identifier: AGPL-3.0-only
"""Reference-track anatomy: measurement, transcription, and corpus grammar.

Import layering contract: `analysis` and `corpus` are pure numpy math and
stay cheap to import. `separate` is the only module allowed to import
demucs/torch. `pipeline` orchestrates and loads audio via librosa/soundfile.
Keep this package out of the `setloom generate` import path.
"""
