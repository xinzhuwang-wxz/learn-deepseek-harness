(() => {
  const body=document.body, storageKey='learn-progress:'+body.dataset.book;
  let progress={}; try { progress=JSON.parse(localStorage.getItem(storageKey)||'{}'); } catch {}
  const store=()=>{try{localStorage.setItem(storageKey,JSON.stringify(progress));}catch{}};
  const update=()=>{
    document.querySelectorAll('[data-chapter]').forEach(a=>{a.classList.toggle('done',!!progress[a.dataset.chapter]);if(a.dataset.chapter===body.dataset.active)a.setAttribute('aria-current','page');});
    document.querySelectorAll('[data-complete]').forEach(b=>{const done=!!progress[b.dataset.complete];b.textContent=done?'已学完 ✓ · 再次点击撤销':'标记学完';b.setAttribute('aria-pressed',String(done));});
    document.querySelectorAll('.progress').forEach(e=>e.textContent=Object.values(progress).filter(Boolean).length+' / '+(window.LEARN_SEARCH||[]).length+' 节完成（仅存本机）');
  };
  document.querySelectorAll('[data-complete]').forEach(b=>b.addEventListener('click',()=>{progress[b.dataset.complete]=!progress[b.dataset.complete];store();update();})); update();
  try{body.dataset.theme=localStorage.getItem('learn-theme')||'light';}catch{}
  document.getElementById('theme')?.addEventListener('click',()=>{body.dataset.theme=body.dataset.theme==='dark'?'light':'dark';try{localStorage.setItem('learn-theme',body.dataset.theme);}catch{}});
  const menu=document.getElementById('menu');menu?.addEventListener('click',()=>{const open=body.classList.toggle('menu-open');menu.setAttribute('aria-expanded',String(open));});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'){body.classList.remove('menu-open');menu?.setAttribute('aria-expanded','false');}if(e.key==='/'&&!['INPUT','TEXTAREA'].includes(document.activeElement.tagName)){e.preventDefault();document.getElementById('search').focus();}});
  const input=document.getElementById('search'),results=document.getElementById('search-results');
  input?.addEventListener('input',()=>{
    results.replaceChildren();const q=input.value.trim().toLocaleLowerCase();if(!q)return;
    const terms=q.split(/\s+/),matches=(window.LEARN_SEARCH||[]).filter(r=>terms.every(t=>(r.title+' '+r.text).toLocaleLowerCase().includes(t)));
    const status=document.createElement('p');status.textContent=matches.length+' 个章节匹配';results.append(status);
    for(const r of matches){const a=document.createElement('a');a.href=r.url;const title=document.createElement('strong');title.textContent=r.title;const p=document.createElement('span');const pos=r.text.toLocaleLowerCase().indexOf(terms[0]);p.textContent=r.text.slice(Math.max(0,pos-35),Math.max(0,pos-35)+150).replace(/\s+/g,' ');a.append(title,p);results.append(a);}
  });
})();
