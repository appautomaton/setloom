"""Per-track synthetic vowel performance: pitch, mouth, breath and phrase energy."""
import numpy as np
from instruments import noise,pan,envelope_edges

def vocal(note,patch,settings,sr):
    duration=note['end']-note['start'];n=round(duration*sr)
    t=np.arange(n)/sr;q=t/duration;cfg=settings['voice_design']
    # Subtle settling; no repeated laser-like semitone dive on every syllable.
    delayed=np.clip((t-.28)/.35,0,1)
    vibrato=cfg['vibrato_cents']*np.sin(2*np.pi*(cfg['vibrato_hz']*t+.035*np.sin(2*np.pi*.8*t)))*delayed
    cents=patch['settle_cents']*np.exp(-t/.038)-7*np.clip((q-.84)/.16,0,1)**2+vibrato
    f=440*2**((note['pitch']-69)/12)*2**(cents/1200)
    phase=np.cumsum(f)*(2*np.pi/sr)
    begin=np.asarray(settings['vowels_hz'][patch['from']])
    end=np.asarray(settings['vowels_hz'][patch['to']])
    opening=patch['mouth_open_at']
    travel=np.clip((q-.09)/max(.1,opening-.09),0,1)
    mouth=(travel*travel*(3-2*travel))*(1-patch['mouth_return']*np.clip((q-.73)/.27,0,1))
    formants=begin[:,None]+(end-begin)[:,None]*mouth
    # A quieter upper formant and steeper excitation tilt soften the reed-like edge.
    y=np.zeros(n)
    for h in range(1,round(6500/max(f))):
        hz=h*f
        response=sum(g*np.exp(-.5*((hz-formants[i])/width)**2)
            for i,(g,width) in enumerate(zip(cfg['formant_gains'],cfg['formant_widths_hz'])))
        response+=.065*np.exp(-hz/1600)
        y+=np.sin(h*phase+.12*h)*response/h**patch['spectral_tilt']
    rng=np.random.default_rng(round(note['start']*1000)+515)
    air=noise(rng,n,sr,1200,5500)
    # Breath belongs inside the evolving voice, rather than a loud hiss on top.
    air_shape=.35*np.exp(-t/.055)+.4*np.sin(np.pi*q)**2+.25*q**3
    y+=air*air_shape*cfg['air_share']
    env=envelope_edges(n,sr,patch['attack_seconds'],min(patch['release_seconds'],duration*.3))
    if patch['role']=='focal':
        energy=np.interp(q,[0,.15,.42,.72,1],[.65,.88,1,.87,.6])
    else:energy=np.interp(q,[0,.12,.55,1],[.83,1,.9,.64])
    y*=env*energy
    y*=patch['rms']*10**(patch['presence_db']/20)/(np.sqrt(np.mean(y*y))+1e-12)*(note['velocity']/100)**1.6
    return pan(np.column_stack([y,y]),patch['pan']).astype('float32')
