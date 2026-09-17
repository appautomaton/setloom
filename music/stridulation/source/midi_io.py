"""Editable note timing/pitch/velocity with stable links to instrument controls."""
from pathlib import Path
from collections import defaultdict, deque
import json
import mido

HERE=Path(__file__).resolve().parent

def export():
    score=json.loads((HERE/"performance.json").read_text())
    midi=mido.MidiFile(ticks_per_beat=960)
    tempo=mido.bpm2tempo(score["bpm"])
    conductor=mido.MidiTrack()
    conductor.append(mido.MetaMessage("set_tempo",tempo=tempo,time=0))
    conductor.append(mido.MetaMessage("time_signature",numerator=4,denominator=4,time=0))
    midi.tracks.append(conductor)
    (HERE/"midi").mkdir(exist_ok=True)
    for part in score["tracks"]:
        track=mido.MidiTrack([mido.MetaMessage("track_name",name=part["name"],time=0)])
        events=[]
        for n in part["notes"]:
            start=round(mido.second2tick(n["start"],960,tempo))
            end=max(start+1,round(mido.second2tick(n["end"],960,tempo)))
            events += [
                (start,1,mido.MetaMessage("text",text="event="+n["curve"])),
                (start,1,mido.Message("note_on",channel=part["channel"],note=n["pitch"],velocity=n["velocity"])),
                (end,0,mido.Message("note_off",channel=part["channel"],note=n["pitch"],velocity=0)),
            ]
        last=0
        for tick,_,message in sorted(events,key=lambda e:(e[0],e[1])):
            track.append(message.copy(time=tick-last));last=tick
        midi.tracks.append(track)
        one=mido.MidiFile(ticks_per_beat=960)
        one.tracks.extend([conductor.copy(),track.copy()])
        one.save(HERE/"midi"/(part["name"]+".mid"))
    midi.save(HERE/"STRIDULATION.mid")

def read(path):
    midi=mido.MidiFile(path)
    tempo=400000
    result={}
    for track in midi.tracks:
        now=0;name=None;event=None;active=defaultdict(deque);notes=[]
        for msg in track:
            now+=mido.tick2second(msg.time,midi.ticks_per_beat,tempo)
            if msg.type=="set_tempo":tempo=msg.tempo
            elif msg.type=="track_name":name=msg.name
            elif msg.type=="text" and msg.text.startswith("event="):event=msg.text[6:]
            elif msg.type=="note_on" and msg.velocity:
                active[msg.note].append({"pitch":msg.note,"start":now,"velocity":msg.velocity,"curve":event})
                event=None
            elif msg.type=="note_off" or (msg.type=="note_on" and not msg.velocity):
                if active[msg.note]:
                    n=active[msg.note].popleft();n["end"]=now;notes.append(n)
        if name:result[name]=sorted(notes,key=lambda n:(n["start"],n["pitch"]))
    return result

if __name__=="__main__":export()
