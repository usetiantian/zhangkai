// 《妖刀录》· 微信开发者工具模拟器 端到端验证
// 用法: node tools/_yd_wx.js
// 流程: 清存档 → 点「编译」重开 → 选性别 → 抽卡 → 背包 → 改形象
const fs = require('fs');
const PORT = 9333;
const OUT = 'C:/Users/87999/.claude/tmp/yd_wx';
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });

const sleep = ms => new Promise(r => setTimeout(r, ms));
let logs = [];

function connect(url) {
  const ws = new WebSocket(url);
  let id = 0; const pend = new Map();
  const ctxIds = [];
  ws.onmessage = e => {
    let m; try { m = JSON.parse(e.data); } catch (x) { return; }
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); return; }
    if (m.method === 'Runtime.executionContextCreated') ctxIds.push(m.params.context.id);
    if (m.method === 'Runtime.consoleAPICalled')
      logs.push('[' + m.params.type + '] ' + (m.params.args || []).map(a => a.value !== undefined ? a.value : (a.description || a.type)).join(' ').slice(0, 260));
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
  /* ⚠️ 多个工程同时开着时，所有 gamePage 长得一样 ——
     必须按「有没有 GAME 全局对象」来认工程，别抓到别的游戏。 */
  for (const t of targets) {
    const c = connect(t.webSocketDebuggerUrl);
    await c.ready;
    await c.send('Runtime.enable');
    await c.send('Page.enable');
    await sleep(900);
    /* 微信开发者工具的 contextId 是 130+ 的，不能只扫 1..40 */
    const ids = Array.from(new Set(c.ctxIds.concat(
      Array.from({ length: 400 }, (_, i) => i + 1)
    )));
    for (const cid of ids) {
      const p = await c.send('Runtime.evaluate', {
        expression: 'typeof GAME', contextId: cid, returnByValue: true
      }).catch(() => null);
      if (p && p.result && p.result.result && p.result.result.value === 'object') {
        console.log('   妖刀录 target:', t.url.match(/:(\d+)\//)[1], 'ctx', cid);
        return { c, cid };
      }
    }
    c.ws.close();
  }
  throw new Error('NO GAME CTX');
}

async function main() {
  // ① 清存档
  {
    const { c, cid } = await findGame();
    const r = await c.send('Runtime.evaluate', {
      expression: 'wx.clearStorageSync(); "cleared"', contextId: cid, returnByValue: true
    });
    console.log('① 清存档:', (r.result && r.result.result && r.result.result.value) || '?');
    c.ws.close();
  }

  // ② 点「编译」重开游戏（编译按钮有时点不动，重试到游戏真的重启为止）
  const compile = async () => {
    const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
    const t = l.find(x => (x.url || '').includes('electron-project.html'));
    if (!t) return 'NO WINDOW';
    const c = connect(t.webSocketDebuggerUrl); await c.ready;
    const r = await c.send('Runtime.evaluate', {
      expression: `(function(){
          var els=[].slice.call(document.querySelectorAll('.simulator-toolbar-item'));
          var hit=els.filter(function(e){return (e.textContent||'').indexOf('编译')>=0;})[0];
          if(!hit) return 'NOT FOUND';
          hit.click(); return 'CLICKED '+(hit.textContent||'').trim();
        })()`, returnByValue: true
    });
    c.ws.close();
    return (r.result && r.result.result && r.result.result.value) || '?';
  };

  {
    let ok = false;
    for (let i = 1; i <= 4 && !ok; i++) {
      console.log('② 编译 第' + i + '次:', await compile());
      await sleep(6000);
      const { c: c2, cid: id2 } = await findGame();
      const st = await c2.send('Runtime.evaluate', {
        expression: 'GAME.S().state', contextId: id2, returnByValue: true
      }).then(r => r.result && r.result.result && r.result.result.value).catch(() => '?');
      console.log('   重开后 state =', st);
      c2.ws.close();
      if (st === 'pick') ok = true;
    }
    console.log('   干净重开:', ok ? '✓' : '✗（继续用当前状态）');
  }

  // ③ 验证
  const { c, cid } = await findGame();
  const ev = async expr => {
    const r = await c.send('Runtime.evaluate', { expression: expr, contextId: cid, returnByValue: true, awaitPromise: true });
    if (r.result && r.result.exceptionDetails) return 'EXC ' + JSON.stringify(r.result.exceptionDetails).slice(0, 200);
    const rr = r.result && r.result.result;
    return rr ? (rr.value !== undefined ? rr.value : rr.description) : '(undef)';
  };
  const tap = async (x, y) => {
    await c.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
    await sleep(90);
    await c.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await sleep(400);
  };
  const shot = async n => {
    const r = await c.send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(OUT + '/' + n + '.png', Buffer.from(r.result.data, 'base64'));
    console.log('   截图', n);
  };

  console.log('③ 开局 state =', await ev('GAME.S().state'), '| sex =', JSON.stringify(await ev('GAME.S().save.sex')));
  await shot('wx01_选性别');

  console.log('④ 点女侠');
  const p = JSON.parse(await ev('(function(){var S=GAME.S();return JSON.stringify({m:S.btnSexm,f:S.btnSexf});})()'));
  await tap(p.f.x, p.f.y);
  await sleep(1400);
  console.log('   state =', await ev('GAME.S().state'), '| sex =', await ev('GAME.S().save.sex'), '| skin =', await ev('GAME.S().save.skin'));
  await shot('wx02_战斗_女侠');

  console.log('⑤ 点抽卡');
  const q = JSON.parse(await ev('(function(){var b=GAME.S().btnPull;return b?JSON.stringify(b):"none";})()'));
  await tap(q.x, q.y);
  await sleep(1200);
  console.log('   state =', await ev('GAME.S().state'), '| 抽到 =', await ev('GAME.S().pullRes.length'), '| 背包 =', await ev('GAME.S().save.bag.length'));
  await shot('wx03_抽卡');

  console.log('⑥ 返回 → 背包');
  const back = await ev('(function(){var b=GAME.S().btnBack;return b?JSON.stringify(b):"none";})()');
  console.log('   ✕ 按钮 =', back);
  if (back !== 'none') { const bb = JSON.parse(back); await tap(bb.x, bb.y); }
  await sleep(800);
  let st = await ev('GAME.S().state');
  console.log('   ✕ 后 state =', st);
  if (st === 'battle') {                      /* 抽卡的 ✕ 回的是 bag；战斗里才需要点背包 */
    const r2 = JSON.parse(await ev('(function(){var b=GAME.S().btnBag;return b?JSON.stringify(b):"none";})()'));
    if (r2 !== 'none') await tap(r2.x, r2.y);
    await sleep(900);
    st = await ev('GAME.S().state');
  }
  console.log('   state =', st, '| 背包件数 =', await ev('GAME.S().save.bag.length'));
  await shot('wx04_背包');

  console.log('⑦ 改形象 → 改回男侠');
  const bl = await ev('(function(){var b=GAME.S().btnLook;return b?JSON.stringify(b):"none";})()');
  console.log('   改形象按钮 =', bl);
  if (bl !== 'none') {
    const r3 = JSON.parse(bl);
    await tap(r3.x, r3.y);
    await sleep(900);
    console.log('   state =', await ev('GAME.S().state'));
    await shot('wx05_改形象');
    const bm = JSON.parse(await ev('(function(){var S=GAME.S();return JSON.stringify({m:S.btnSexm});})()'));
    await tap(bm.m.x, bm.m.y);
    await sleep(1200);
    console.log('   改回男侠 → state =', await ev('GAME.S().state'), '| sex =', await ev('GAME.S().save.sex'), '| 背包保留 =', await ev('GAME.S().save.bag.length'));
    await shot('wx06_改回男侠');
  }

  console.log('\n--- 控制台 ---');
  console.log(logs.length ? logs.slice(-12).map(s => '  ' + s).join('\n') : '  (无报错)');
  c.ws.close();
  process.exit(0);
}
main().catch(e => { console.log('FATAL', e && e.message || e); process.exit(9); });
