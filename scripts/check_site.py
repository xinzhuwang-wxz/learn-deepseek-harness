#!/usr/bin/env python3
"""Offline HTML validation at both origin root and a GitHub Pages project subpath."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
import json

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links = [], []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        for key in ('href', 'src'):
            if key in attrs:
                self.links.append(attrs[key])

parsed = {}
for path in SITE.rglob('*.html'):
    page = Page()
    text = path.read_text()
    page.feed(text)
    parsed[path.resolve()] = page
    assert '[[source:' not in text, path
    assert not [key for key, n in Counter(page.ids).items() if n > 1], str(path) + ' duplicate IDs'
assert parsed, 'Build site/ before checking links.'
checks = 0
for prefix in ('/', '/learn-deepseek-harness/'):
    for path, page in parsed.items():
        current = 'https://course.invalid' + prefix + path.relative_to(SITE).as_posix()
        for href in page.links:
            given = urlparse(href)
            if given.scheme or given.netloc:
                continue
            absolute = urlparse(urljoin(current, href))
            assert absolute.path.startswith(prefix), f'{path.name}: leaves project prefix: {href}'
            target = (SITE / unquote(absolute.path[len(prefix):])).resolve()
            assert target.is_relative_to(SITE), f'{path.name}: escapes site: {href}'
            assert target.is_file(), f'{path.name}: missing {href}'
            if absolute.fragment and target in parsed:
                assert unquote(absolute.fragment) in parsed[target].ids, f'{path.name}: missing anchor {href}'
            checks += 1
assert not list(SITE.rglob('*.pdf')), 'Default site must not contain PDF exports.'
print(json.dumps({'pages': len(parsed), 'relative_links_and_fragments': checks,
                  'prefixes': ['/', '/learn-deepseek-harness/'], 'unique_ids': 'passed',
                  'source_placeholders': 0, 'pdf_files': 0}, indent=2))
