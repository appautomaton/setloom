// SPDX-License-Identifier: AGPL-3.0-only
//
// Setloom vibe patches v3 — designed timbres for the melodic/progressive
// techno pack. v3 applies the cross-model break critique (2026-06-07):
// continuous motion, stereo design, darker space, noise-air layer.
// Deterministic: every noise UGen is RandSeed'd; LFOs are phase-fixed.
//
// This file EVALUATES TO an Array of SynthDefs; the render driver loads it
// with .load and injects each def into the NRT score via /d_recv.
//
// Shared args: out, freq (Hz), amp (0-1), sustain (s), pumpRate (beats/s).

[
// vibe_kick — pitch-dropping sine body + click + tanh drive.
SynthDef(\vibe_kick, { |out=0, freq=50, amp=0.9, sustain=0.3,
                        bodyHi=92, bodyLo=43, bodyTime=0.10, drive=1.8|
    var pitch, body, click, env, sig;
    RandSeed.ir(1, 47);
    pitch = EnvGen.kr(Env([bodyHi, bodyLo], [bodyTime], -7));
    body = SinOsc.ar(pitch);
    click = HPF.ar(Impulse.ar(0) + (PinkNoise.ar(0.4) *
        EnvGen.kr(Env.perc(0.0005, 0.008))), 1400) * 0.22;
    env = EnvGen.kr(Env.perc(0.0015, sustain.min(0.4), 1, -6), doneAction: 2);
    sig = ((body + click) * drive).tanh * env * amp;
    Out.ar(out, sig ! 2);
}),

// vibe_bass — mono sub + saturated harmonic, dark LPF, beat-synced pump.
SynthDef(\vibe_bass, { |out=0, freq=55, amp=0.8, sustain=0.2, pumpRate=2.066,
                        harm=0.10, cutoff=290, pumpDepth=0.6|
    var duck, pump, sub, grit, env, sig;
    duck = LFSaw.kr(pumpRate, 1).range(0, 1).pow(0.35);
    pump = 1 - (pumpDepth * (1 - duck));
    sub = SinOsc.ar(freq);
    grit = (Pulse.ar(freq * 2, 0.5) * 0.8).tanh * harm;
    env = EnvGen.kr(Env.linen(0.004, (sustain - 0.03).max(0.01), 0.03), doneAction: 2);
    sig = LPF.ar(((sub + grit) * 1.6).tanh, cutoff) * env * amp * pump;
    Out.ar(out, sig ! 2);
}),

// vibe_pad — dark wide MOVING pad: detuned saws, filter bloom + slow cutoff
// wander (anti-static fix), DelayC stereo chorus, seeded noise-air bed,
// GVerb dark space, high-shelf rolloff.
//   cutoff: darkness ceiling | bloom: open time | verbMix: GVerb wet
//   airLevel: noise-air bed level (felt, not heard)
SynthDef(\vibe_pad, { |out=0, freq=220, amp=0.5, sustain=4.0, pumpRate=2.066,
                       detune=0.005, cutoff=850, bloom=3.5, pumpDepth=0.38,
                       verbMix=0.20, airLevel=0.02|
    var ratios, saws, duck, pump, open, cutoffMove, env, dry, air, mod, st, wet, sig;
    RandSeed.ir(1, 91);
    ratios = [1 - detune, 1 - (detune * 0.5), 1, 1 + (detune * 0.5), 1 + detune];
    saws = Mix(ratios.collect { |r| Saw.ar(freq * r) * 0.2 });
    duck = LFSaw.kr(pumpRate, 1).range(0, 1).pow(0.5);
    pump = 1 - (pumpDepth * (1 - duck));
    open = EnvGen.kr(Env([cutoff * 0.3, cutoff], [bloom], \sin));
    cutoffMove = SinOsc.kr(0.035, 0).range(cutoff * 0.75, cutoff * 1.25);
    env = EnvGen.kr(
        Env.linen(1.2, (sustain - 3.0).max(0.5), 1.8, 1, \sin), doneAction: 2);
    dry = RLPF.ar(saws, open.min(cutoffMove).max(150), 0.45) * env * amp * pump;
    air = HPF.ar(PinkNoise.ar(airLevel), 1800);
    air = BPF.ar(air, SinOsc.kr(0.025).range(2200, 5200), 0.4) * env * amp;
    dry = dry + air;
    mod = SinOsc.kr([0.07, 0.11], [0, 1.7]).range(0, 0.004);
    st = DelayC.ar(dry ! 2, 0.04, [0.013, 0.021] + mod);
    wet = GVerb.ar(LPF.ar(dry, 4500), 55, 5.5, 0.35, 0.55, 12, 0);
    sig = (st * 0.75) + (wet * verbMix);
    sig = BHiShelf.ar(sig, 6500, 1, -5);
    Out.ar(out, sig);
}),

// vibe_chords — dark stab/swell with stereo chorus + small dark room
// (was: dry-leaning mono; the chorus/space lift is the cross-model delta).
SynthDef(\vibe_chords, { |out=0, freq=220, amp=0.6, sustain=0.3, pumpRate=2.066,
                          cutoff=1100, pluck=0.18, verbMix=0.22|
    var stab, ratios, saws, fenv, env, dry, mod, st, wet, sig;
    stab = sustain < 1.0;
    ratios = [0.996, 1, 1.004];
    saws = Mix(ratios.collect { |r| Saw.ar(freq * r) * 0.3 });
    fenv = EnvGen.kr(Env([cutoff, cutoff * 0.25], [Select.kr(stab, [sustain * 0.8, pluck])], -3));
    env = EnvGen.kr(Env.linen(0.004, (sustain - 0.06).max(0.02), 0.05), doneAction: 2);
    dry = LPF.ar(saws, fenv.max(120)) * env * amp;
    mod = SinOsc.kr([0.09, 0.13], [0, 2.1]).range(0, 0.003);
    st = DelayC.ar(dry ! 2, 0.04, [0.011, 0.017] + mod);
    wet = GVerb.ar(LPF.ar(dry, 4000), 45, 3.5, 0.4, 0.55, 10, 0);
    sig = (st * 0.8) + (wet * verbMix);
    sig = BHiShelf.ar(sig, 6500, 1, -4);
    Out.ar(out, sig);
}),

// vibe_lead — delayed pluck with FILTERED STEREO ping-pong echoes + diffusion
// (replaces the mono comb — the "metallic cheap" tell). Dry stays sine-forward.
SynthDef(\vibe_lead, { |out=0, freq=440, amp=0.6, sustain=0.4, pumpRate=2.066,
                        delayBeats=0.75, cutoff=2400|
    var pluckEnv, tone, dry, delayTime, wet, env, sig;
    pluckEnv = EnvGen.kr(Env.perc(0.002, 0.5, 1, -5));
    tone = (SinOsc.ar(freq) * 0.65) + (Saw.ar(freq) * 0.18);
    tone = LPF.ar(tone, (cutoff * pluckEnv).max(300));
    dry = tone * pluckEnv;
    delayTime = delayBeats / pumpRate;
    wet = DelayC.ar(dry ! 2, 1.0, [delayTime, delayTime * 1.5]);
    wet = LPF.ar(HPF.ar(wet, 350), 4200);
    wet = wet + AllpassC.ar(wet, 0.08, [0.031, 0.043], 1.2);
    env = EnvGen.kr(Env.linen(0.001, sustain.max(0.3) + 2.0, 0.4), doneAction: 2);
    sig = ((dry ! 2) + (wet * 0.35)) * env * amp;
    Out.ar(out, sig);
}),

// vibe_arp — metallic pluck, sits behind the lead.
SynthDef(\vibe_arp, { |out=0, freq=440, amp=0.5, sustain=0.12, pumpRate=2.066,
                       cutoff=1900, snap=0.07|
    var env, tone, sig;
    env = EnvGen.kr(Env.perc(0.001, sustain.max(0.1) + 0.12, 1, -6), doneAction: 2);
    tone = (Pulse.ar(freq, 0.35) * 0.4) + (Pulse.ar(freq * 1.005, 0.35) * 0.3);
    tone = LPF.ar(tone, (cutoff * EnvGen.kr(Env.perc(0.001, snap))).max(400));
    sig = tone + CombC.ar(tone, 0.3, 0.25 / pumpRate, 0.8, 0.3);
    sig = HPF.ar(sig, 550);  // arp owns 900Hz+ (spectral fences, mix review)
    Out.ar(out, (sig * env * amp) ! 2);
}),

// vibe_fx — noise riser grains + boom impact (low notes become the boom).
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
}),

