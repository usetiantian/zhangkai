/* 微信开发者工具模拟器：地面特征逐图验证。
   流程：编译重载 → （选性别如需）→ 解锁全图 → 逐图进战斗截图。
   用法：node tools/yd_ground_wx.js */
const fs = require('fs');
const PORT = 9333;
const OUT = 'C:/Users/87999/.claude/tmp/yd_ground_wx';
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let logs = [];

function connect(url) {
  const ws = new WebSocket(url);
  let id = 0; const pend = new Map(); const ctxIds = [];
  ws.onmessage = e => {
    let m; try { m = JSON.parse(e.data); } catch (x) { return; }
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); return; }
    if (m.method === 'Runtime.executionContextCreated') ctxIds.push(m.params.context.id);
    if (m.method === 'Runtime.consoleAPICalled' && (m.params.type === 'error' || m.params.type === 'warning'))
      logs.push('[con.' + m.params.type + '] ' + (m.params.args || []).map(a => a.value !== undefined ? a.value : (a.description || a.type)).join(' ').slice(0, 400));
    if (m.method === 'Runtime.exceptionThrown') {
      const d = m.params.exceptionDetails || {};
      logs.push('[EXC] ' + ((d.exception && (d.exception.description || d.exception.value)) || d.text || '').slice(0, 400));
    }
  };
  const send = (method, params) => new Promise((res, rej) => {
    const mid = ++id; pend.set(mid, res);
    setTimeout(() => { if (pend.has(mid)) { pend.delete(mid); rej(new Error('timeout ' + method)); } }, 20000);
    ws.send(JSON.stringify({ id: mid, method, params: params || {} }));
  });
  return { ws, send, ctxIds, ready: new Promise(r => ws.onopen = r) };
}

async function findGame() {
  const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const targets = l.filter(x => (x.url || '').includes('gamePage.html'));
  for (const t of targets) {
    const c = connect(t.webSocketDebuggerUrl);
    await c.ready;
    await c.send('Runtime.enable');
    await c.send('Page.enable');
    await sleep(900);
    const ids = Array.from(new Set(c.ctxIds.concat(Array.from({ length: 400 }, (_, i) => i + 1))));
    for (const cid of ids) {
      const p = await c.send('Runtime.evaluate', {
        expression: 'typeof GAME', contextId: cid, returnByValue: true
      }).catch(() => null);
      if (p && p.result && p.result.result && p.result.result.value === 'object') {
        return { c, cid };
      }
    }
    c.ws.close();
  }
  throw new Error('NO GAME CTX');
}

async function compile() {
  const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const t = l.find(x => (x.url || '').includes('electron-project.html'));
  if (!t) return 'NO WINDOW';
  const c = connect(t.webSocketDebuggerUrl); await c.ready;
  const r = await c.send('Runtime.evaluate', {
    expression: `(function(){
        var els=[].slice.call(document.querySelectorAll('.simulator-toolbar-item'));
        var hit=els.filter(function(e){return (e.textContent||'').indexOf('编译')>=0;})[0];
        if(!hit) return 'NOT FOUND';
        hit.click(); return 'CLICKED';
      })()`, returnByValue: true
  });
  c.ws.close();
  return (r.result && r.result.result && r.result.result.value) || '?';
}

(async () => {
  console.log('① 编译重载（载入新包）:', await compile());
  await sleep(7000);
  const { c, cid } = await findGame();
  console.log('② 找到妖刀录 ctx', cid);
  const ev = async expr => {
    const r = await c.send('Runtime.evaluate', { expression: expr, contextId: cid, returnByValue: true, awaitPromise: true });
    if (r.result && r.result.exceptionDetails) return 'EXC ' + JSON.stringify(r.result.exceptionDetails).slice(0, 200);
    const rr = r.result && r.result.result;
    return rr ? (rr.value !== undefined ? rr.value : rr.description) : '(undef)';
  };
  let CAL = { s: 1, ox: 0, oy: 0 };
  const rawTap = async (x, y) => {
    await c.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
    await sleep(80);
    await c.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await sleep(300);
  };
  await rawTap(60, 60);
  const p1 = JSON.parse(await ev('JSON.stringify(GAME.S().lastTap)'));
  await rawTap(180, 180);
  const p2 = JSON.parse(await ev('JSON.stringify(GAME.S().lastTap)'));
  const sx = (p2.x - p1.x) / 120 || 1, sy = (p2.y - p1.y) / 120 || 1;
  CAL = { s: (sx + sy) / 2, ox: p1.x - 60 * sx, oy: p1.y - 60 * sy };
  console.log('   校准: scale=' + CAL.s.toFixed(3) + ' offset=(' + CAL.ox.toFixed(1) + ',' + CAL.oy.toFixed(1) + ')');
  const tap = async (x, y) => rawTap((x - CAL.ox) / CAL.s, (y - CAL.oy) / CAL.s);
  const shot = async n => {
    /* 优先从游戏内部取画布（微信截屏抓不到模拟器合成层时这招才可靠） */
    const url = await ev('(G.cv&&G.cv.toDataURL)?G.cv.toDataURL("image/png"):""');
    if (url && url.indexOf('data:image/png') === 0) {
      fs.writeFileSync(OUT + '/' + n + '.png', Buffer.from(url.split(',')[1], 'base64'));
    } else {
      const r = await c.send('Page.captureScreenshot', { format: 'png' });
      fs.writeFileSync(OUT + '/' + n + '.png', Buffer.from(r.result.data, 'base64'));
    }
    console.log('   截图', n);
  };

  let st = await ev('GAME.S().state');
  if (st === 'pick') {
    const pm = JSON.parse(await ev('JSON.stringify(GAME.S().btnSexm)'));
    await tap(pm.x, pm.y); await sleep(1200);
    st = await ev('GAME.S().state');
  }
  if (st !== 'battle') { await ev('(function(){GAME.S().state="battle";return "ok";})()'); st = 'battle'; }
  console.log('③ 开局 state =', st);
  await ev('(function(){var S=GAME.S();S.save.maxWave=6;G.persist();return "ok";})()');
  console.log('④ 解锁全图，逐图进战斗');
  for (var idx = 1; idx <= 6; idx++) {
    await tap(70, 28); await sleep(700);
    let st2 = await ev('GAME.S().state');
    if (st2 !== 'maps') {
      console.log('   ⚠ tap 后 state=' + st2 + '，lastTap=' + await ev('JSON.stringify(GAME.S().lastTap)') + ' → 直接切 maps');
      await ev('(function(){GAME.S().state="maps";return 1;})()'); await sleep(400);
    }
    if (idx === 1) { await shot('wx_00_选关面板'); console.log('   选关面板 state =', await ev('GAME.S().state')); }
    const b = JSON.parse(await ev('(function(){var S=GAME.S();return JSON.stringify(S["mapBtn'+idx+'"]);})()'));
    if (!b || b.locked) { console.log('  map' + (idx + 1) + ' LOCKED/SKIP', JSON.stringify(b)); continue; }
    await tap(b.x, b.y); await sleep(1600);
    console.log('  map' + (idx + 1), await ev('GAME.S().map.name'), '| fx =', await ev('GAME.S().map.fx||"(默认)"'),
      '| state =', await ev('GAME.S().state'));
    await shot('wx_map' + (idx + 1));
  }
  console.log('⑤ 异常:', logs.length ? logs.join(' || ') : '(无)');
  c.ws.close(); process.exit(0);
})().catch(e => { console.log('FATAL', e.message); process.exit(9); });
