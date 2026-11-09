# SPDX-License-Identifier: AGPL-3.0-only
"""Master the approved Palimpsest mixes serially with Setloom's shared peak control."""

import json
from pathlib import Path
import subprocess

import numpy as np
import soundfile as sf

from setloom.audio import measure_loudness, write_audio, write_master

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parents[1]/"tmp/palimpsest"


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+"\n")


def main():
    source=json.loads((OUT/"render/manifest.json").read_text())
    config=json.loads((ROOT/"source/mastering.json").read_text())
    assert source["revision"]==config["source_revision"]
    parameters={key:config[key] for key in ("target_lufs","input_gain_db","ceiling_dbtp",
                "lookahead_ms","release_ms","tolerance_lu")}
    manifest={"revision":config["revision"],"edition":config["edition"],"source_revision":source["revision"],
        "frames":source["frames"],"sample_rate":source["sample_rate"],"duration_s":source["duration_s"],
        "processing":parameters,"rationale":config["rationale"],"lossless_format":"FLAC","preview_bitrate":"256k","views":{},
        "scope":"Technical mastering delivery"}
    for kick in (item for item in source["kicks"] if item["id"] == "round"):
        key="mix-"+kick["id"]
        audio,rate=sf.read(OUT/source["views"][key]["wav"],dtype="float32",always_2d=True)
        destination=OUT/"master/palimpsest.flac"
        destination.parent.mkdir(parents=True,exist_ok=True)
        print("Mastering",kick["label"],flush=True)
        # Preserve the established PCM24 quantization before lossless compression.
        temporary_master=destination.with_suffix('.working.wav')
        try:
            result=write_master(temporary_master,audio,sample_rate=rate,**parameters)
            subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-i',str(temporary_master),
                            '-map_metadata','-1','-c:a','flac','-compression_level','8',
                            '-threads','1',str(destination)],check=True)
            quantized,quantized_rate=sf.read(temporary_master,dtype='float32',always_2d=True)
            compressed,compressed_rate=sf.read(destination,dtype='float32',always_2d=True)
            assert quantized_rate==compressed_rate and np.array_equal(quantized,compressed)
            del quantized,compressed
        finally:
            temporary_master.unlink(missing_ok=True)
        print("Measured",result["measured"],flush=True)
        assert result["within_target_tolerance"] and result["within_peak_ceiling"],result
        mastered,master_rate=sf.read(destination,dtype="float32",always_2d=True)
        assert master_rate==rate and mastered.shape==audio.shape and np.isfinite(mastered).all()
        assert np.max(np.abs(mastered))<1
        encoded=OUT/"audio/palimpsest.m4a"
        encoded.parent.mkdir(parents=True,exist_ok=True)
        preview_gain=0.0
        def encode(input_path):
            subprocess.run(["ffmpeg","-v","error","-nostdin","-y","-threads","1", "-i",str(input_path),
                            "-c:a","aac","-b:a","256k",str(encoded)],check=True)
        encode(destination)
        preview=measure_loudness(encoded)
        if preview["true_peak_dbtp"]>config["preview_peak_ceiling_dbtp"]:
            preview_gain=config["preview_peak_ceiling_dbtp"]-preview["true_peak_dbtp"]-.15
            temporary=encoded.with_suffix(".preview-input.wav")
            write_audio(temporary,mastered*10**(preview_gain/20),sample_rate=rate,subtype="FLOAT")
            try:encode(temporary)
            finally:temporary.unlink()
            preview=measure_loudness(encoded)
        assert preview["true_peak_dbtp"]<=config["preview_peak_ceiling_dbtp"]
        decoded=subprocess.check_output(["ffmpeg","-v","error","-nostdin","-threads","1","-i",str(encoded),
                "-f","f32le","-ac","2","-ar",str(rate),"pipe:1"])
        decoded=np.frombuffer(decoded,dtype="<f4").reshape(-1,2)
        assert abs(len(decoded)-len(mastered))<=1024 and np.isfinite(decoded).all()
        assert np.max(np.abs(decoded))<1
        length=min(len(decoded),len(mastered))
        expected=mastered[:length]*10**(preview_gain/20)
        error=np.sqrt(np.mean((decoded[:length]-expected)**2))
        snr=float(20*np.log10(np.sqrt(np.mean(expected**2))/max(error,1e-12)))
        assert snr>22,snr
        manifest["views"][key]={"path":str(encoded.relative_to(OUT)),"lossless":str(destination.relative_to(OUT)),"master":result,
            "measured_preview":preview,"preview_attenuation_db":preview_gain,
            "decoded_frames":len(decoded),"preview_error_snr_db":snr,
            "activity":[round(float(np.sqrt(np.mean(block**2))),6) for block in np.array_split(mastered,352)]}
        del audio,mastered,decoded,expected
    manifest["status"]="passed"
    save(OUT/"master/manifest.json",manifest)
    print("One PCM24 FLAC master and its fully decoded AAC 256 kbps preview are ready.",flush=True)


if __name__=="__main__":main()
