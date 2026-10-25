#!/usr/bin/env python3
"""Run authored offline walkthroughs and compare committed observations; never rewrite them."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
for expected in sorted((ROOT / 'walkthroughs/expected').glob('s*.json')):
    script = ROOT / 'walkthroughs' / (expected.stem + '.py')
    result = subprocess.run([sys.executable, str(script), 'all'], cwd=ROOT,
                            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                            capture_output=True, text=True, timeout=10, check=True)
    if json.loads(result.stdout) != json.loads(expected.read_text()):
        raise SystemExit(f'{script.relative_to(ROOT)}: output differs from {expected.relative_to(ROOT)}. '
                         'Review your edit and explain the change; this check does not overwrite either file.')
    print(expected.stem + ': actual output matches committed observations')
