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

// vibe_pad v2 — saturated euphoric dark pad ("ecstasy", take-9 + cross-model
// recipe): 7-voice VarSaw with moving widths (the emotional beating source),
// asymmetric pre-filter saturation swelling with the bloom (warm glow, not
// bright clip), slow 4.8s bloom, pump after tone shaping, dark space after
// pump, 420 Hz carve making room for the lead's body push.
SynthDef(\vibe_pad, { |out=0, freq=220, amp=0.5, sustain=4.0, pumpRate=2.066,
    detune=0.006, cutoff=1050, bloom=4.8, pumpDepth=0.40,
    verbMix=0.16, airLevel=0.018, drive=1.55, bias=0.14, leadCarve=2.5|
    var ratios, levels, widths, raw, body, driveEnv, sat;
    var duck, pump, open, cutoffMove, env, filt, air;
    var mod, wideSource, st, wet, sig;
    RandSeed.ir(1, 91);
    // About -12, -7, -3, 0, +4, +8, +13 cents.
    ratios = [0.9931, 0.9960, 0.9983, 1, 1.0023, 1.0046, 1.0075];
    levels = [0.07, 0.09, 0.11, 0.14, 0.11, 0.09, 0.07];
    widths = SinOsc.kr(
        [0.027, 0.033, 0.041, 0.019, 0.046, 0.052, 0.061],
        [0, 1.2, 2.1, 0.4, 1.7, 2.6, 3.0]
    ).range(0.36, 0.58);
    raw = Mix(VarSaw.ar(freq * ratios, 0, widths) * levels);
    body = SinOsc.ar(freq) * 0.10;  // warmth without a true sub layer
    raw = raw + body;
    driveEnv = EnvGen.kr(Env([drive * 0.75, drive], [bloom * 0.85], \sin));
    sat = (((raw * driveEnv) + bias).tanh - bias.tanh) / driveEnv;
    open = EnvGen.kr(Env([cutoff * 0.22, cutoff * 1.12], [bloom], \sin));
    cutoffMove = SinOsc.kr(0.035, 0).range(0.84, 1.18);
    env = EnvGen.kr(
        Env.linen(1.6, (sustain - 4.0).max(0.6), 2.4, 1, \sin), doneAction: 2);
    filt = RLPF.ar(sat, (open * cutoffMove).clip(180, 1800), 0.42);
    filt = HPF.ar(filt, 155);
    filt = BPeakEQ.ar(filt, 260, 0.7, 1.4);            // warmth below the lead body
    filt = BPeakEQ.ar(filt, 420, 0.85, leadCarve.neg);  // room for lead v2's push
    duck = LFSaw.kr(pumpRate, 1).range(0, 1).pow(0.52);
    pump = 1 - (pumpDepth * (1 - duck));
    filt = filt * env * amp * pump;
    air = HPF.ar(PinkNoise.ar(airLevel), 1800);
    air = BPF.ar(air, SinOsc.kr(0.025).range(2400, 5200), 0.35) * env * amp * pump;
    filt = filt + air;
    wideSource = HPF.ar(filt, 320);
    mod = SinOsc.kr([0.07, 0.11], [0, 1.7]).range(0, 0.004);
    st = DelayC.ar(wideSource ! 2, 0.04, [0.013, 0.021] + mod);
    wet = GVerb.ar(LPF.ar(HPF.ar(filt, 260), 4300), 60, 6.2, 0.42, 0.52, 12, 0);
    sig = ((filt ! 2) * 0.38) + (st * 0.78) + (wet * verbMix);
    sig = LPF.ar(sig, 5200);
    sig = BHiShelf.ar(sig, 6500, 1, -6);
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

// vibe_lead v2 — signature dark pluck/body lead (take-9 + cross-model recipe):
// centered sine core + 5-voice VarSaw unison (±4-8 cents) + pulse edge +
// quiet octave-down support + air transient, asymmetric pre-filter tanh,
// resonant darkening filter with slow wander, filtered stereo ping-pong
// delay + small dark verb. Body and identity, still restrained.
SynthDef(\vibe_lead, { |out=0, freq=440, amp=0.6, sustain=0.4, pumpRate=2.066,
    delayBeats=0.75, cutoff=2600, drive=1.55, wetMix=0.32,
    width=0.18, octaveLevel=0.10|
    var hitEnv, bodyEnv, tailEnv, filtEnv, cutMove;
    var ratios, core, uni, edge, octave, air, mono, sat, filt;
    var center, wideSource, wide, delayTime, echo, verb, sig;
    RandSeed.ir(1, 83);
    hitEnv = EnvGen.kr(Env.perc(0.004, 0.42, 1, -5));
    bodyEnv = EnvGen.kr(Env.linen(0.006, sustain.max(0.20), 0.32, 1, \sin));
    tailEnv = EnvGen.kr(
        Env.linen(0.001, sustain.max(0.30) + 2.2, 0.45), doneAction: 2);
    // Filter opens for the attack, then settles dark instead of vanishing.
    filtEnv = EnvGen.kr(Env(
        [cutoff * 1.15, cutoff * 0.68, cutoff * 0.42], [0.10, 0.65], [-3, -4]));
    cutMove = SinOsc.kr(0.045, 0).range(0.92, 1.08);
    ratios = [0.9954, 0.9977, 1, 1.0023, 1.0046];  // ±4-8 cents, no supersaw cheese
    core = SinOsc.ar(freq) * 0.38;
    uni = Mix(VarSaw.ar(freq * ratios, 0, 0.42) * [0.07, 0.09, 0.12, 0.09, 0.07]);
    edge = Pulse.ar(freq * 1.001, 0.42) * 0.08;
    octave = (SinOsc.ar(freq * 0.5) * octaveLevel) + (VarSaw.ar(freq * 0.5, 0, 0.35) * 0.035);
    octave = LPF.ar(HPF.ar(octave, 160), 900);  // chest, not bass
    air = HPF.ar(PinkNoise.ar(0.01), 2500) * hitEnv;
    mono = core + uni + edge + octave + air;
    sat = (mono * drive).tanh / drive;  // dirt before filter: expensive-dark
    filt = RLPF.ar(sat, (filtEnv * cutMove).clip(450, 4200), 0.38);
    filt = BPeakEQ.ar(filt, 420, 0.8, 2.0);  // subtle body push
    filt = BHiShelf.ar(filt, 6500, 1, -5);
    center = filt * bodyEnv;
    wideSource = HPF.ar(filt, 350) * bodyEnv;
    wide = DelayC.ar(wideSource ! 2, 0.035,
        [0.012, 0.019] + SinOsc.kr([0.08, 0.13], [0, 1.4]).range(0, 0.002));
    delayTime = delayBeats / pumpRate;
    echo = DelayC.ar((center ! 2) + (wide * 0.35), 1.0, [delayTime, delayTime * 1.5]);
    echo = LPF.ar(HPF.ar(echo, 350), 3900);
    echo = echo + AllpassC.ar(echo, 0.08, [0.031, 0.043], 1.1);
    verb = GVerb.ar(LPF.ar(center, 3600), 35, 2.6, 0.4, 0.55, 8, 0) * 0.05;
    sig = ((center ! 2) * 0.82) + (wide * width) + (echo * wetMix) + verb;
    sig = (sig * 1.15).tanh * 0.9 * amp * tailEnv;
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
