# SPDX-License-Identifier: AGPL-3.0-only
"""Route the actual piano MIDI to the locally installed sampled grand."""
import subprocess
from pathlib import Path

import mido
import numpy as np
import soundfile as sf
from scipy.signal import butter, resample_poly, sosfilt


def split_performance(path, scratch):
    """Retain all event timing; synthesize piano programs/controllers as MIDI."""
    performance = mido.MidiFile(path)
    piano_tracks = [tr for tr in performance.tracks if tr.name == 'piano']
    if len(piano_tracks) != 1:
        raise ValueError('Expected exactly one piano track')
    piano_track = piano_tracks[0]
    if {m.channel for m in piano_track if hasattr(m, 'channel')} != {8}:
        raise ValueError('Piano must use its dedicated channel 8')
    accepted = mido.MidiFile(type=1, ticks_per_beat=performance.ticks_per_beat)
    accepted.tracks = [tr for tr in performance.tracks if tr is not piano_track]
    if any(m.channel == 8 for tr in accepted.tracks for m in tr if hasattr(m, 'channel')):
        raise ValueError('Piano channel collides with accepted music')
    accepted_path = scratch / 'accepted.mid'
    accepted.save(accepted_path)
    # Tempo changes can occur in any track, so explicitly collect the global map.
    tempo_events = []
    end_tick = 0
    for ti, tr in enumerate(performance.tracks):
        tick = 0
        for ei, event in enumerate(tr):
            tick += event.time
            if event.type in ('set_tempo', 'time_signature'):
                tempo_events.append((tick, ti, ei, event))
        end_tick = max(end_tick, tick)
    tempo_track = mido.MidiTrack()
    previous = 0
    for tick, _, _, event in sorted(tempo_events, key=lambda row: row[:3]):
        tempo_track.append(event.copy(time=tick - previous))
        previous = tick
    tempo_track.append(mido.MetaMessage('end_of_track', time=end_tick - previous))
    piano = mido.MidiFile(type=1, ticks_per_beat=performance.ticks_per_beat)
    piano.tracks = [tempo_track, piano_track]
    piano_path = scratch / 'piano.mid'
    piano.save(piano_path)
    return accepted_path, piano_path


def synthesize(piano_midi, patch, repo, scratch, frames, sr):
    soundfont = repo / patch['soundfont']
    raw_path = scratch / 'piano-dry.wav'
    command = [patch['fluidsynth'], '-ni', '-r', '48000', '-g', str(patch['engine_gain']),
               '-R', '0', '-C', '0', '-o', 'synth.polyphony=256', '-T', 'wav',
               '-O', 'float', '-F', str(raw_path), str(soundfont), str(piano_midi)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    audio, source_sr = sf.read(raw_path, dtype='float32', always_2d=True)
    dry_peak = float(np.max(np.abs(audio)))
    dry_clipped = int(np.sum(np.abs(audio) >= 1))
    assert source_sr == 48000 and sr == 44100
    audio = resample_poly(audio, 147, 160, axis=0).astype(np.float32)
    audio = audio[:frames]
    if len(audio) < frames:
        audio = np.pad(audio, ((0, frames - len(audio)), (0, 0)))
    audio = sosfilt(butter(2, patch['highpass_hz'], fs=sr, btype='highpass', output='sos'), audio, axis=0)
    audio = sosfilt(butter(2, patch['lowpass_hz'], fs=sr, output='sos'), audio, axis=0)
    audio *= 10 ** (patch['bus_gain_db'] / 20)
    return audio, {'engine_command': command, 'instrument_sample': str(soundfont),
                   'license': patch['license'],
                   'credit': patch['credit'], 'dry_sample_peak': dry_peak,
                   'dry_clipped_samples': dry_clipped,
                   'piano_sample_peak': float(np.max(np.abs(audio)))}
