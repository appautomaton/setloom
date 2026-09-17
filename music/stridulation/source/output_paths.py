"""Keep generated audio outside the shareable source directory."""
from pathlib import Path
PROJECT = Path(__file__).resolve().parents[1]

def validate_output(path):
    result = Path(path).expanduser().resolve()
    if result == PROJECT or PROJECT in result.parents:
        raise ValueError('Choose an output directory outside the STRIDULATION source folder.')
    return result
