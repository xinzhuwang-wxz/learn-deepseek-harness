#!/usr/bin/env python3
"""Render committed Markdown and code with Pandoc; never regenerate source files."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import unquote, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]


def render(text: str) -> str:
    return subprocess.run(['pandoc', '-f', 'markdown+fenced_divs+link_attributes',
                           '-t', 'html5', '--section-divs', '--highlight-style=pygments'],
                          input=text, text=True, capture_output=True, check=True).stdout


def relocate(body, origin, chapters):
    """Resolve authored Markdown-relative links into a flat, subpath-safe site."""
    routes = {str((ROOT / c['file']).resolve()): c['slug'] + '.html' for c in chapters}
    def link(match):
        attr, encoded = match.groups()
        href = html.unescape(encoded)
        url = urlsplit(href)
        if url.scheme or url.netloc or not url.path:
            return match[0]
        target = (origin.parent / unquote(url.path)).resolve()
        if not target.is_relative_to(ROOT):
            raise ValueError(f'{origin}: link leaves course directory: {href}')
        path = routes.get(str(target), target.relative_to(ROOT).as_posix())
        fragment = url.fragment
        if target.suffix == '.py' and target.is_file():
            path += '.html'
            if re.fullmatch(r'L\d+-L\d+', fragment):
                fragment = fragment.split('-')[0]
        return attr + '="' + html.escape(urlunsplit(('', '', path, url.query, fragment)), quote=True) + '"'
    return re.sub(r'(href|src)="([^"]+)"', link, body)


def diagram_links(body):
    def wrap(match):
        tag, src = match.group(0), match.group(1)
        if not src.lower().endswith('.svg'):
            return tag
        return ('<span class="diagram-scroll" tabindex="0" role="region" aria-label="机制图，可横向滚动"><a class="diagram-image" href="' + src + '">' + tag +
                '</a></span><a class="diagram-original" href="' + src + '">打开原图 / 放大 ↗</a>')
    return re.sub(r'<img\b[^>]*\bsrc="([^"]+)"[^>]*>', wrap, body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', default='site')
    args = parser.parse_args()
    inputs = [p for folder in ('docs', 'lessons', 'walkthroughs', 'examples', 'assets')
              for p in (ROOT / folder).rglob('*')
              if p.is_file() and '__pycache__' not in p.parts]
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    cfg = json.loads((ROOT / 'book.json').read_text())
    sources = json.loads((ROOT / 'sources.json').read_text())
    out = (ROOT / args.site).resolve()
    if not out.is_relative_to(ROOT) or out == ROOT or out.parts[len(ROOT.parts)] not in {'site', 'tmp'}:
        raise SystemExit('--site must be site/ or an output directory below tmp/')
    out.mkdir(exist_ok=True, parents=True)
    for folder in ('assets', 'lessons', 'walkthroughs', 'docs', 'legal', 'reference', 'examples'):
        shutil.copytree(ROOT / folder, out / folder, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('LICENSE', 'sources.json', 'upstream.lock.json', 'README.md', 'QA_REPORT.md', 'PUBLISHING.md'):
        shutil.copy2(ROOT / name, out / name)
    # Old local exports are not course downloads and never enter a new site build.
    for old in out.rglob('*.pdf'):
        old.unlink()
    chapters = cfg['chapters']
    records, bodies, canon = [], [], []
    for ch in chapters:
        raw = (ROOT / ch['file']).read_text()
        if '[[source:' in raw:
            raise ValueError(f'{ch["file"]}: use real Markdown source links, not placeholders')
        body = diagram_links(relocate(render(raw), ROOT / ch['file'], chapters))
        body = body.replace('<pre', '<pre tabindex="0" aria-label="代码或输出，可横向滚动"')
        records.append({**ch, 'url': ch['slug'] + '.html', 'text': html.unescape(re.sub(r'<[^>]+>', ' ', body))})
        bodies.append(body)
        canon.append(raw)
    (out / 'assets/search-data.js').write_text('window.LEARN_SEARCH = ' + json.dumps(records, ensure_ascii=False) + ';\n')
    nav = ''.join('<a class="nav-link" data-chapter="' + html.escape(ch['slug']) + '" href="' + ch['slug'] + '.html"><span>' + f'{i:02d}' + '</span>' + html.escape(ch['title']) + '</a>' for i, ch in enumerate(chapters))
    def shell(title, body, active='', pager=''):
        return ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="' + html.escape(cfg['description']) + '"><title>' + html.escape(title + ' · ' + cfg['title']) + '</title><link rel="stylesheet" href="assets/style.css"><script defer src="assets/search-data.js"></script><script defer src="assets/site.js"></script><script defer src="assets/trace-data.js"></script><script defer src="assets/trace.js"></script></head><body data-book="' + html.escape(cfg['title']) + '" data-active="' + active + '"><a class="skip" href="#main">跳至正文</a><header class="topbar"><a class="brand" href="index.html"><span class="mark">H·</span>' + html.escape(cfg.get('nav_title', cfg['title'])) + '</a><div class="top-actions"><a href="book.html">整本阅读 ↗</a><button id="theme" aria-label="切换深浅主题">◐</button><button id="menu" aria-controls="sidebar" aria-expanded="false">目录</button></div></header><aside id="sidebar"><div class="nav-label">LEARNING PATH / 学习路径</div><nav aria-label="章节">' + nav + '</nav><div class="source-lock">SOURCE LOCK<br><a href="' + cfg['repo'] + '/tree/' + cfg['commit'] + '">' + cfg['commit'][:12] + '</a><br>教学实现 ≠ 生产运行</div></aside><main id="main"><div class="search-wrap"><label for="search">搜索课程</label><input id="search" type="search" placeholder="输入关键词，如 权限、并发…  /" autocomplete="off"><div id="search-results" aria-live="polite"></div></div>' + body + pager + '<footer>独立教学项目，非上游官方教程。正文以 Markdown 维护，代码与图均可离线阅读。<br>固定来源 · 可运行实验 · 明确边界</footer></main></body></html>')
    cards = ''.join('<a class="chapter-card" href="' + ch['slug'] + '.html"><span class="card-num">' + f'{i:02d}' + '</span><div><h2>' + html.escape(ch['title']) + '</h2><p>' + html.escape(ch.get('summary', '')) + '</p><small>' + html.escape(ch.get('time', '')) + '</small></div><span class="arrow">↗</span></a>' for i, ch in enumerate(chapters))
    intro = '<section class="hero"><p class="eyebrow">SOURCE → CONCEPT → EXPERIMENT → EVIDENCE</p><h1>' + html.escape(cfg['title']) + '</h1><p class="hero-tagline">' + html.escape(cfg['tagline']) + '</p><p>' + html.escape(cfg['description']) + '</p><div class="hero-meta"><span>8 个累计实验</span><span>零凭据 · 纯内存</span><span>固定源码版本</span></div></section><div class="quicklinks"><a href="s01-loop.html">开始 S01 →</a><a href="traces.html">打开轨迹实验室</a><a href="book.html">整本阅读</a></div><section class="chapter-grid" aria-label="课程">' + cards + '</section>'
    (out / 'index.html').write_text(shell('课程首页', intro))
    for i, (ch, body) in enumerate(zip(chapters, bodies)):
        pager = '<div class="lesson-actions"><button class="complete" data-complete="' + ch['slug'] + '">标记学完</button><span class="progress" aria-live="polite"></span></div><nav class="pager" aria-label="前后章节">'
        if i:
            pager += '<a href="' + chapters[i - 1]['slug'] + '.html">← ' + html.escape(chapters[i - 1]['title']) + '</a>'
        if i + 1 < len(chapters):
            pager += '<a href="' + chapters[i + 1]['slug'] + '.html">' + html.escape(chapters[i + 1]['title']) + ' →</a>'
        pager += '</nav>'
        bar = '<div class="source-bar"><a href="' + ch['file'] + '" download>下载 Markdown</a>'
        if ch.get('lesson'):
            lesson = ch['lesson']
            bar += '<a href="lessons/' + lesson + '/code.py.html">阅读本课完整代码</a><a href="lessons/' + lesson + '/code.py" download>下载代码</a>'
            if (ROOT / 'lessons' / lesson / 'delta.patch').exists():
                bar += '<a href="lessons/' + lesson + '/delta.patch">相邻阶段差异</a>'
        bar += '</div>'
        (out / (ch['slug'] + '.html')).write_text(shell(ch['title'], bar + '<article>' + body + '</article>', ch['slug'], pager))
    toc = '<section class="book-title"><p class="eyebrow">' + html.escape(cfg['title']) + '</p><h1>' + html.escape(cfg['tagline']) + '</h1><p>' + html.escape(cfg['description']) + '</p><p>源码基线 ' + cfg['commit'] + '<br>来源与许可见附录。</p></section><section class="book-toc"><h1>目录</h1><ol>' + ''.join('<li><a href="#chapter-' + ch['slug'] + '">' + html.escape(ch['title']) + '</a></li>' for ch in chapters) + '</ol></section>'
    def book_body(ch, body):
        prefix = 'bk-' + ch['slug'] + '-'
        body = re.sub(r'id="([^"]+)"', lambda m: 'id="' + (m[1] if m[1].startswith('trace-') else prefix + m[1]) + '"', body)
        return re.sub(r'href="#([^"]+)"', lambda m: 'href="#' + prefix + m[1] + '"', body)
    book = toc + ''.join('<article class="book-chapter" id="chapter-' + ch['slug'] + '">' + book_body(ch, body) + '</article>' for ch, body in zip(chapters, bodies))
    (out / 'book.html').write_text(shell('完整教程', book))
    for path in sorted(out.rglob('*.py')):
        prefix = Path(os.path.relpath(out, path.parent)).as_posix() + '/'
        lines = ''.join('<span class="code-line" id="L' + str(n) + '"><a class="line-no" href="#L' + str(n) + '" aria-label="第 ' + str(n) + ' 行">' + str(n) + '</a>' + html.escape(line) + '</span>' for n, line in enumerate(path.read_text().splitlines(), 1))
        page = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(str(path.relative_to(out))) + '</title><link rel="stylesheet" href="' + prefix + 'assets/style.css"></head><body><main class="source-view"><nav><a href="' + prefix + 'index.html">课程首页</a> · <a href="' + path.name + '" download>下载原始代码</a></nav><h1>' + html.escape(str(path.relative_to(out))) + '</h1><pre class="code-file"><code>' + lines + '</code></pre></main></body></html>'
        path.with_suffix(path.suffix + '.html').write_text(page)
    (ROOT / 'output').mkdir(exist_ok=True)
    (ROOT / 'output/book.md').write_text('\n\n'.join(canon))
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    if before != after:
        raise RuntimeError('A source file changed during rendering; site build must be read-only on authored inputs.')
    manifest = {'title': cfg['title'], 'upstream_commit': cfg['commit'], 'chapter_count': len(chapters), 'canonical_sha256': hashlib.sha256(('\n\n'.join(canon)).encode()).hexdigest(), 'chapter_files': [ch['file'] for ch in chapters], 'pdf_included': False, 'source_files_rewritten': False}
    (out / 'build-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
