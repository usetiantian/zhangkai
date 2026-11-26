// 妖刀录 · 微信模拟器启动诊断：开 Runtime → 点编译 → 抓控制台和异常
const PORT = 9333;
const sleep = ms => new Promise(r => setTimeout(r, ms));

function connect(url) {
  const ws = new WebSocket(url);
  let id = 0; const pend = new Map(); const logs = []; const ctxIds = [];
  ws.onmessage = e => {
    let m; try { m = JSON.parse(e.data); } catch (x) { return; }
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); return; }
    if (m.method === 'Runtime.executionContextCreated') ctxIds.push(m.params.context.id);
    if (m.method === 'Runtime.consoleAPICalled')
      logs.push('[' + m.params.type + '] ' + (m.params.args || []).map(a => a.value !== undefined ? a.value : (a.description || a.type)).join(' ').slice(0, 400));
    if (m.method === 'Runtime.exceptionThrown') {
      const d = m.params.exceptionDetails || {};
      logs.push('[EXC] ' + ((d.exception && (d.exception.description || d.exception.value)) || d.text || '') +
        ' @' + (d.url || '') + ':' + (d.lineNumber !== undefined ? d.lineNumber : '?'));
    }
    if (m.method === 'Log.entryAdded') logs.push('[log] ' + (m.params.entry.text || '').slice(0, 300));
  };
  const send = (method, params) => new Promise((res, rej) => {
    const mid = ++id; pend.set(mid, res);
    setTimeout(() => { if (pend.has(mid)) { pend.delete(mid); rej(new Error('timeout ' + method)); } }, 20000);
    ws.send(JSON.stringify({ id: mid, method, params: params || {} }));
  });
  return { ws, send, logs, ctxIds, ready: new Promise(r => ws.onopen = r) };
}

(async () => {
  const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const t = l.find(x => (x.url || '').includes('gamePage.html'));
  if (!t) { console.log('NO TARGET'); process.exit(1); }
  console.log('target:', t.url);
  const c = connect(t.webSocketDebuggerUrl);
  await c.ready;
  await c.send('Runtime.enable');
  await c.send('Log.enable');
  await c.send('Page.enable');
  await sleep(500);

  // 点编译
  const l2 = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const ep = l2.find(x => (x.url || '').includes('electron-project.html'));
  if (ep) {
    const c2 = connect(ep.webSocketDebuggerUrl); await c2.ready;
    const r = await c2.send('Runtime.evaluate', {
      expression: `(function(){var els=[].slice.call(document.querySelectorAll('.simulator-toolbar-item'));
        var hit=els.filter(function(e){return (e.textContent||'').indexOf('编译')>=0;})[0];
        if(!hit) return 'NOT FOUND'; hit.click(); return 'CLICKED '+(hit.textContent||'').trim();})()`,
      returnByValue: true
    });
    console.log('编译:', (r.result && r.result.result && r.result.result.value) || '?');
    c2.ws.close();
  } else console.log('编译: 无 electron-project 窗口');
  await sleep(8000);

  // 探环境
  const ev = async (expr, cid) => {
    const r = await c.send('Runtime.evaluate', { expression: expr, contextId: cid, returnByValue: true }).catch(() => null);
    if (!r || !r.result || !r.result.result) return '?';
    const v = r.result.result.value;
    return v === undefined ? r.result.result.description : v;
  };
  console.log('\n--- 各 context 的 typeof GAME / document.readyState ---');
  const ids = Array.from(new Set(c.ctxIds.concat(Array.from({ length: 60 }, (_, i) => i + 1))));
  for (const cid of ids) {
    const g = await ev('typeof GAME', cid);
    if (g === '?') continue;
    const rs = await ev('(typeof document!=="undefined"&&document)?document.readyState:"no-doc"', cid);
    const hasWin = await ev('typeof window', cid);
    const hasWx = await ev('typeof wx', cid);
    console.log('  ctx', cid, '| GAME=', g, '| readyState=', rs, '| window=', hasWin, '| wx=', hasWx);
  }
  console.log('\n--- 控制台/异常 ---');
  console.log(c.logs.length ? c.logs.join('\n') : '  (空)');
  process.exit(0);
})().catch(e => { console.log('FATAL', e && e.message || e); process.exit(9); });
