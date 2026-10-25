#!/usr/bin/env python3
"""Offline source-lock and authored-content validation; no network required."""
from pathlib import Path
import hashlib,json,re,ast
ROOT=Path(__file__).resolve().parents[1]
sources=json.loads((ROOT/'sources.json').read_text())
lock=json.loads((ROOT/'upstream.lock.json').read_text())
cfg=json.loads((ROOT/'book.json').read_text())
for key,item in sources.items():
    p=ROOT/'reference/upstream'/item['path'];data=p.read_bytes();lines=data.decode().splitlines()
    assert hashlib.sha256(data).hexdigest()==item['sha256'],key+' hash'
    assert 1<=item['start']<=item['end']<=len(lines),key+' range'
    assert item['symbol'] in lines[item['start']-1],key+' symbol'
    assert lock['target']['commit'] in item['url'],key+' commit'
slugs=set()
for ch in cfg['chapters']:
    assert ch['slug'] not in slugs;slugs.add(ch['slug'])
    text=(ROOT/ch['file']).read_text();assert text.startswith('# '),ch['file']
    for key in re.findall(r'\[\[source:([^\]]+)\]\]',text):assert key in sources,key
    for asset in re.findall(r'!\[[^\]]*\]\((\.\./assets/[^)]+)\)',text):assert (ROOT/ch['file']).parent.joinpath(asset).exists(),asset
for p in (ROOT/'lessons').glob('*/code.py'):
    tree=ast.parse(p.read_text())
    imports=[alias.name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import) for alias in n.names]
    imports += [n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module]
    assert not set(imports) & {'subprocess','urllib','requests','os','socket'},str(p)
print(json.dumps({'source_anchors':len(sources),'chapters':len(cfg['chapters']),'standalone_lessons':len(list((ROOT/'lessons').glob('*/code.py'))),'status':'passed'},indent=2))
