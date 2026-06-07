// SPDX-License-Identifier: AGPL-3.0-only
//
// Setloom vibe patches v1 — the three vibe-bearing timbres (kick, bass, pad)
// for the melodic/progressive techno style pack. Patches are executable
// sound-design recipes: every "knob" is a commented arg so listening feedback
// maps to named parameters. No random UGens: renders are deterministic.
//
// This file EVALUATES TO an Array of SynthDefs; the render driver loads it
// with .load and injects each def into the NRT score via /d_recv.
//
// Shared args: out (bus), freq (Hz), amp (0-1 from MIDI velocity),
// sustain (seconds), pumpRate (beats per second = bpm/60).

[
// vibe_kick — synthesized club kick: pitch-dropping sine body + click + drive.
//   bodyHi/bodyLo: pitch envelope start/end (higher = punchier, lower = deeper)
//   bodyTime:     pitch drop time; longer = boomier
//   drive:        tanh saturation amount; more = denser/darker
SynthDef(\vibe_kick, { |out=0, freq=50, amp=0.9, sustain=0.3,
                        bodyHi=108, bodyLo=46, bodyTime=0.085, drive=2.2|
    var pitch, body, click, env, sig;
    // Fixed noise seed: PinkNoise must render byte-identically across runs.
    RandSeed.ir(1, 47);
    pitch = EnvGen.kr(Env([bodyHi, bodyLo], [bodyTime], -7));
    body = SinOsc.ar(pitch);
    click = HPF.ar(Impulse.ar(0) + (PinkNoise.ar(0.4) *
        EnvGen.kr(Env.perc(0.0005, 0.012))), 900) * 0.5;
    env = EnvGen.kr(Env.perc(0.0015, sustain.min(0.4), 1, -6), doneAction: 2);
    sig = ((body + click) * drive).tanh * env * amp;
    Out.ar(out, sig ! 2);
}),

// vibe_bass — mono sub: sine fundamental + saturated low harmonic, dark LPF,
// beat-synced pump leaving kick space.
//   harm:      level of the saturated octave harmonic (presence without brightness)
//   cutoff:    lowpass ceiling; lower = darker
//   pumpDepth: sidechain duck depth (0 none, 1 full duck)
SynthDef(\vibe_bass, { |out=0, freq=55, amp=0.8, sustain=0.2, pumpRate=2.066,
                        harm=0.22, cutoff=420, pumpDepth=0.6|
    var duck = LFSaw.kr(pumpRate, 1).range(0, 1).pow(0.35);
    var pump = 1 - (pumpDepth * (1 - duck));
    var sub = SinOsc.ar(freq);
    var grit = (Pulse.ar(freq * 2, 0.5) * 0.8).tanh * harm;
    var env = EnvGen.kr(Env.linen(0.004, (sustain - 0.03).max(0.01), 0.03), doneAction: 2);
    var sig = LPF.ar(((sub + grit) * 1.6).tanh, cutoff) * env * amp * pump;
    Out.ar(out, sig ! 2);
}),

// vibe_pad — wide dark pad: fixed-ratio detuned saw stack, slow filter bloom,
// gentle pump, reverb tail baked into the stem.
//   detune:    spread of the saw stack (wider = lusher)
//   cutoff:    filter ceiling; the "darkness" knob
//   bloom:     seconds for the filter to open after note start
//   pumpDepth: gentler than bass so the bed breathes, not gasps
//   verbMix:   reverb wet amount (space)
SynthDef(\vibe_pad, { |out=0, freq=220, amp=0.5, sustain=4.0, pumpRate=2.066,
                       detune=0.006, cutoff=1500, bloom=2.5, pumpDepth=0.42,
                       verbMix=0.38|
    var ratios = [1 - detune, 1 - (detune * 0.5), 1, 1 + (detune * 0.5), 1 + detune];
    var saws = Mix(ratios.collect { |r| Saw.ar(freq * r) * 0.2 });
    var duck = LFSaw.kr(pumpRate, 1).range(0, 1).pow(0.5);
    var pump = 1 - (pumpDepth * (1 - duck));
    var open = EnvGen.kr(Env([cutoff * 0.3, cutoff], [bloom], \sin));
    var env = EnvGen.kr(
        Env.linen(1.2, (sustain - 3.0).max(0.5), 1.8, 1, \sin), doneAction: 2);
    var sig = LPF.ar(saws, open) * env * amp * pump;
    sig = FreeVerb2.ar(sig, sig, verbMix, 0.86, 0.4);
    Out.ar(out, [sig[0], sig[1]]);
})
]
