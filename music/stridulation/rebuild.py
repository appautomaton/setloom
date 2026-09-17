"""Rebuild STRIDULATION from its local MIDI and controls through final delivery."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT / 'source'))
import soundfile as sf
from audio_runtime import limit_peak_lookahead, write_audio, measure_loudness
from output_paths import validate_output


def run(args):
    subprocess.run(args, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='Output folder outside this source directory')
    parser.add_argument('--cover', type=Path, help='Optional external PNG/JPEG to embed in the M4A')
    parser.add_argument('--keep-intermediates', action='store_true', help='Keep synthesized parts, mix and floating-point intermediates')
    args = parser.parse_args()
    out = validate_output(args.out)
    if out.exists() and any(out.iterdir()):
        raise ValueError('Use a new or empty output folder to preserve existing renders.')
    cover = args.cover.expanduser().resolve(strict=True) if args.cover else None
    out.mkdir(parents=True, exist_ok=True)
    work = out / 'intermediates'
    settings = json.loads((PROJECT / 'source/delivery.json').read_text())
    cfg = settings['mastering']
    run([sys.executable, str(PROJECT / 'source/render.py'), '--out', str(work / 'mix')])
    premaster = work / 'mix/premaster-float.wav'
    audio, sr = sf.read(premaster, dtype='float32', always_2d=True)
    mastered = limit_peak_lookahead(
        audio * 10 ** (cfg['input_gain_db'] / 20), sample_rate=sr,
        ceiling_dbtp=cfg['ceiling_dbtp'], lookahead_ms=cfg['lookahead_ms'],
        release_ms=cfg['release_ms'],
    )
    mastered[-1] = 0
    raw_master = work / 'master-pcm24.wav'
    write_audio(raw_master, mastered, sample_rate=sr, subtype='PCM_24')
    wav = out / (settings['title'] + '.wav')
    m4a = out / (settings['title'] + '.m4a')
    metadata = []
    for key, value in [('title', settings['title']), ('artist', settings['artist']),
                       ('album', settings['title']), ('genre', settings['genre']),
                       ('comment', settings['comment'])]:
        metadata += ['-metadata', f'{key}={value}']
    ffmpeg = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin']
    run(ffmpeg + ['-i', str(raw_master), '-map', '0:a:0', '-c:a', 'copy'] + metadata + [str(wav)])
    command = ffmpeg + ['-i', str(wav)]
    if cover:
        command += ['-i', str(cover)]
    command += ['-map', '0:a:0']
    if cover:
        command += ['-map', '1:v:0']
    command += ['-c:a', 'aac', '-b:a', settings['aac_bitrate']]
    if cover:
        command += ['-c:v', 'copy', '-disposition:v:0', 'attached_pic']
    run(command + ['-movflags', '+faststart'] + metadata + [str(m4a)])
    report = {
        'input': 'Local MIDI, note controls, instruments, voice and mix settings; no input recording',
        'duration_seconds': len(audio) / sr,
        'sample_rate': sr,
        'mastering': cfg,
        'cover': str(cover) if cover else None,
        'measurements': {p.name: measure_loudness(p) for p in [wav, m4a]},
        'sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [wav, m4a]},
        'source_sha256': {
            str(p.relative_to(PROJECT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in PROJECT.rglob('*') if p.is_file() and '__pycache__' not in p.parts
        },
    }
    (out / 'rebuild-report.json').write_text(json.dumps(report, indent=2) + '\n')
    if not args.keep_intermediates:
        shutil.rmtree(work)
    print(json.dumps({'output': str(out), 'measurements': report['measurements']}, indent=2))


if __name__ == '__main__':
    main()
