// 微信运行时音效验证：内嵌音频上下文能不能用、包里文件在不在
const sleep = ms => new Promise(r => setTimeout(r, ms));
const PORT = 9333;

function connect(url) {
  const ws = new WebSocket(url);
  let id = 0; const pend = new Map(); const logs = []; const errs = [];
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); return; }
    if (m.method === 'Runtime.consoleAPICalled')
      logs.push('[' + m.params.type + '] ' + (m.params.args || []).map(a => a.value !== undefined ? a.value : (a.description || a.type)).join(' ').slice(0, 250));
    if (m.method === 'Runtime.exceptionThrown') {
      const d = m.params.exceptionDetails || {};
      errs.push((d.exception && (d.exception.description || d.exception.value)) || d.text || '');
    }
  };
  const send = (m, p) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method: m, params: p || {} })); });
  return { ws, send, logs, errs, ready: new Promise(r => ws.onopen = r) };
}

(async () => {
  const l = await (await fetch('http://127.0.0.1:' + PORT + '/json/list')).json();
  const t = l.find(x => (x.url || '').includes('gamePage.html') && !(x.url || '').includes(':63362'));
  if (!t) { console.log('没找到妖刀录 target'); process.exit(1); }
  const c = connect(t.webSocketDebuggerUrl);
  await c.ready;
  await c.send('Runtime.enable');
  await sleep(1200);

  let cid = null;
  for (let i = 1; i <= 400; i++) {
    const r = await c.send('Runtime.evaluate', { expression: 'typeof GAME', contextId: i, returnByValue: true }).catch(() => null);
    if (r && r.result && r.result.result && r.result.result.value === 'object') { cid = i; break; }
  }
  if (!cid) { console.log('没找到游戏上下文'); process.exit(2); }
  const ev = async expr => {
    const r = await c.send('Runtime.evaluate', { expression: expr, contextId: cid, returnByValue: true, awaitPromise: true });
    if (r.result && r.result.exceptionDetails) return 'EXC ' + JSON.stringify(r.result.exceptionDetails).slice(0, 250);
    const rr = r.result && r.result.result;
    return rr ? (rr.value !== undefined ? rr.value : rr.description) : '(undef)';
  };

  console.log('① 微信音频 API:');
  console.log('   wx.createInnerAudioContext =', await ev('typeof wx.createInnerAudioContext'));
  console.log('   音效池已建 =', await ev('(typeof G!=="undefined" && G.sfx) ? "是" : "否"'));
  console.log('   静音状态 =', await ev('(typeof G!=="undefined" && G.sfx) ? G.sfx.mute : "-"'));

  console.log('② 逐个播放（看会不会报错）');
  const names = ['click', 'hit', 'crit', 'drop', 'rare', 'pull', 'upgrade', 'boss', 'gem', 'pet'];
  for (const n of names) {
    const r = await ev('(function(){try{G.sfx.play("' + n + '");return "ok";}catch(e){return "ERR "+e.message;}})()');
    console.log('   ' + n.padEnd(8) + ' →', r);
    await sleep(120);
  }

  console.log('③ 运行时异常:');
  console.log(c.errs.length ? c.errs.map(x => '   ' + x).join('\n') : '   （无）');
  console.log('④ 控制台:');
  console.log(c.logs.length ? c.logs.slice(-5).map(x => '   ' + x).join('\n') : '   （无）');
  c.ws.close();
  process.exit(0);
})().catch(e => { console.log('FATAL', e.message); process.exit(9); });
