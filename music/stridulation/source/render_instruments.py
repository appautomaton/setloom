"""Render the authored MIDI performance and coherent full-length solo buses."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
from audio_runtime import write_audio,measure_loudness
from midi_io import read
from output_paths import validate_output
from instruments import synthesize,noise,filt,pan,envelope_edges,room,delays,voice_gesture,window_mask
HERE=Path(__file__).resolve().parent
WORK=HERE.parent

from voice import vocal

def added_noise(note,patch,sr,friction=False):
    count=round((note['end']-note['start'])*sr);t=np.arange(count)/sr
    rng=np.random.default_rng(round(note['start']*1000)+171)
    if friction:
        center=patch['center_hz'];rate=patch['teeth_hz']
        texture=noise(rng,count,sr,max(700,center*.58),min(6500,center*1.9))
        teeth=(.5+.5*np.sin(2*np.pi*(rate*t+rate*.3*t*t)))**3
        modes=sum(np.sin(2*np.pi*f*t)*np.exp(-t/.045) for f in [center,center*1.41,center*1.73])*.14
        y=filt(texture*(.25+.75*teeth)+modes,sr,lo=700,hi=6400)
    else:y=noise(rng,count,sr,1600,5900)
    y*=envelope_edges(count,sr,.01,.03)
    y*=patch['rms']/(np.sqrt(np.mean(y*y))+1e-12)*(note['velocity']/100)**1.6
    return pan(np.column_stack([y,y]),patch['pan']).astype('float32')

def automate(n,sr,points):
    return 10**(np.interp(np.arange(n)/sr,*np.array(points).T)/20)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    out=validate_output(args.out);stems=out/'stems';stems.mkdir(parents=True,exist_ok=True)
    score=json.loads((HERE/'performance.json').read_text());design=json.loads((HERE/'mix-design.json').read_text())
    settings=json.loads((HERE/'voice-score.json').read_text());played=read(HERE/'STRIDULATION.mid')
    controls=np.load(HERE/'instrument-controls.npz');spatial=np.load(HERE/'spatial-controls.npz')
    sr=score['sample_rate'];n=round(score['duration_seconds']*sr)
    groups={k:np.zeros((n,2),dtype='float32') for k in ['rhythm','synth','voice','friction']}
    sends={k:np.zeros((n,2),dtype='float32') for k in groups};echo={k:np.zeros((n,2),dtype='float32') for k in groups}
    kickduck=np.ones(n,dtype='float32');foreground=np.ones(n,dtype='float32');vspace=np.ones(n,dtype='float32')
    def dip(array,start,duration,depth,recovery):
        a=max(0,round(start*sr));end=min(n,a+round(duration*sr));t=np.arange(end-a)/sr
        if end>a:array[a:end]=np.minimum(array[a:end],1-(1-10**(-depth/20))*np.exp(-t/recovery))
    for part in score['tracks']:
        num=part['name'][:2]
        for note in played[part['name']]:
            if num in ['01','03','05','07','08','09','10']:dip(foreground,note['start'],.2,2.5,.07)
            if num=='10':dip(kickduck,note['start'],.2,2.5,.07)
            if num=='15' and 'preserved_synth_space_windows' not in settings:
                a=max(0,round((note['start']-.025)*sr));b=min(n,round((note['end']+.16)*sr))
                edge=envelope_edges(b-a,sr,.025,.16)
                vspace[a:b]=np.minimum(vspace[a:b],1-edge*(1-10**(-2.2/20)))
    for window in settings.get('preserved_synth_space_windows', []):
        a=max(0,round((window['start']-.025)*sr));b=min(n,round((window['end']+.16)*sr))
        edge=envelope_edges(b-a,sr,.025,.16)
        vspace[a:b]=np.minimum(vspace[a:b],1-edge*(1-10**(-2.2/20)))
    gate=window_mask(n,sr,design['delay']['windows_seconds'])
    leadgain=automate(n,sr,design['automation']['lead_space']);texturegain=automate(n,sr,design['automation']['texture_space'])
    report=[];max_error=0;total=0
    for part in score['tracks']:
        num=part['name'][:2];refs={x['curve']:x for x in part['notes']};events=played[part['name']]
        assert len(refs)==len(events)
        y=np.zeros((n,2),dtype='float32')
        for note in events:
            ref=refs[note['curve']];total+=1
            max_error=max(max_error,abs(note['start']-ref['start']),abs(note['end']-ref['end']))
            if part['kind']=='voice':z=vocal(note,settings['patches'][note['curve']],settings,sr)
            elif part['kind'] in ['breath','friction']:z=added_noise(note,settings['patches'][note['curve']],sr,part['kind']=='friction')
            else:
                z=synthesize(part,note,ref,controls,spatial,sr,design)*ref.get('arrangement_gain',1)
                shorten=ref.get('tail_shorten',0)
                if shorten:
                    t=np.arange(len(z))/sr;duration=len(z)/sr
                    z*=np.exp(-shorten*np.clip((t-.025)/max(.02,duration-.025),0,1)*3)[:,None]
            a=round(note['start']*sr)
            anchor=design.get('unchanged_event_sample_anchors',{}).get(note['curve'])
            if anchor and abs(note['start']-anchor['midi_start'])<1e-9:a=anchor['sample_start']
            b=min(n,a+len(z));assert 0<=a<b<=n
            y[a:b]+=z[:b-a]
        if num=='02':
            y=filt(y,sr,lo=44).astype('float32')
            for window in design.get('bass_response_windows',[]):
                a=round(window['start']*sr);b=round(window['end']*sr)
                shape=envelope_edges(b-a,sr,window['attack'],window['release'])
                y[a:b]*=(1-shape*(1-10**(-window['dip_db']/20)))[:,None]
        if num=='13':y*=foreground[:,None]*texturegain[:,None]
        if num in ['03','04','05','09']:y*=leadgain[:,None]*vspace[:,None]
        if num in ['14','15','16']:
            group='voice';send=settings['voice_design']['room_send'];echo[group]+=y
        elif num=='17':group='friction';send=.07;echo[group]+=y*.32
        elif num in ['01','02','10','11','12']:
            group='rhythm';send=design['parts'][num]['room_send']
        else:
            group='synth';send=design['parts'][num]['room_send']
            if num in design['delay']['source_parts']:echo[group]+=y*gate[:,None]
        groups[group]+=y;sends[group]+=y*send
        if num=='01':motif=y.copy()
        write_audio(stems/(part['name']+'.wav'),y,sample_rate=sr,subtype='FLOAT')
        report.append({'name':part['name'],'events':len(events),'rms':float(np.sqrt(np.mean(y*y))),'peak':float(abs(y).max())})
        print(part['name'],len(events),round(report[-1]['rms'],5),flush=True)
    for group in groups:
        wet=room(sends[group],sr,design['room'])*kickduck[:,None]
        if group=='voice':
            cfg=settings['voice_design']
            echo_return=delays(echo[group],sr,cfg['delay_seconds_gain'],lo=cfg['delay_highpass_hz'],hi=cfg['delay_lowpass_hz'])
            # Keep the dry utterance in front; allow echoes to emerge in its gaps.
            voice_duck=np.ones(n,dtype='float32')
            for part in score['tracks']:
                if part['kind']!='voice':continue
                for note in played[part['name']]:
                    a=max(0,round(note['start']*sr));b=min(n,round((note['end']+.09)*sr))
                    shape=envelope_edges(b-a,sr,.025,.09)
                    voice_duck[a:b]=np.minimum(voice_duck[a:b],1-shape*(1-10**(-cfg['echo_duck_db']/20)))
            wet+=echo_return*voice_duck[:,None]
        elif group=='synth':wet+=delays(echo[group],sr,design['delay']['taps_seconds_gain'])*kickduck[:,None]
        elif group=='friction':wet+=delays(echo[group],sr,[[.3,.18],[.6,.07]],lo=1300,hi=4600)
        write_audio(stems/(group+' - effects.wav'),wet,sample_rate=sr,subtype='FLOAT')
        groups[group]+=wet
    # Extend the composed exit with a filtered decaying reflection of its voice.
    # All excitation is synthesized above. No source recording enters the render.
    a=round(194*sr);b=round(195.1*sr)
    tail=groups['voice'][a:b].copy()
    tail*=envelope_edges(len(tail),sr,.025,.20)[:,None]
    for when,gain in [(195.2,.2),(196.4,.11),(197.6,.055),(198.8,.022)]:
        start=round(when*sr);z=filt(tail,sr,lo=700,hi=2600)*gain
        groups['voice'][start:start+len(z)]+=z
    # Quiet resonant continuation decays into the last half-second without padding.
    endfade=np.ones(n,dtype='float32');a=round(197.8*sr)
    endfade[a:]=np.cos(np.linspace(0,np.pi/2,n-a))**2;endfade[-1]=0
    # The last continuation lasts to 198.423; a shared-space tail extends naturally.
    for group in groups:
        groups[group]*=endfade[:,None]
        write_audio(out/(group+'-float.wav'),groups[group],sample_rate=sr,subtype='FLOAT')
    motif=(motif+room(motif*design['parts']['01']['room_send'],sr,design['room'])*kickduck[:,None])*endfade[:,None]
    mix=sum(groups.values());write_audio(out/'mix-float.wav',mix,sample_rate=sr,subtype='FLOAT')
    provisional=out/'meter.wav';write_audio(provisional,mix*.25,sample_rate=sr,subtype='FLOAT')
    measured=measure_loudness(provisional);provisional.unlink()
    gain=.25*10**((design['target_lufs']-measured['integrated_lufs'])/20)
    gain=10**(design['export_gain_db']/20) if 'export_gain_db' in design else gain
    gain=min(gain,.82/float(abs(mix).max()))
    for name,y in [('STRIDULATION',mix),('Voice solo',groups['voice']),('Synth solo',groups['synth']),('Rhythm',groups['rhythm']),('Friction',groups['friction']),('Motif solo',motif)]:
        write_audio(out/(name+'.wav'),y*gain,sample_rate=sr,subtype='PCM_24')
    meters=measure_loudness(out/'STRIDULATION.wav')
    # A measured true-peak correction applies equally to all buses, never solo normalization.
    correction=min(0,design['true_peak_ceiling_dbtp']-meters['true_peak_dbtp'])
    if correction<0:
        gain*=10**(correction/20)
        for name,y in [('STRIDULATION',mix),('Voice solo',groups['voice']),('Synth solo',groups['synth']),('Rhythm',groups['rhythm']),('Friction',groups['friction']),('Motif solo',motif)]:
            write_audio(out/(name+'.wav'),y*gain,sample_rate=sr,subtype='PCM_24')
        meters=measure_loudness(out/'STRIDULATION.wav')
    assert np.isfinite(mix).all() and np.max(abs(mix[-1]))==0
    assert max_error<.0005
    summary={'duration_seconds':n/sr,'frames':n,'sample_rate':sr,'parts':report,'events':total,
             'midi_max_timing_error_seconds':max_error,'gain_db':float(20*np.log10(gain)),
             'measurements':meters,'target_lufs':design['target_lufs'],'true_peak_ceiling_dbtp':design['true_peak_ceiling_dbtp'],
             'solo_gain':'Same gain as full mix, including each bus effects; not individually normalized',
             'reference_pcm_used':False,'listening_status':'User-approved revision 05 creative baseline; retained locally'}
    (out/'render.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
