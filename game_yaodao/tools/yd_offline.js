/* 离线收益验证：直写存储把 offAt 拨回两小时 → 重载 → 断言金币/精粹到账。
   跑法：node tools/yd_offline.js          （H5）
         node tools/yd_offline.js wx       （微信模拟器）
   ⚠️ 不能用 G.persist() 注入 —— persist 会把 offAt 重盖成 now（生产行为，故意的）。 */
const isWx = process.argv[2] === 'wx';
const { spawn, execSync } = require('child_process');
const fs = require('fs');
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = isWx ? 9333 : (9480 + Math.floor(Math.random() * 60));
const OUT = 'C:/Users/87999/.claude/tmp/yd_offline';
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
function connect(url) {
  const ws = new WebSocket(url);
  let id = 0; const pend = new Map(); const ctxIds = []; const logs = [];
  ws.onmessage = e => {
    let m; try { m = JSON.parse(e.data); } catch (x) { return; }
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); return; }
    if (m.method === 'Runtime.executionContextCreated') ctxIds.push(m.params.context.id);
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error')
      logs.push('[con.error] ' + (m.params.args || []).map(a => a.value !== undefined ? a.value : (a.description || a.type)).join(' ').slice(0, 300));
    if (m.method === 'Runtime.exceptionThrown') {
      const d = m.params.exceptionDetails || {};
      logs.push('[EXC] ' + ((d.exception && (d.exception.description || d.exception.value)) || d.text || '').slice(0, 300));
    }
  };
  const send = (method, params) => new Promise((res, rej) => {
    const mid = ++id; pend.set(mid, res);
    setTimeout(() => { if (pend.has(mid)) { pend.delete(mid); rej(new Error('timeout ' + method)); } }, 20000);
    ws.send(JSON.stringify({ id: mid, method, params: params || {} }));
  });
  return { ws, send, ctxIds, logs, ready: new Promise(r => ws.onopen = r) };
}
async function findGame(tries) {
  for (let t = 0; t < (tries || 1); t++) {
    if (t) await sleep(5000);
    const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
    const targets = l.filter(x => (x.url || '').includes(isWx ? 'gamePage.html' : 'index.html'));
    for (const tg of targets) {
      const c = connect(tg.webSocketDebuggerUrl);
      await c.ready;
      await c.send('Runtime.enable'); await c.send('Page.enable');
      await sleep(isWx ? 900 : 300);
      const ids = isWx
        ? Array.from(new Set(c.ctxIds.concat(Array.from({ length: 900 }, (_, i) => i + 1))))
        : [undefined];
      for (const cid of ids) {
        const p = await c.send('Runtime.evaluate', {
          expression: 'typeof GAME', contextId: cid, returnByValue: true
        }).catch(() => null);
        if (p && p.result && p.result.result && p.result.result.value === 'object') return { c, cid };
      }
      c.ws.close();
    }
  }
  throw new Error('NO GAME CTX');
}
async function compile() {
  const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const t = l.find(x => (x.url || '').includes('electron-project.html'));
  if (!t) return 'NO WINDOW';
  const c = connect(t.webSocketDebuggerUrl); await c.ready;
  const r = await c.send('Runtime.evaluate', {
    expression: `(function(){var els=[].slice.call(document.querySelectorAll('.simulator-toolbar-item'));
        var hit=els.filter(function(e){return (e.textContent||'').indexOf('编译')>=0;})[0];
        if(!hit) return 'NOT FOUND'; hit.click(); return 'CLICKED';})()`, returnByValue: true
  });
  c.ws.close();
  return (r.result && r.result.result && r.result.result.value) || '?';
}
const SAVE_KEY = 'yaodao_save_v1';
/* 注入同时补 sex：微信端没做坐标校准，选性别的 tap 未必点上；
   pick 态 grantOffline 会直接跳过，所以直接把存档修成已开局 */
const inject = isWx
  ? `wx.setStorageSync('${SAVE_KEY}', (function(){var s=GAME.S().save; s.sex=s.sex||'m'; s.offAt=Date.now()-7200000; return s;})())`
  : `localStorage.setItem('${SAVE_KEY}', JSON.stringify((function(){var s=GAME.S().save; s.sex=s.sex||'m'; s.offAt=Date.now()-7200000; return s;})()))`;