// ---- Synthesized percussion kit (tranche 3): GM percussion retired. ----
// One dark-analog family: filtered noise + metal partials, no samples.

// vibe_hat — closed hat: metallic noise tick.
SynthDef(\vibe_hat, { |out=0, freq=440, amp=0.5, sustain=0.06, pumpRate=2.066|
    var env, sig;
    RandSeed.ir(1, 53);
    env = EnvGen.kr(Env.perc(0.001, sustain.clip(0.03, 0.08), 1, -7), doneAction: 2);
    sig = BPF.ar(WhiteNoise.ar(1), 9000, 0.9) + BPF.ar(WhiteNoise.ar(0.5), 12500, 1.2);
    Out.ar(out, (HPF.ar(sig, 6000) * env * amp) ! 2);
}),

// vibe_openhat — offbeat sizzle: same family, longer tail.
SynthDef(\vibe_openhat, { |out=0, freq=440, amp=0.5, sustain=0.3, pumpRate=2.066|
    var env, sig;
    RandSeed.ir(1, 59);
    env = EnvGen.kr(Env.perc(0.001, sustain.clip(0.18, 0.4), 1, -4), doneAction: 2);
    sig = BPF.ar(WhiteNoise.ar(1), 8500, 0.7) + BPF.ar(WhiteNoise.ar(0.4), 11500, 1.0);
    Out.ar(out, (HPF.ar(sig, 5500) * env * amp * 0.8) ! 2);
}),

