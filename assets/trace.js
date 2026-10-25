(() => {
  const root = document.querySelector('[data-trace-lab]');
  if (!root || !window.HARNESS_TRACES) return;
  const cases = window.HARNESS_TRACES;
  const select = document.getElementById('trace-case');
  cases.forEach((c, i) => { const o = document.createElement('option'); o.value = i; o.textContent = c.title; select.append(o); });
  let current = 0, cursor = 0;
  const render = () => {
    const frames = cases[current].frames, f = frames[cursor];
    document.getElementById('trace-event').textContent = JSON.stringify(f.event, null, 2);
    document.getElementById('trace-projection').textContent = JSON.stringify(f.visible_messages, null, 2);
    document.getElementById('trace-position').textContent = `${cursor + 1} / ${frames.length}`;
    document.getElementById('trace-observation').textContent = `日志已有 ${f.durable_count} 条事实，模型可见 ${f.visible_count} 条消息。两者不是同一个列表。`;
    document.getElementById('trace-prev').disabled = cursor === 0;
    document.getElementById('trace-next').disabled = cursor === frames.length - 1;
  };
  select.addEventListener('change', () => { current = Number(select.value); cursor = 0; render(); });
  document.getElementById('trace-prev').addEventListener('click', () => { cursor = Math.max(0, cursor - 1); render(); });
  document.getElementById('trace-next').addEventListener('click', () => { cursor = Math.min(cases[current].frames.length - 1, cursor + 1); render(); });
  document.getElementById('trace-reset').addEventListener('click', () => { cursor = 0; render(); });
  render();
})();
