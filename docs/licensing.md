<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Licensing

This document describes the intended licensing architecture for Setloom. It is project policy, not legal advice.

## License Summary

| Material | License |
| --- | --- |
| Core code | AGPL-3.0-only |
| Harness prompts | AGPL-3.0-only |
| Schemas and executable lane packs | AGPL-3.0-only |
| Automation logic | AGPL-3.0-only |
| Project documentation | CC BY-SA 4.0 |
| Generated audio, MIDI, stems, arrangements, and sets | Owned by the creator, subject to third-party inputs |
| Samples and model assets | Not included by default; must have explicit compatible licensing |

Canonical license texts are stored in `LICENSES/`.

## Hosted Services

Setloom is open source, but it is not intended for closed SaaS capture.

Hosted services that modify Setloom or integrate AGPL-covered Setloom components must comply with AGPL-3.0-only network source obligations.

Hosted forks must not imply they are official Setloom or AppAutomaton services without permission.

## Generated Outputs

Setloom does not claim ownership over user-generated music outputs.

Users may sell, release, perform, or share music they create with Setloom, subject to the licenses and rights of any third-party samples, models, prompts, references, or source material they choose to use.

## Samples

Do not add proprietary samples to the repository.

If sample assets are ever included, each asset must include clear license metadata. Prefer CC0 or similarly permissive material for example content.

## Models

Do not commit model weights to the repository.

Any optional model integration must document:

- model license;
- allowed commercial use;
- output terms;
- attribution requirements;
- whether the model is safe for generated music intended for release.

## Trademarks

`Setloom` and `AppAutomaton` names may be used to identify the project accurately.

Forks, hosted services, and downstream distributions may not present themselves as official Setloom or AppAutomaton services unless they have permission.

See `TRADEMARKS.md`.
