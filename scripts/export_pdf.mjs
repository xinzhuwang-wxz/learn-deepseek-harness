/** Reproducible sandboxed print path; uses an installed, trusted Playwright. */
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const moduleName=process.env.PLAYWRIGHT_MODULE || 'playwright-core';
const { chromium }=await import(moduleName.startsWith('/')?pathToFileURL(moduleName).href:moduleName);
const browser=await chromium.launch({headless:true,chromiumSandbox:true,...(process.env.HARNESS_CHROMIUM?{executablePath:process.env.HARNESS_CHROMIUM}:{}),args:['--disable-dev-shm-usage']});
try {
 const page=await browser.newPage();
 await page.goto(pathToFileURL(path.join(root,'site/book.html')).href,{waitUntil:'load'});
 await page.evaluate(()=>document.fonts.ready);
 await page.emulateMedia({media:'print'});
 const dir=path.join(root,'output/pdf');await fs.mkdir(dir,{recursive:true});
 await page.pdf({path:path.join(dir,'learn-deepseek-harness-zh.pdf'),format:'A4',preferCSSPageSize:true,printBackground:true,displayHeaderFooter:true,headerTemplate:'<span></span>',footerTemplate:'<div style="font-size:8px;color:#536783;width:100%;padding:0 17mm;display:flex;justify-content:space-between"><span>Learn DeepSeek Harness · 22ddee379240</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'});
 console.log('PDF exported from the same canonical chapter HTML with browser sandbox enabled.');
} finally {await browser.close();}

const correction=spawnSync(process.env.CODEX_PRIMARY_RUNTIME_PYTHON||'python3',[path.join(root,'scripts/normalize_pdf_text.py'),path.join(root,'output/pdf/learn-deepseek-harness-zh.pdf')],{stdio:'inherit'});
if(correction.status!==0)throw new Error('PDF text-map validation/correction failed');
