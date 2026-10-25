#!/usr/bin/env python3
"""Check marked Markdown excerpts against local teaching code, without importing it."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r'<!-- snippet: ([^\n:]+):(\d+):(\d+) -->\n```python\n(.*?)\n```', re.S)


def check(paths):
    checked, errors = 0, []
    for path in paths:
        text = path.read_text(encoding='utf-8')
        matches = list(PATTERN.finditer(text))
        if text.count('<!-- snippet:') != len(matches):
            errors.append(f'{path.relative_to(ROOT)}: malformed snippet marker')
        for match in matches:
            name, first, last, block = match.groups()
            source = (ROOT / name).resolve()
            if not source.is_relative_to(ROOT) or not source.is_file():
                errors.append(f'{path.relative_to(ROOT)}: invalid source {name}')
                continue
            lines = source.read_text(encoding='utf-8').splitlines()
            first, last = int(first), int(last)
            expected = '\n'.join(lines[first - 1:last])
            if not 1 <= first <= last <= len(lines) or block != expected:
                errors.append(f'{path.relative_to(ROOT)}: excerpt differs from {name}:{first}-{last}')
            checked += 1
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'{checked} exact teaching-code excerpts verified in {len(paths)} Markdown file(s)')
    return checked


if __name__ == '__main__':
    paths = [(ROOT / p).resolve() for p in sys.argv[1:]] if sys.argv[1:] else sorted((ROOT / 'docs').glob('*.md'))
    check(paths)
