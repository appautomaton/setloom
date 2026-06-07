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

// ---- Modern lead bus (2026): role-separated layers, not one retro patch. ----
// Anti-retro safeguards: no static single saw/pulse disco lead, no bright
// chorus-brass profile, and no equal-status octave/unison doubling across all notes.

// vibe_lead_body — center identity/body.
// Spectral allocation: owns 400Hz-3.5kHz; avoids sub and hat air.
// Math/psychoacoustics: sine-FM core gives focus, VarSaw micro-detune gives
// controlled beating, pre-filter tanh adds body before a dark moving LPF.
// Stereo/phase: mostly center; tiny post-HPF micro-delay only above 350Hz.
SynthDef(\vibe_lead_body, { |out=0, freq=440, amp=0.6, sustain=0.4, pumpRate=2.066,
    cutoff=2600, drive=1.45|
    var hit, hold, tail, fm, core, ratios, widths, saw, raw, sat, filt, wide, sig;
    hit = EnvGen.kr(Env.perc(0.004, 0.22, 1, -5));
    hold = EnvGen.kr(Env.linen(0.006, sustain.max(0.22), 0.34, 1, \sin));
    tail = EnvGen.kr(Env.linen(0.001, sustain.max(0.30) + 1.5, 0.30), doneAction: 2);
    fm = SinOsc.ar(freq * 1.997, 0, freq * 0.018 * hit);
    core = SinOsc.ar(freq + fm) * 0.40;
    ratios = [0.996, 0.9985, 1, 1.0025, 1.004];
    widths = SinOsc.kr([0.031, 0.037, 0.043, 0.049, 0.055], 0).range(0.38, 0.52);
    saw = Mix(VarSaw.ar(freq * ratios, 0, widths) * [0.05, 0.08, 0.11, 0.08, 0.05]);
    raw = core + saw;
    sat = (raw * drive).tanh / drive;
    filt = RLPF.ar(sat, (cutoff * hit.linlin(0, 1, 0.42, 1.08)).clip(420, 3600), 0.36);
    filt = BPeakEQ.ar(filt, 430, 0.8, 1.6);
    filt = LPF.ar(BHiShelf.ar(filt, 6500, 1, -5), 5200) * hold;
    wide = DelayC.ar(HPF.ar(filt, 350) ! 2, 0.03, [0.011, 0.017]);
    sig = ((filt ! 2) * 0.88) + (wide * 0.10);
    Out.ar(out, sig * amp * tail);
}),

// vibe_lead_edge — short modern attack bite.
// Spectral allocation: 1.2-4.8kHz only; it adds attack, never sustained brass.
// Temporal rule: very short envelope, so it cannot become an 80s disco stab.
// Stereo/phase: narrow, because transient localization should stay precise.
SynthDef(\vibe_lead_edge, { |out=0, freq=440, amp=0.35, sustain=0.08, pumpRate=2.066,
    drive=1.8|
    var env, pm, body, glass, sig;
    env = EnvGen.kr(Env.perc(0.0015, sustain.clip(0.035, 0.14), 1, -7), doneAction: 2);
    pm = SinOsc.ar(freq * 3.01, 0, freq * 0.025);
    body = SinOsc.ar((freq * 2.0) + pm) * 0.28;
    glass = Pulse.ar(freq * 2.003, 0.42) * 0.10;
    sig = ((body + glass) * drive).tanh / drive;
    sig = LPF.ar(HPF.ar(sig, 1200), 4800);
    Out.ar(out, (sig * env * amp) ! 2);
}),

// vibe_lead_air — filtered air/grain texture.
// Spectral allocation: 3-5.5kHz; deliberately below the hat/shaker >6k zone.
// Psychoacoustic role: movement and expensive texture, not brightness ownership.
// Stereo/phase: wide after HPF; deterministic RandSeed controls noise source.
SynthDef(\vibe_lead_air, { |out=0, freq=440, amp=0.18, sustain=0.25, pumpRate=2.066|
    var env, band, motion, grains, wide, sig;
    RandSeed.ir(1, 89);
    env = EnvGen.kr(Env.perc(0.008, sustain.max(0.18) + 0.35, 1, -4), doneAction: 2);
    motion = SinOsc.kr(0.067, 0).range(3300, 5200);
    band = BPF.ar(PinkNoise.ar(1), motion, 0.22);
    grains = HPF.ar(Impulse.ar(freq / 8) * 0.12, 2500);
    sig = LPF.ar(HPF.ar((band + grains) * env, 2800), 5500);
    wide = DelayC.ar(sig ! 2, 0.035, [0.014, 0.023]);
    Out.ar(out, wide * amp);
}),

