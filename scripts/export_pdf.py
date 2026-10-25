#!/usr/bin/env python3
"""Print the same local chapter HTML to PDF with an installed Chromium."""
import os,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
chrome=shutil.which('chromium') or shutil.which('google-chrome') or shutil.which('chromium-browser')
if not chrome:raise SystemExit('Install Chromium from an official source, or print site/book.html manually.')
out=ROOT/'output/pdf/learn-deepseek-harness-zh.pdf';out.parent.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='harness-pdf-') as profile:
    # The application sandbox in some containers cannot host Chromium's nested
    # process sandbox. --no-sandbox is deliberately NOT supplied by this script.
    flags=[chrome,'--headless','--disable-gpu','--no-pdf-header-footer',f'--user-data-dir={profile}',f'--print-to-pdf={out}',(ROOT/'site/book.html').as_uri()]
    subprocess.run(flags,check=True,timeout=120)
if not out.exists() or out.stat().st_size<1000:raise SystemExit('PDF was not produced')
subprocess.run([os.environ.get('CODEX_PRIMARY_RUNTIME_PYTHON','python3'), str(ROOT/'scripts/normalize_pdf_text.py'), str(out)],check=True)
print(out)
