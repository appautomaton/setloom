<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Dossier Guide: Technical Evidence Only

`setloom anatomize --layers` writes local dossiers, layer stems, and approximate
MIDI transcriptions. Those files are useful technical evidence, but they are
not musical truth.

For new reference study, start with timestamped listening notes. Machine
reports are not style evidence and must not become durable musical contracts.

## Boundary

| Output | Meaning |
| --- | --- |
| `<track>.quick.yml` | Full-mix technical cache: tempo estimate, loudness, key guess, section heuristic |
| `<track>.layers.yml` | Active 53-stem layer lens; overlapping extractions, not a mix partition |
| `<track>.*.mid` | Approximate monophonic transcriptions for inspection |
| `<track>.score.yml` | Technical distance report against current pack targets, when targets exist |
| `corpus-summary.yml` | Aggregate cache; never a taste verdict |

## Reading Rule

Use dossiers to ask better listening questions:

```text
measurement -> what should we listen for? -> human note -> rebuild decision
```

Do not use dossiers to decide that a candidate is good, bad, authentic, or
inauthentic. The listening gate owns that decision.
