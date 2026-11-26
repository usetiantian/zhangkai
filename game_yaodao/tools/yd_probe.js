/* 抓微信模拟器里游戏的 console（主循环异常被 try/catch 吞进 console.error） */
const PORT = 9333;
const sleep = ms => new Promise(r => setTimeout(r, ms));
function connect(url) {
  const ws = new WebSocket(url);
  let id = 0; const pend = new Map(); const ctxIds = []; const logs = [];
  ws.onmessage = e => {
    let m; try { m = JSON.parse(e.data); } catch (x) { return; }
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); return; }
    if (m.method === 'Runtime.executionContextCreated') ctxIds.push(m.params.context.id);
    if (m.method === 'Runtime.consoleAPICalled')
      logs.push('[' + m.params.type + '] ' + (m.params.args || []).map(a => a.value !== undefined ? a.value : (a.description || a.type)).join(' ').slice(0, 500));
    if (m.method === 'Runtime.exceptionThrown')
      logs.push('[EXC] ' + JSON.stringify(m.params.exceptionDetails).slice(0, 500));
  };
  const send = (method, params) => new Promise((res, rej) => {
    const mid = ++id; pend.set(mid, res);
    setTimeout(() => { if (pend.has(mid)) { pend.delete(mid); rej(new Error('timeout')); } }, 20000);
    ws.send(JSON.stringify({ id: mid, method, params: params || {} }));
  });
  return { ws, send, ctxIds, logs, ready: new Promise(r => ws.onopen = r) };
}
(async () => {
  const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const t = l.find(x => (x.url || '').includes('gamePage.html'));
  const c = connect(t.webSocketDebuggerUrl); await c.ready;
  await c.send('Runtime.enable');
  await sleep(900);
  const ids = Array.from(new Set(c.ctxIds.concat(Array.from({ length: 400 }, (_, i) => i + 1))));
  let cid = null;
  for (const id of ids) {
    const p = await c.send('Runtime.evaluate', { expression: 'typeof GAME', contextId: id, returnByValue: true }).catch(() => null);
    if (p && p.result && p.result.result && p.result.result.value === 'object') { cid = id; break; }
  }
  console.log('ctx', cid);
  await sleep(3000);   /* 收 3 秒 console */
  const uniq = [];
  for (const x of c.logs) if (!uniq.some(u => u.slice(0, 120) === x.slice(0, 120))) uniq.push(x);
  console.log('console 去重后', uniq.length, '条:');
  uniq.slice(0, 15).forEach(x => console.log('  ', x));
  c.ws.close(); process.exit(0);
})().catch(e => { console.log('FATAL', e.message); process.exit(9); });