(async () => {
  let proc = null;
  if (!isWx) {
    proc = spawn(EDGE, ['--headless=new','--disable-gpu','--no-sandbox',
      '--remote-debugging-port='+PORT,'--window-size=390,844',
      '--user-data-dir='+OUT+'/profile_'+Date.now(),'about:blank'], {stdio:'ignore'});
    await sleep(2500);
  }
  let before = null;
  {
    if (isWx) { console.log('① 编译:', await compile()); await sleep(7000); }
    else {
      /* 新 Edge 停在 about:blank —— 先导航到游戏页 */
      const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const c0 = connect(l.find(t => t.type === 'page').webSocketDebuggerUrl);
      await c0.ready; await c0.send('Page.enable');
      await c0.send('Page.navigate', { url: 'file:///C:/Users/87999/claude-workspace/game_yaodao/dist/index.html' });
      await sleep(2500); c0.ws.close();
    }
    const { c, cid } = await findGame();
    const ev = async e => {
      const p = { expression: e, returnByValue: true };
      if (cid !== undefined) p.contextId = cid;
      const r = await c.send('Runtime.evaluate', p);
      if (r.result && r.result.exceptionDetails) return 'EXC ' + JSON.stringify(r.result.exceptionDetails).slice(0, 200);
      const rr = r.result && r.result.result;
      return rr ? (rr.value !== undefined ? rr.value : rr.description) : '(undef)';
    };
    if (await ev('GAME.S().state') === 'pick') {
      const pm = JSON.parse(await ev('JSON.stringify(GAME.S().btnSexm)'));
      await c.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: pm.x, y: pm.y }] });
      await sleep(80);
      await c.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
      await sleep(1000);
    }
    before = JSON.parse(await ev('(function(){var s=GAME.S().save;return JSON.stringify({c:s.coins,i:s.items,m:s.map});})()'));
    console.log('② 结算前', JSON.stringify(before), '| 注入:', await ev(inject));
    await ev('GAME.__offSentinel=1');
    if (isWx) {
      /* 重载 = 改一下 wx/game.js 触发文件监视器自动重编译（工具栏编译按钮不可靠，
         location.reload() 会把运行时打死 —— 两个坑都踩过了，见 CLAUDE.md #17） */
      c.ws.close();
      fs.appendFileSync('C:/Users/87999/claude-workspace/game_yaodao/wx/game.js', '\n');
      await sleep(8000);
      const g2 = await findGame(5);
      const ev2 = async e => {
        const r = await g2.c.send('Runtime.evaluate', { expression: e, contextId: g2.cid, returnByValue: true });
        const rr = r.result && r.result.result;
        return rr ? (rr.value !== undefined ? rr.value : rr.description) : '(undef)';
      };
      const reloaded = await ev2('typeof GAME.__offSentinel') === 'undefined';
      console.log('③ 整页重载:', reloaded ? '✓' : '✗（还在旧实例）');
      g2.c.ws.close();
      if (!reloaded) { console.log('❌ reload 都没生效'); process.exit(8); }
    }
    else {
      await c.send('Page.navigate', { url: 'file:///C:/Users/87999/claude-workspace/game_yaodao/dist/index.html' });
      await sleep(2500);
      c.ws.close();
    }
  }
  {
    const { c, cid } = await findGame();
    const ev = async e => {
      const p = { expression: e, returnByValue: true };
      if (cid !== undefined) p.contextId = cid;
      const r = await c.send('Runtime.evaluate', p);
      const rr = r.result && r.result.result;
      return rr ? (rr.value !== undefined ? rr.value : rr.description) : '(undef)';
    };
    const after = JSON.parse(await ev('(function(){var s=GAME.S().save;return JSON.stringify({c:s.coins,i:s.items,m:s.map});})()'));
    console.log('④ 结算后', JSON.stringify(after), '| toast =', JSON.stringify(String(await ev('GAME.S().toast')).slice(0, 70)));
    const dc = after.c - before.c, di = after.i - before.i;
    console.log('⑤ 增量: 金币 +' + dc + ' 精粹 +' + di, isWx ? '（微信端）' : '（H5 端）');
    console.log(dc > 0 && di >= 0 ? '✅ 离线收益生效' : '❌ 没生效');
    console.log('异常:', c.logs.length ? c.logs.slice(0, 3).join(' || ') : '(无)');
    c.ws.close();
  }
  if (proc) proc.kill();
  process.exit(0);
})().catch(e => { console.log('FATAL', e.message); process.exit(9); });