// vibe_clap — 909-style clap: three pre-echo bursts + main burst, dark band.
SynthDef(\vibe_clap, { |out=0, freq=440, amp=0.7, sustain=0.25, pumpRate=2.066|
    var burstEnv, tailEnv, noise, sig;
    RandSeed.ir(1, 61);
    burstEnv = EnvGen.kr(Env(
        [0, 1, 0.2, 1, 0.25, 1, 0], [0.001, 0.009, 0.001, 0.009, 0.001, 0.02], -4));
    tailEnv = EnvGen.kr(Env.perc(0.02, 0.18, 0.5, -5), doneAction: 2);
    noise = BPF.ar(WhiteNoise.ar(1), 1200, 0.9) + BPF.ar(WhiteNoise.ar(0.6), 1800, 1.1);
    sig = noise * (burstEnv + tailEnv);
    sig = LPF.ar(HPF.ar(sig, 800), 4000);  // dark rim shadow band (mix review)
    Out.ar(out, (sig * amp) ! 2);
}),

// vibe_ride — peak shimmer: high metal partials, restrained.
SynthDef(\vibe_ride, { |out=0, freq=440, amp=0.4, sustain=0.35, pumpRate=2.066|
    var env, metal, sig;
    RandSeed.ir(1, 67);
    env = EnvGen.kr(Env.perc(0.001, sustain.clip(0.25, 0.5), 1, -3), doneAction: 2);
    metal = Mix([5237, 6433, 7891, 9241].collect { |f| SinOsc.ar(f) * 0.1 });
    sig = (metal + BPF.ar(WhiteNoise.ar(0.5), 8200, 0.8)) * env;
    Out.ar(out, (HPF.ar(sig, 4500) * amp * 0.7) ! 2);
}),

// vibe_shaker — 16th texture: soft dark noise grain with velocity contour.
SynthDef(\vibe_shaker, { |out=0, freq=440, amp=0.4, sustain=0.05, pumpRate=2.066|
    var env, sig;
    RandSeed.ir(1, 71);
    env = EnvGen.kr(Env.perc(0.004, sustain.clip(0.03, 0.07), 1, -5), doneAction: 2);
    sig = BPF.ar(PinkNoise.ar(1.2), 6800, 1.1);
    Out.ar(out, (HPF.ar(sig, 4200) * env * amp) ! 2);
}),

// vibe_tom — fill tom: pitched sine drop, same family as the kick.
SynthDef(\vibe_tom, { |out=0, freq=110, amp=0.7, sustain=0.25, pumpRate=2.066|
    var pitch, env, sig;
    RandSeed.ir(1, 73);
    pitch = EnvGen.kr(Env([freq * 1.6, freq], [0.06], -4));
    env = EnvGen.kr(Env.perc(0.002, sustain.clip(0.15, 0.35), 1, -5), doneAction: 2);
    sig = (SinOsc.ar(pitch) * 1.3).tanh * env * amp;
    Out.ar(out, sig ! 2);
})
]
