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
                        bodyHi=92, bodyLo=43, bodyTime=0.10, drive=1.8|
    var pitch, body, click, env, sig;
    // Fixed noise seed: PinkNoise must render byte-identically across runs.
    RandSeed.ir(1, 47);
    pitch = EnvGen.kr(Env([bodyHi, bodyLo], [bodyTime], -7));
    body = SinOsc.ar(pitch);
    click = HPF.ar(Impulse.ar(0) + (PinkNoise.ar(0.4) *
        EnvGen.kr(Env.perc(0.0005, 0.008))), 1400) * 0.22;
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
                        harm=0.10, cutoff=290, pumpDepth=0.6|
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
                       detune=0.005, cutoff=850, bloom=3.5, pumpDepth=0.38,
                       verbMix=0.30|
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
}),

// vibe_chords — dark stab/swell hybrid: 3-voice detuned saw, filter envelope
// scaled by note length (short notes pluck, long notes bloom), dry-leaning.
//   cutoff:   ceiling of the filter envelope (darkness)
//   pluck:    filter decay for short stabs (seconds)
//   verbMix:  small room amount
SynthDef(\vibe_chords, { |out=0, freq=220, amp=0.6, sustain=0.3, pumpRate=2.066,
                          cutoff=1100, pluck=0.18, verbMix=0.18|
    var stab, ratios, saws, fenv, env, sig;
    stab = sustain < 1.0;
    ratios = [0.996, 1, 1.004];
    saws = Mix(ratios.collect { |r| Saw.ar(freq * r) * 0.3 });
    fenv = EnvGen.kr(Env([cutoff, cutoff * 0.25], [Select.kr(stab, [sustain * 0.8, pluck])], -3));
    env = EnvGen.kr(Env.linen(0.004, (sustain - 0.06).max(0.02), 0.05), doneAction: 2);
    sig = LPF.ar(saws, fenv.max(120)) * env * amp;
    sig = FreeVerb.ar(sig, verbMix, 0.7, 0.5);
    Out.ar(out, sig ! 2);
}),

// vibe_lead — delayed pluck (the T01 palette: "delayed pluck motif, sparse and
// emotional"): sine+saw blend, fast filter decay, dotted-8th feedback delay.
//   delayBeats: echo spacing in beats (0.75 = dotted 8th)
//   decay:      echo tail length (seconds)
SynthDef(\vibe_lead, { |out=0, freq=440, amp=0.6, sustain=0.4, pumpRate=2.066,
                        delayBeats=0.75, decay=2.2, cutoff=2400|
    var pluckEnv, tone, delayTime, sig, env;
    pluckEnv = EnvGen.kr(Env.perc(0.002, 0.5, 1, -5));
    tone = (SinOsc.ar(freq) * 0.6) + (Saw.ar(freq) * 0.25);
    tone = LPF.ar(tone, (cutoff * pluckEnv).max(300));
    delayTime = delayBeats / pumpRate;
    sig = tone * pluckEnv;
    sig = sig + CombC.ar(sig, 1.0, delayTime, decay, 0.45);
    env = EnvGen.kr(Env.linen(0.001, sustain.max(0.3) + decay, 0.4), doneAction: 2);
    sig = sig * env * amp;
    Out.ar(out, Pan2.ar(sig, 0));
}),

// vibe_arp — metallic pluck: detuned pulse, tight filter snap, short comb
// shimmer; sits behind the lead.
SynthDef(\vibe_arp, { |out=0, freq=440, amp=0.5, sustain=0.12, pumpRate=2.066,
                       cutoff=1900, snap=0.07|
    var env, tone, sig;
    env = EnvGen.kr(Env.perc(0.001, sustain.max(0.1) + 0.12, 1, -6), doneAction: 2);
    tone = (Pulse.ar(freq, 0.35) * 0.4) + (Pulse.ar(freq * 1.005, 0.35) * 0.3);
    tone = LPF.ar(tone, (cutoff * EnvGen.kr(Env.perc(0.001, snap))).max(400));
    sig = tone + CombC.ar(tone, 0.3, 0.25 / pumpRate, 0.8, 0.3);
    Out.ar(out, (sig * env * amp) ! 2);
}),

// vibe_fx — noise riser grains + boom impact. Low notes (impact register,
// octave <= 1) become a sine boom; higher notes are bandpassed noise hits whose
// center follows the chromatic run, so risers read as a rising noise roll.
SynthDef(\vibe_fx, { |out=0, freq=440, amp=0.7, sustain=0.12, pumpRate=2.066|
    var isBoom, noiseEnv, noise, boomEnv, boom, sig;
    RandSeed.ir(1, 47);
    isBoom = freq < 60;
    noiseEnv = EnvGen.kr(Env.perc(0.002, sustain.max(0.1), 1, -4));
    noise = BPF.ar(WhiteNoise.ar(1), freq.max(180) * 6, 0.6) * noiseEnv * 0.8;
    boomEnv = EnvGen.kr(Env.perc(0.004, sustain.max(0.8), 1, -6));
    boom = (SinOsc.ar(EnvGen.kr(Env([70, 38], [0.12], -4))) * 1.6).tanh * boomEnv;
    sig = Select.ar(isBoom, [noise, boom]);
    EnvGen.kr(Env.linen(0.001, sustain.max(0.8) + 0.3, 0.2), doneAction: 2);
    Out.ar(out, (sig * amp) ! 2);
})
]
