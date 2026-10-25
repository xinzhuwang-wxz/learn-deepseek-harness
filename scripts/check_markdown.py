#!/usr/bin/env python3
"""Check repository-relative Markdown links and exact code-line ranges, read-only."""
from pathlib import Path
import re
from urllib.parse import unquote, urlparse
ROOT = Path(__file__).resolve().parents[1]
paths = sorted((ROOT / 'docs').glob('*.md')) + [ROOT / 'README.md', ROOT / 'PUBLISHING.md']
count = 0
for path in paths:
    text = path.read_text()
    assert '[[source:' not in text, str(path) + ': unresolved source link'
    for href in re.findall(r'!?\[[^\]\n]*\]\(([^\s)]+)\)', text):
        url = urlparse(href)
        if url.scheme or url.netloc or not url.path:
            continue
        target = (path.parent / unquote(url.path)).resolve()
        assert target.is_relative_to(ROOT) and target.is_file(), f'{path.name}: missing {href}'
        if target.suffix == '.py' and url.fragment:
            m = re.fullmatch(r'L(\d+)(?:-L(\d+))?', url.fragment)
            assert m, f'{path.name}: invalid code-line fragment {href}'
            first, last = int(m[1]), int(m[2] or m[1])
            assert 1 <= first <= last <= len(target.read_text().splitlines()), href
        count += 1
print(f'{count} local Markdown links and code ranges verified; no sources rewritten')
