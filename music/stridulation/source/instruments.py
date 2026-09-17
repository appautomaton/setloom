"""Editable revision performance with authored routing and fully synthetic voice.

Only MIDI, JSON and parameter arrays are inputs. No reference audio is replayed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
from scipy.signal import butter,sosfilt,lfilter,resample_poly,fftconvolve
from scipy.ndimage import uniform_filter1d
from audio_runtime import write_audio,measure_loudness
from midi_io import read

HERE=Path(__file__).resolve().parent
WORK=HERE.parent

def curve(x,n):
    return np.interp(np.linspace(0,1,n),np.linspace(0,1,len(x)),x)

def filt(y,sr,lo=None,hi=None):
    if lo is not None:y=sosfilt(butter(3,lo,fs=sr,btype='highpass',output='sos'),y,axis=0)
    if hi is not None:y=sosfilt(butter(3,hi,fs=sr,btype='lowpass',output='sos'),y,axis=0)
    return y

def noise(rng,n,sr,lo,hi):
    y=filt(rng.standard_normal(n+2048),sr,lo,hi)[2048:]
    return y/(np.sqrt(np.mean(y*y))+1e-12)

def eq_peak(y,sr,hz,db,q):
    a=10**(db/40);w=2*np.pi*hz/sr;alpha=np.sin(w)/(2*q)
    b=np.array([1+alpha*a,-2*np.cos(w),1-alpha*a])
    aa=np.array([1+alpha/a,-2*np.cos(w),1-alpha/a])
    return lfilter(b/aa[0],aa/aa[0],y,axis=0)

def pan(y,p):
    # Small balance offsets preserve the measured interchannel relationship.
    y[:,0]*=np.sqrt(1-p);y[:,1]*=np.sqrt(1+p)
    return y

def envelope_edges(n,sr,attack=.0015,release=.006):
    t=np.arange(n)/sr
    return np.clip(np.minimum(t/attack,(t[-1]-t)/release),0,1)

def synthesize(part,note,ref,data,spatial,sr,design):
    n=max(2,round((note['end']-note['start'])*sr));t=np.arange(n)/sr
    y=np.zeros((n,2));key=ref['curve'];kind=part['kind'];number=part['name'][:2]
    cfg=design['parts'][number]
    seed=int.from_bytes(hashlib.sha256(ref.get('seed_key',key).encode()).digest()[:8],'little')
    rng=np.random.default_rng(seed)
    if kind in ['tonal','kick']:
        amps=data[key+'_amp'];cents=data[key+'_cents']
        for h,ratio in enumerate(part['oscillator_ratios']):
            amp=curve(amps[h],n)
            frequency=440*2**((note['pitch']-69)/12)*ratio*2**(curve(cents[h],n)/1200)
            phase=np.cumsum(frequency)*(2*np.pi/sr)+(0.2 if kind=='kick' else h*.73)+ref.get('initial_phase',[0]*len(part['oscillator_ratios']))[h]
            offset=curve(spatial[key+'_right_phase'][h],n)*cfg['phase_scale']
            rg=curve(spatial[key+'_right_gain'][h],n)
            normalization=np.sqrt(2/(1+rg*rg))
            left = np.sin(phase)
            right = np.sin(phase + offset)
            variation = design.get('resonance_variation', {})
            if number == variation.get('part') and h + 1 in variation.get('partial_numbers', []):
                absolute_time = t + note['start']
                for window in variation['windows']:
                    start, end = window['start'], window['end']
                    if note['end'] <= start or note['start'] >= end:
                        continue
                    edge = variation['crossfade_seconds']
                    ramp = np.minimum(np.clip((absolute_time-start)/edge, 0, 1),
                                      np.clip((end-absolute_time)/edge, 0, 1))
                    blend = .5 - .5*np.cos(np.pi*ramp)
                    shifted_phase = phase + np.cumsum(frequency *
                        (2**(window['semitones']/12)-1)) * (2*np.pi/sr)
                    left += blend * (np.sin(shifted_phase) - left)
                    right += blend * (np.sin(shifted_phase + offset) - right)
            y[:,0]+=left*amp*normalization
            y[:,1]+=right*amp*rg*normalization
        if kind=='kick':
            k=design['kick'];attack=np.sin(2*np.pi*(120*t+50*.012*(1-np.exp(-t/.012))))
            y+=attack[:,None]*np.exp(-t/.012)[:,None]*.08
            up=k['oversampling'];z=resample_poly(y,up,1,axis=0)
            y=resample_poly(np.tanh(z*k['drive']),1,up,axis=0)[:n]
            y*=min(ref['target_rms']/(np.sqrt(np.mean(y*y))+1e-9),3)
            y=eq_peak(y,sr,k['body_eq_hz'],k['body_eq_db'],k['body_eq_q'])
            for row,(lo,hi) in enumerate(part['noise_bands']):
                env=curve(spatial[key+'_strike_noise'][row],n)*k['strike_band_gains'][row]
                left=noise(rng,n,sr,lo,hi);other=noise(rng,n,sr,lo,hi)
                rho=k['strike_noise_correlation']
                y[:,0]+=left*env;y[:,1]+=(rho*left+np.sqrt(1-rho*rho)*other)*env
    else:
        bands=part.get('noise_bands',[(150,650),(650,2500),(2500,6500),(6500,16000)])
        colors=data[key+'_noise'];rho=cfg['noise_correlation']
        for row,(lo,hi) in enumerate(bands):
            env=curve(colors[row],n)
            a=noise(rng,n,sr,lo,hi);b=noise(rng,n,sr,lo,hi)
            y[:,0]+=a*env;y[:,1]+=(rho*a+np.sqrt(1-rho*rho)*b)*env
        if number=='11':
            body=np.sin(2*np.pi*(218*t+70*.008*(1-np.exp(-t/.008))))
            y+=body[:,None]*curve(colors[0],n)[:,None]*.45
            y=filt(y,sr,hi=11000)
        if number=='12':
            h=design['hats'];modes=h['modal_frequencies_hz']
            metal=sum(np.sin(2*np.pi*f*t+.41*i)*np.exp(-t/(.036+i*.006))
                      for i,f in enumerate(modes))
            metal/=np.sqrt(np.mean(metal*metal))+1e-9
            env=curve(np.sqrt(colors[-1]**2+colors[-2]**2),n)
            y=y*h['noise_share']+metal[:,None]*env[:,None]*h['modal_share']
            y=filt(y,sr,lo=2500,hi=14500)
    y*=envelope_edges(n,sr,release=ref.get('release_seconds',.006))[:,None]
    y*=(note['velocity']/ref['reference_velocity'])**1.6
    y*=10**(cfg['gain_db']/20)
    return pan(y,cfg['pan']).astype('float32')

def window_mask(n,sr,windows):
    result=np.zeros(n,dtype='float32')
    for a,b in windows:
        i=max(0,round(a*sr));j=min(n,round(b*sr))
        if j>i:result[i:j]=np.maximum(result[i:j],envelope_edges(j-i,sr,.04,.04))
    return result

def room(y,sr,settings):
    n=len(y);size=round(settings['duration_seconds']*sr)
    rng=np.random.default_rng(413);out=np.zeros_like(y)
    for ch in [0,1]:
        ir=np.zeros(size)
        taps=[(.011,.52),(.017,.38),(.029,.3),(.043,.23),(.061,.15),(.083,.1)]
        for i,(when,gain) in enumerate(taps):
            ir[round((when+ch*.003+((i%2)*.001))*sr)]=gain*(-1 if (i+ch)%3==0 else 1)
        t=np.arange(size)/sr
        diffuse=rng.standard_normal(size)*np.exp(-t/.075)*(t>.022)*.007
        ir+=diffuse;ir=filt(ir,sr,settings['highpass_hz'],settings['lowpass_hz'])
        ir/=np.sqrt(np.sum(ir*ir))+1e-12
        out[:,ch]=fftconvolve(y[:,ch]*.75+y[:,1-ch]*.25,ir)[:n]
    return out

def delays(y,sr,taps,lo=600,hi=3900):
    y=filt(y,sr,lo,hi);out=np.zeros_like(y)
    for i,(seconds,gain) in enumerate(taps):
        shift=round(seconds*sr)
        source=y[:-shift,::-1] if i%2==0 else y[:-shift]
        out[shift:]+=source*gain
    return out

def voice_gesture(note,settings,sr):
    n=round(note['duration']*sr);t=np.arange(n)/sr;progress=t/max(t[-1],1e-9)
    f0=440*2**((note['pitch']-69)/12)
    pitch_cents=90*np.exp(-t/.025)-35*progress**3+6*np.sin(2*np.pi*9*t)
    fundamental=f0*2**(pitch_cents/1200)
    phase=np.cumsum(fundamental)*2*np.pi/sr
    begin=np.array(settings['vowels_hz'][note['from']]);end=np.array(settings['vowels_hz'][note['to']])
    morph=np.clip((progress-.12)/.7,0,1);formants=begin[:,None]*(1-morph)+end[:,None]*morph
    y=np.zeros(n)
    for h in range(1,round(7000/f0)):
        hz=h*fundamental
        # Excitation and moving oral resonances remain independently editable.
        response=sum(g*np.exp(-.5*((hz-formants[i])/bw)**2)
                     for i,(bw,g) in enumerate([(85,1),(125,.82),(200,.38)]))
        response+=.035*np.exp(-hz/2000)
        y+=np.sin(h*phase+.12*h)*response/h**.85
    rng=np.random.default_rng(round(note['start']*1000))
    hiss=noise(rng,n,sr,2300,7800)*np.exp(-t/.025)*.045
    y+=hiss
    env=envelope_edges(n,sr,.008,min(.04,n/sr*.25))*np.exp(-progress*.35)
    y*=env;y*=note['rms']/(np.sqrt(np.mean(y*y))+1e-12)
    return pan(np.column_stack([y,y]),note['pan']).astype('float32')