// vibe_lead_shadow — quiet octave/response support.
// Spectral allocation: 160-900Hz chest only; high-passed out of bass territory.
// Arrangement role: the renderer does not send every note; this layer supports
// selected moments instead of becoming equal-status octave doubling.
// Stereo/phase: mono/narrow to protect body-range phase.
SynthDef(\vibe_lead_shadow, { |out=0, freq=220, amp=0.24, sustain=0.35, pumpRate=2.066|
    var env, core, pulse, sig;
    env = EnvGen.kr(Env.linen(0.008, sustain.max(0.18), 0.22, 1, \sin), doneAction: 2);
    core = SinOsc.ar(freq) * 0.28;
    pulse = VarSaw.ar(freq * 1.005, 0, 0.36) * 0.08;
    sig = LPF.ar(HPF.ar(((core + pulse) * 1.25).tanh, 160), 900);
    Out.ar(out, (sig * env * amp) ! 2);
}),

// ---- Lead-effect source gestures: dark rave function, not MIDI-note patches. ----
// Anti-EDM safeguards: phrase-triggered only, filtered under 5.5kHz, no random
// riser spam, no open white-noise sweep, no supersaw hook substitute.

// vibe_lead_fx_tease — early filtered identity cue.
// Spectral allocation: 3-5.5kHz resonant air, below hats and above lead body.
// Gesture/envelope: short breathed sweep; it hints at identity before the motif.
// Stereo/phase: wide only after HPF, so low/body content stays phase-safe.
SynthDef(\vibe_lead_fx_tease, { |out=0, freq=440, amp=0.18, sustain=0.8, pumpRate=2.066|
    var env, sweep, body, noise, sig, wide;
    RandSeed.ir(1, 101);
    env = EnvGen.kr(Env.linen(0.012, sustain.max(0.20), 0.34, 1, \sin), doneAction: 2);
    sweep = EnvGen.kr(
        Env([freq * 3.8, freq * 5.2, freq * 2.6], [sustain * 0.42, sustain * 0.58], \sin));
    body = Mix(SinOsc.ar(freq * [1, 1.005]) * [0.045, 0.035]);
    noise = BPF.ar(PinkNoise.ar(0.9), sweep.clip(1800, 5400), 0.20);
    sig = LPF.ar(HPF.ar((noise + body) * env, 1800), 5500);
    wide = DelayC.ar(sig ! 2, 0.04, [0.017, 0.029]);
    Out.ar(out, wide * amp);
}),

// vibe_lead_fx_throw — dark resonant phrase throw.
// Spectral allocation: 1.2-4.8kHz transient/motion band, away from sub and hats.
// Gesture/envelope: fast hit into resonant falling tail; reads as a throw, not a note.
// Stereo/phase: localized attack plus a filtered post-HPF slap for club width.
SynthDef(\vibe_lead_fx_throw, { |out=0, freq=440, amp=0.22, sustain=0.45, pumpRate=2.066|
    var env, fenv, pm, hit, noise, tail, slap, sig;
    RandSeed.ir(1, 103);
    env = EnvGen.kr(Env.perc(0.002, sustain.max(0.24) + 0.22, 1, -5), doneAction: 2);
    fenv = EnvGen.kr(Env([freq * 7.5, freq * 3.2, freq * 2.1], [0.05, sustain.max(0.20)], -4));
    pm = SinOsc.ar(freq * 2.01, 0, freq * 0.06 * env);
    hit = SinOsc.ar((freq * 2.0) + pm) * 0.22;
    noise = BPF.ar(PinkNoise.ar(0.8), fenv.clip(1200, 4800), 0.18);
    tail = RLPF.ar(((hit + noise) * 2.2).tanh, fenv.clip(900, 5200), 0.28);
    tail = LPF.ar(HPF.ar(tail, 1100), 5000) * env;
    slap = DelayC.ar(tail ! 2, 0.06, [0.023, 0.037]) * 0.26;
    sig = ((tail ! 2) * 0.82) + slap;
    Out.ar(out, sig * amp);
}),

// vibe_lead_fx_whoop — semi-pitched call-response sweep.
// Spectral allocation: 500Hz-3.5kHz body motion, filtered before the hat band.
// Gesture/envelope: curved pitch sweep with saturation, a rave response instead of MIDI melody.
// Stereo/phase: centered body with only high-passed delayed width.
SynthDef(\vibe_lead_fx_whoop, { |out=0, freq=440, amp=0.20, sustain=0.70, pumpRate=2.066|
    var env, sweep, mod, raw, shaped, filt, wide, sig;
    env = EnvGen.kr(Env.linen(0.006, sustain.max(0.30), 0.24, 1, \sin), doneAction: 2);
    sweep = EnvGen.kr(
        Env([freq * 0.72, freq * 1.36, freq * 2.10], [sustain * 0.48, sustain * 0.52], \sin));
    mod = SinOsc.ar(sweep * 1.51, 0, sweep * 0.035);
    raw = (SinOsc.ar(sweep + mod) * 0.34) + (VarSaw.ar(sweep * 0.5, 0, 0.42) * 0.11);
    shaped = ((raw * 2.4).tanh) * env;
    filt = RLPF.ar(shaped, (sweep * 2.2).clip(520, 3600), 0.32);
    filt = LPF.ar(HPF.ar(filt, 480), 4200);
    wide = DelayC.ar(HPF.ar(filt, 900) ! 2, 0.035, [0.014, 0.024]) * 0.18;
    sig = ((filt ! 2) * 0.88) + wide;
    Out.ar(out, sig * amp);
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
