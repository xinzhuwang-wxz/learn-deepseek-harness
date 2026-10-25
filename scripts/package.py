#!/usr/bin/env python3
"""Create a deterministic source bundle; generated sites are opt-in, PDFs excluded."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {'.gitignore', 'LICENSE', 'Makefile', 'PUBLISHING.md', 'QA_REPORT.md',
              'README.md', 'book.json', 'sources.json', 'upstream.lock.json'}
SOURCE_DIRS = {'.github', 'assets', 'docs', 'examples', 'legal', 'lessons',
               'reference', 'scripts', 'tests', 'walkthroughs'}
EXCLUDE = {'.git', '__pycache__', '.pytest_cache', 'node_modules', '.venv',
           'research', 'tmp', 'output', 'dist'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-site', action='store_true',
                        help='Also include the already-checked static site; never PDFs or QA screenshots.')
    args = parser.parse_args()
    allowed = SOURCE_DIRS | ({'site'} if args.include_site else set())
    files = []
    for path in sorted(ROOT.rglob('*')):
        relative = path.relative_to(ROOT)
        if not path.is_file() or path.is_symlink() or set(relative.parts) & EXCLUDE:
            continue
        if path.suffix.lower() in {'.pdf', '.pyc', '.pyo'} or path.name.startswith('.env'):
            continue
        if (len(relative.parts) == 1 and path.name in ROOT_FILES) or relative.parts[0] in allowed:
            files.append((relative, path.read_bytes()))
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    output = dist / ('learn-deepseek-harness-with-site.zip' if args.include_site else 'learn-deepseek-harness-source.zip')
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for relative, data in files:
            info = zipfile.ZipInfo(str(Path(ROOT.name) / relative), date_time=(2026, 10, 25, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    tree = ''.join(str(relative) + '\0' + hashlib.sha256(data).hexdigest() + '\n' for relative, data in files)
    metadata = {'file': output.name, 'bytes': output.stat().st_size,
                'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                'source_tree_sha256': hashlib.sha256(tree.encode()).hexdigest(),
                'files': len(files), 'static_site_included': args.include_site, 'pdf_included': False}
    (dist / 'manifest.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata, indent=2))

if __name__ == '__main__':
    main()
