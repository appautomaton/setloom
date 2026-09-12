# SPDX-License-Identifier: AGPL-3.0-only
"""Accepted MIDI importer extended for two pulse lanes and channel-global CC11."""
import collections,copy,math
import mido
PARTS=['body','upper','bass','texture','pulse_lower','pulse_upper']
DRUMS={36:'kick',38:'snare',37:'snare_ghost',42:'hat',46:'bright_percussion'}
FX_WASH='FX wash (unpitched trigger)'
FX_END='FX resonant ending (excitation root)'
def velocity_gain(velocity):return 40*math.log10(velocity/100)

def import_midi(path, controls):
    midi=mido.MidiFile(path)
    if midi.type != 1: raise ValueError('Expected Type 1 MIDI')
    # Global MIDI tempo map, including edits and changes mid-song.
    tempos=[(0,500000)]
    end_tick=0
    for tr in midi.tracks:
        t=0
        for m in tr:
            t+=m.time
            if m.type=='set_tempo':tempos.append((t,m.tempo))
        end_tick=max(end_tick,t)
    tempos.sort(key=lambda row:row[0])
    def seconds(tick):
        result=0.;previous=0;tempo=500000
        for t,new in tempos:
            if t>tick:break
            result+=mido.tick2second(t-previous,midi.ticks_per_beat,tempo)
            previous=t;tempo=new
        return result+mido.tick2second(tick-previous,midi.ticks_per_beat,tempo)
    score=copy.deepcopy(controls)
    score.update(source_start_seconds=0,duration_seconds=seconds(end_tick),tempo_context_bpm=mido.tempo2bpm(tempos[0][1]),notes=[],kicks=[],snares=[],hats=[],bright_percussion=[],wash_triggers=[],ending_triggers=[],kick_velocity_db={})
    # Controllers are MIDI-channel global, even in separate automation tracks.
    channel_bends=collections.defaultdict(lambda:[[0.,0.]])
    channel_expression=collections.defaultdict(lambda:[[0.,127.]])
    state=collections.defaultdict(lambda:{'msb':127,'lsb':127,'range':2.,'coarse':2,'fine':0,'wheel':0})
    absolute=[]
    part_channels=collections.defaultdict(set)
    for track_index,tr in enumerate(midi.tracks):
        t=0
        for event_index,m in enumerate(tr):
            t+=m.time
            if m.type in ('control_change','pitchwheel'):
                absolute.append((t,track_index,event_index,m))
            if m.type=='program_change':
                raise ValueError('Program changes are unsupported: edit patch.json for this external synthesis mapping, then remove the program-change event')
            if tr.name in PARTS and m.type=='note_on' and m.velocity:
                part_channels[tr.name].add(m.channel)
    for part,channels in part_channels.items():
        if len(channels)>1:
            raise ValueError(f'{part} must use one MIDI channel; found {sorted(channels)}. Keep its notes on one channel for connected synthesis')
    pulse_channels={m.channel for tr in midi.tracks if tr.name in ['pulse_lower','pulse_upper'] for m in tr if hasattr(m,'channel')}
    original_channels=set().union(*(part_channels.get(part,set()) for part in ['body','upper','bass','texture']))
    if pulse_channels & original_channels:raise ValueError('Pulse lanes must use channels separate from accepted pitched parts')
    for t,_,_,m in sorted(absolute,key=lambda row:row[:3]):
        s=seconds(t);ch=m.channel;st=state[ch]
        if m.type=='control_change':
            if m.control==11:
                if ch not in pulse_channels:raise ValueError('CC11 is supported only on declared pulse-lane channels; no silently ignored expression edits')
                channel_expression[ch].append([s,float(m.value)]);continue
            if m.control not in (101,100,6,38):
                raise ValueError(f'Unsupported CC {m.control}; no silent controller override')
            if m.control in (6,38) and (st['msb'],st['lsb']) != (0,0):
                raise ValueError('Only pitch-bend sensitivity RPN 0,0 is supported')
            if m.control==101:st['msb']=m.value
            if m.control==100:st['lsb']=m.value
            if st['msb']==st['lsb']==0 and m.control in (6,38):
                st['coarse' if m.control==6 else 'fine']=m.value
                st['range']=st['coarse']+st['fine']/100
                channel_bends[ch].append([s,st['wheel']/8192*st['range']])
        elif m.type=='pitchwheel':
            st['wheel']=m.pitch;channel_bends[ch].append([s,m.pitch/8192*st['range']])
    for tr in midi.tracks:
        name=tr.name;t=0;active=collections.defaultdict(collections.deque);notes=[]
        for m in tr:
            t+=m.time;s=seconds(t)
            if m.is_meta or m.type in ('control_change','pitchwheel'): continue
            ch=m.channel if hasattr(m,'channel') else 0
            if m.type=='note_on' and m.velocity:
                active[(ch,m.note)].append((s,m.velocity))
            elif m.type=='note_off' or (m.type=='note_on' and m.velocity==0):
                if not active[(ch,m.note)]:raise ValueError(f'Unmatched note-off in {name}')
                start,v=active[(ch,m.note)].popleft()
                if s<=start:raise ValueError(f'Zero/negative note duration in {name}')
                notes.append((start,s,m.note,v,ch))
            else:
                raise ValueError(f'Unsupported MIDI message {m.type}; cannot silently ignore edits')
        if any(active.values()):raise ValueError(f'Unclosed notes in {name}')
        for start,end,key,velocity,ch in sorted(notes):
            if name in PARTS:
                score['notes'].append(dict(part=name,midi=key,start_seconds=start,end_seconds=end,velocity=velocity,carry_in=False,midi_bend_points=channel_bends[ch],midi_expression_points=channel_expression[ch],midi_channel=ch))
            elif name==FX_WASH:
                score['wash_triggers'].append(dict(start=start,end=end,velocity=velocity))
            elif name==FX_END:
                score['ending_triggers'].append(dict(start=start,end=end,midi=key,velocity=velocity))
            elif ch==9:
                part=DRUMS.get(key)
                if part is None:raise ValueError(f'Unsupported percussion key {key}; supported {DRUMS}')
                gain=velocity_gain(velocity)
                if part=='kick':score['kicks'].append(start);score['kick_velocity_db'][str(start)]=gain
                elif part=='hat':score['hats'].append({'source_seconds':start,'gain_db':gain})
                elif part.startswith('snare'):score['snares'].append([start,'ghost' if part=='snare_ghost' else 'hit',gain])
                else:score['bright_percussion'].append([start,gain])
            else:raise ValueError(f'Unknown musical track {name!r}')
    # Tempo context is the effective tempo at tick zero; note timing uses full map.
    score['tempo_context_bpm']=mido.tempo2bpm([v for t,v in tempos if t==0][-1])
    return score
