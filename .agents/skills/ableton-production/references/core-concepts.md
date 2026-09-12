# Live objects and units

Session clip slots and Arrangement clips have different identities and indexes.
Use the objects returned by the relevant query; a track name or UI position does
not identify a clip reliably after edits.

The local bridge expresses musical positions and durations in beats. Audio
inspection uses file seconds. Preserve tempo and timeline origin when moving
between them, including pickup offsets and clip start/loop settings.

The current bridge can insert Arrangement MIDI by copying a Session clip.
That is an interface path, not a requirement to compose or sketch in Session
View. Inspect the current tool schema when another editing path is needed.

Master processing affects the whole mix, and return processing affects every
sending part. Work within the existing authorization and evaluate their effect
on the ensemble; these track types do not require a separate approval ritual.

Choose devices from the actual Set and browser. Verify parameter ranges, units
and mappings before using automation; a numeric control value need not represent
Hz, dB or a MIDI controller value directly.
