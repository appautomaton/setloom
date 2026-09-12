# SPDX-License-Identifier: AGPL-3.0-only
"""Small warm FM/additive tine instrument, driven by editable notes and CC11."""
import collections
import mido
import numpy as np
from scipy.signal import butter, sosfilt


def read_performance(full):
    track = next(tr for tr in full.tracks if tr.name == 'electric_piano')
    assert {e.channel for e in track if hasattr(e, 'channel')} == {12}
    tick = 0; active = collections.defaultdict(collections.deque)
    notes = []; expression = [[0, 0]]
    for event in track:
        tick += event.time
        seconds = mido.tick2second(tick, full.ticks_per_beat, 400000)
        if event.type == 'note_on' and event.velocity:
            active[event.note].append((seconds, event.velocity))
        elif event.type == 'note_off' or (event.type == 'note_on' and not event.velocity):
            assert active[event.note], 'Unmatched EP note-off'
            start, velocity = active[event.note].popleft()
            assert seconds > start
            notes.append((start, seconds, event.note, velocity))
        elif event.type == 'control_change':
            if event.control != 11: raise ValueError('The EP supports editable CC11 expression only')
            expression.append([seconds, event.value])
        elif not event.is_meta:
            raise ValueError(f'Unsupported EP event {event.type}')
    assert not any(active.values()), 'Unclosed EP note'
    return sorted(notes), expression


def synthesize(full, patch, frames, sr):
    notes, expression = read_performance(full)
    output = np.zeros((frames, 2))
    for onset, off, key, velocity in notes:
        begin = round(onset*sr)
        end = min(frames, round((off+patch['release_seconds'])*sr))
        if begin >= end: continue
        time = np.arange(end-begin)/sr
        frequency = 440*2**((key-69)/12)
        phase = 2*np.pi*frequency*time
        strength = velocity/100
        index = (patch['fm_index_soft']+strength*patch['fm_index_velocity'])*np.exp(-time/patch['fm_index_decay_seconds'])
        body = .72*np.sin(phase+index*np.sin(phase*patch['fm_ratio']))
        body += .22*np.sin(phase)+.08*np.sin(2*phase)*np.exp(-time/.55)
        tine = np.sin(phase*patch['tine_ratio']+patch['tine_mod_index']*np.sin(phase*patch['tine_mod_ratio']))
        tine *= patch['tine_gain']*strength*np.exp(-time/patch['tine_decay_seconds'])
        attack = np.sin(np.pi/2*np.clip(time/(patch['attack_ms']/1000), 0, 1))**2
        envelope = .78*np.exp(-time/patch['decay_seconds'])+.22*np.exp(-time/patch['sustain_decay_seconds'])
        release_age = np.maximum(time-(off-onset), 0)
        release = np.exp(-release_age/patch['release_decay_seconds'])*np.clip((patch['release_seconds']-release_age)/.012, 0, 1)
        wave = (body+tine)*attack*envelope*release*strength**patch['velocity_exponent']
        pan = np.clip((key-60)/16, -1, 1)*patch['stereo_width']
        output[begin:end] += wave[:, None]*np.array([np.sqrt((1-pan)/2), np.sqrt((1+pan)/2)])
    output = sosfilt(butter(2, [patch['highpass_hz'], patch['lowpass_hz']], btype='bandpass', fs=sr, output='sos'), output, axis=0)
    time = np.arange(frames)/sr
    # Interpolating the stored CC11 is deliberate continuous expression.
    level = np.interp(time, *np.asarray(expression).T)/127
    output *= (level*10**(patch['gain_db']/20))[:, None]
    dry = output.copy()
    for channel, delay_ms in enumerate(patch['ambience_delays_ms']):
        delay = round(delay_ms*sr/1000)
        output[delay:, channel] += dry[:-delay, 1-channel]*patch['ambience_wet']
        output[:, channel] *= 1+patch['tremolo_depth']*np.sin(2*np.pi*patch['tremolo_hz']*time+channel*.35)
    return output
