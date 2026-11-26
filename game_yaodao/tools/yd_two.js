// 双项目体检：确认果子乐园存档还在 + 妖刀录能不能启动
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
      logs.push('[' + m.params.type + '] ' + (m.params.args || []).map(a => a.value !== undefined ? a.value : (a.description || a.type)).join(' ').slice(0, 250));
    if (m.method === 'Runtime.exceptionThrown') {
      const d = m.params.exceptionDetails || {};
      logs.push('[EXC] ' + ((d.exception && (d.exception.description || d.exception.value)) || d.text || '').slice(0, 350));
    }
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
  const games = l.filter(x => (x.url || '').includes('gamePage.html'));
  for (const t of games) {
    const c = connect(t.webSocketDebuggerUrl);
    await c.ready;
    await c.send('Runtime.enable');
    await sleep(1200);
    const ids = Array.from(new Set(c.ctxIds.concat(Array.from({ length: 60 }, (_, i) => i + 1))));
    let cid = null, kind = '';
    for (const x of ids) {
      const g = await c.send('Runtime.evaluate', { expression: 'typeof GAME', contextId: x, returnByValue: true }).catch(() => null);
      const v = g && g.result && g.result.result && g.result.result.value;
      if (v === 'object') { cid = x; kind = '妖刀录'; break; }
      const m = await c.send('Runtime.evaluate', { expression: 'typeof window.__mini', contextId: x, returnByValue: true }).catch(() => null);
      const mv = m && m.result && m.result.result && m.result.result.value;
      if (mv === 'object') { cid = x; kind = '果子乐园'; break; }
    }
    console.log('\n======', t.url.match(/:(\d+)\//)[1], '→', kind || '未识别', '======');
    if (!cid) { console.log('  (没找到游戏上下文)'); c.ws.close(); continue; }
    const ev = async expr => {
      const r = await c.send('Runtime.evaluate', { expression: expr, contextId: cid, returnByValue: true }).catch(() => null);
      if (!r || !r.result || !r.result.result) return '?';
      const v = r.result.result.value;
      return v === undefined ? r.result.result.description : v;
    };
    if (kind === '妖刀录') {
      console.log('  state =', await ev('GAME.S().state'), '| sex =', JSON.stringify(await ev('GAME.S().save.sex')));
      console.log('  画布 =', await ev('G.W+"x"+G.H'));
    } else {
      console.log('  存档键 =', await ev('(function(){try{var o=wx.getStorageSync("guozi_save_v1")||wx.getStorageSync("game_save");return Object.keys(o||{}).slice(0,12).join(",");}catch(e){return "ERR "+e.message;}})()'));
      console.log('  screen =', await ev('window.__mini && window.__mini.screen'));
      console.log('  全部storage键 =', await ev('(function(){try{var i=wx.getStorageInfoSync();return i.keys.join(",");}catch(e){return "ERR";}})()'));
    }
    console.log('  日志:', c.logs.slice(-4).join(' || ') || '(空)');
    c.ws.close();
  }
  process.exit(0);
})().catch(e => { console.log('FATAL', e && e.message || e); process.exit(9); });
