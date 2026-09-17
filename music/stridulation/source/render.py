"""Render the accepted performance, then apply the editable whole-song mix stage."""
from pathlib import Path
import argparse,json,subprocess,sys
import numpy as np,soundfile as sf
from scipy.signal import fftconvolve
from instruments import filt,eq_peak,envelope_edges
from midi_io import read
from output_paths import validate_output
from audio_runtime import write_audio,measure_loudness
H=Path(__file__).resolve().parent;WORK=H.parent

def automation(points,n,sr):
    return np.interp(np.arange(n)/sr,*np.array(points).T).astype('float32')

def chamber(y,sr,cfg):
    """Damped diffuse stereo tail with independent predelay, without dry widening."""
    size=round((cfg['decay_seconds']+cfg['predelay_seconds'])*sr)
    offset=round(cfg['predelay_seconds']*sr);t=np.arange(size-offset)/sr
    rng=np.random.default_rng(cfg['seed']);ir=np.zeros((size,2))
    for ch in [0,1]:
        decay=np.exp(-6.907755*t/cfg['decay_seconds'])
        build=1-np.exp(-t/.012)
        tail=rng.standard_normal(len(t))*decay*build
        tail=filt(tail,sr,lo=cfg['highpass_hz'],hi=cfg['lowpass_hz'])
        tail/=np.sqrt(np.sum(tail*tail))+1e-12
        ir[offset:,ch]=tail
    excitation=filt(y,sr,lo=cfg['highpass_hz'],hi=cfg['lowpass_hz'])
    out=np.zeros_like(y)
    for ch in [0,1]:
        feed=.85*excitation[:,ch]+.15*excitation[:,1-ch]
        out[:,ch]=fftconvolve(feed,ir[:,ch])[:len(y)]
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--reuse-raw',action='store_true',help='Reuse this work area raw render after source identity verification');args=ap.parse_args()
    out=validate_output(args.out);raw=out/'raw';out.mkdir(parents=True,exist_ok=True)
    import hashlib
    source_ids={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in H.iterdir() if p.is_file() and p.name not in ['render.py','mix-stage.json']}
    if args.reuse_raw:
        assert json.loads((raw/'source-identities.json').read_text())==source_ids,'Raw performance cache is stale'
    else:
        subprocess.run([sys.executable,str(H/'render_instruments.py'),'--out',str(raw)],check=True)
        (raw/'source-identities.json').write_text(json.dumps(source_ids,indent=2)+'\n')
    score=json.loads((H/'performance.json').read_text());cfg=json.loads((H/'mix-stage.json').read_text());played=read(H/'STRIDULATION.mid')
    n=round(score['duration_seconds']*score['sample_rate']);sr=score['sample_rate']
    fade=np.ones(n,dtype='float32');a=round(197.8*sr);fade[a:]=np.cos(np.linspace(0,np.pi/2,n-a))**2;fade[-1]=0
    groups={k:sf.read(raw/(k+'-float.wav'),dtype='float32')[0] for k in ['rhythm','synth','voice','friction']}
    sends={k:np.zeros((n,2),dtype='float32') for k in cfg['space']}
    dry_deltas=np.zeros((n,2),dtype='float32');lead_gain=10**(automation(cfg['lead_level_db'],n,sr)/20)
    for part in score['tracks']:
        num=part['name'][:2];y=sf.read(raw/'stems'/(part['name']+'.wav'),dtype='float32')[0]
        if num=='13':
            z=y.copy()
            for hz,db,q in cfg['texture_eq']:z=eq_peak(z,sr,hz,db,q)
            z*=10**(automation(cfg['texture_level_db'],n,sr)/20)[:,None]
            delta=(z-y)*fade[:,None];groups['synth']+=delta;dry_deltas+=delta
        if num in ['03','04','05','06','07','08','09']:
            delta=y*(lead_gain-1)[:,None]*fade[:,None];groups['synth']+=delta;dry_deltas+=delta;y=y*lead_gain[:,None]
        for name,space in cfg['space'].items():
            if num in space['parts']:sends[name]+=y
    kickduck=np.ones(n,dtype='float32');voiceduck=np.ones(n,dtype='float32')
    for part in score['tracks']:
        for note in played[part['name']]:
            if part['name'].startswith('10 '):
                a=round(note['start']*sr);length=min(n-a,round(.38*sr));t=np.arange(length)/sr
                kickduck[a:a+length]=np.minimum(kickduck[a:a+length],1-(1-10**(-cfg['kick_duck_db']/20))*np.exp(-t/cfg['kick_recovery_seconds']))
            if part['kind']=='voice':
                a=max(0,round(note['start']*sr));b=min(n,round((note['end']+.18)*sr));edge=envelope_edges(b-a,sr,.025,.18)
                voiceduck[a:b]=np.minimum(voiceduck[a:b],1-edge*(1-10**(-cfg['voice_duck_db']/20)))
    returns={};focus=automation(cfg['return_focus'],n,sr)
    for name,space in cfg['space'].items():
        feed=sends[name]*automation(space['send'],n,sr)[:,None]
        wet=chamber(feed,sr,space)*kickduck[:,None]*voiceduck[:,None]*focus[:,None]*fade[:,None]
        groups[name]+=wet;returns[name]=wet
        write_audio(out/(name+'-new-space-float.wav'),wet,sample_rate=sr,subtype='FLOAT')
    mix=sum(groups.values());assert np.isfinite(mix).all() and abs(mix[-1]).max()==0
    write_audio(out/'mix-unscaled-float.wav',mix,sample_rate=sr,subtype='FLOAT')
    write_audio(out/'meter.wav',mix*.25,sample_rate=sr,subtype='FLOAT');meter=measure_loudness(out/'meter.wav');(out/'meter.wav').unlink()
    gain=.25*10**((cfg['preview_lufs']-meter['integrated_lufs'])/20)
    names={'mix':mix,'voice':groups['voice'],'synth':groups['synth'],'space':sum(returns.values()),'rhythm':groups['rhythm']}
    for name,y in names.items():write_audio(out/(name+'.wav'),y*gain,sample_rate=sr,subtype='PCM_24')
    measured=measure_loudness(out/'mix.wav')
    assert measured['true_peak_dbtp']<=cfg['true_peak_ceiling'],measured
    assert abs(measured['integrated_lufs']-cfg['preview_lufs'])<=.06,measured
    write_audio(out/'premaster-float.wav',mix*gain,sample_rate=sr,subtype='FLOAT')
    write_audio(out/'dry-mix-delta-float.wav',dry_deltas,sample_rate=sr,subtype='FLOAT')
    report={'status':'User-approved Mix 01 baseline; not a final master','duration_seconds':n/sr,'gain_db':float(20*np.log10(gain)),'measurements':measured,'notes_and_source_patches':'Unchanged retained revision 05 performance','changes':'Small foreground balance and texture EQ, damped section-aware spatial returns; intact kick and bass dry sources','source_identities':source_ids,'new_space_rms':{k:float(np.sqrt(np.mean(v*v))) for k,v in returns.items()}}
    (out/'render.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
