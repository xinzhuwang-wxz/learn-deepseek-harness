#!/usr/bin/env python3
"""Explicitly restore selected reference files from an audited, pinned checkout.

This is not part of site builds. It never executes upstream code, changes course
prose, or chooses new anchors. Update sources.json only after reviewing a change.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-checkout', type=Path, required=True)
    args = parser.parse_args()
    source = args.from_checkout.resolve()
    lock = json.loads((ROOT / 'upstream.lock.json').read_text())['target']
    commit = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                            text=True, capture_output=True, check=True).stdout.strip()
    if commit != lock['commit']:
        raise SystemExit('Checkout HEAD differs from the committed source lock.')
    records = json.loads((ROOT / 'sources.json').read_text())
    selected = {}
    for record in records.values():
        path = record['path']
        data = (source / path).read_bytes()
        if hashlib.sha256(data).hexdigest() != record['sha256']:
            raise SystemExit('Source bytes differ from reviewed hash: ' + path)
        selected[path] = data
    if (source / 'LICENSE').read_bytes() != (ROOT / 'legal/DeepSeek-Harness-MIT.txt').read_bytes():
        raise SystemExit('License differs; review the upstream license before copying.')
    # Check every selected file and the license before writing any destination.
    for path, data in selected.items():
        target = ROOT / 'reference/upstream' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    print(f'Restored {len(selected)} fixed reference files; no runtime code executed.')

if __name__ == '__main__':
    main()
