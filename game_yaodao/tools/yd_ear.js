/* 常驻监听器：挂在微信模拟器的游戏会话上，把 console/异常持续写进日志文件。
   张凯在玩游戏时一直跑着 —— 他说"不对"的瞬间，翻这个文件就有现场报错。
   跑法：node tools/yd_ear.js   （Ctrl+C 停；断线自动重连） */
const fs = require('fs');
const PORT = 9333;
const LOG = 'C:/Users/87999/.claude/tmp/yd_ear.log';
const sleep = ms => new Promise(r => setTimeout(r, ms));

function ts() { return new Date().toLocaleTimeString('zh-CN', { hour12: false }); }
function log(line) {
  fs.appendFileSync(LOG, '[' + ts() + '] ' + line + '\n');
}

function attach(target) {
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  let id = 0; const pend = new Map(); const ctxs = [];
  ws.onmessage = e => {
    let m; try { m = JSON.parse(e.data); } catch (x) { return; }
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); return; }
    if (m.method === 'Runtime.executionContextCreated') ctxs.push(m.params.context.id);
    if (m.method === 'Runtime.consoleAPICalled') {
      const t = m.params.type;
      if (t === 'error' || t === 'warning') {
        const args = (m.params.args || []).map(a => a.value !== undefined ? String(a.value) : (a.description || a.type)).join(' ');
        log('[con.' + t + '] ' + args.slice(0, 400));
      }
    }
    if (m.method === 'Runtime.exceptionThrown') {
      const d = m.params.exceptionDetails || {};
      log('[EXC] ' + ((d.exception && (d.exception.description || d.exception.value)) || d.text || '').toString().slice(0, 500));
    }
  };
  const send = (me, p) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method: me, params: p || {} })); });
  return {
    ws,
    ready: new Promise(r => ws.onopen = r),
    send,
    ctxs
  };
}

(async () => {
  fs.writeFileSync(LOG, '=== yd_ear 启动 ' + new Date().toISOString() + ' ===\n');
  log('常驻监听开始（console error/warning + 未捕获异常）');
  while (true) {
    try {
      const l = await (await fetch('http://127.0.0.1:' + PORT + '/json/list')).json();
      const t = l.find(x => (x.url || '').includes('gamePage.html'));
      if (!t) { await sleep(3000); continue; }
      const c = attach(t);
      await c.ready;
      await c.send('Runtime.enable');
      await c.send('Log.enable');
      log('-- 已挂上游戏会话 --');
      /* 断线重连：页面重编译时 WS 会关 */
      await new Promise(r => { c.ws.onclose = r; c.ws.onerror = r; });
      log('-- 会话断开（重编译/重启），3 秒后重连 --');
    } catch (e) {
      await sleep(3000);
    }
    await sleep(3000);
  }
})();
