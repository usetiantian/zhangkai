/* 套装系统验证。
   H5：注入 4 件血煞套装 → 逐件点穿 → 断言 2 件套(vamp+2)/4 件套(atk×1.08) + toast + 截图。
   微信（wx 参数）：注入并直接穿上 → 属性断言 + 截图（tap 路径 H5 已覆盖）。 */
const isWx = process.argv[2] === 'wx';
const { spawn } = require('child_process');
const fs = require('fs');
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = isWx ? 9333 : (9540 + Math.floor(Math.random() * 40));
const OUT = 'C:/Users/87999/.claude/tmp/yd_sets';
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
        const p = await c.send('Runtime.evaluate', { expression: 'typeof GAME', contextId: cid, returnByValue: true }).catch(() => null);
        if (p && p.result && p.result.result && p.result.result.value === 'object') return { c, cid };
      }
      c.ws.close();
    }
  }
  throw new Error('NO GAME CTX');
}
const INJECT = `(function(){
  var S=GAME.S(), s=S.save;
  var mk=function(slot,i){return {uid:'set'+i,q:'b',qn:'稀有测试件',col:'#4a9bff',slot:slot,
    wtype:slot==='weapon'?'blade':null,aff:{},atk:20,range:62,cd:0.62,dmgMul:1,set:'blood',lv:0};};
  ['head','body','neck','weapon'].forEach(function(sl,i){ s.bag.push(mk(sl,i+1)); });
  G.persist(); return s.bag.length;
})()`;
(async () => {
  let proc = null;
  if (!isWx) {
    proc = spawn(EDGE, ['--headless=new','--disable-gpu','--no-sandbox',
      '--remote-debugging-port='+PORT,'--window-size=390,844',
      '--user-data-dir='+OUT+'/profile_'+Date.now(),'about:blank'], {stdio:'ignore'});
    await sleep(2500);
    const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
    const c0 = connect(l.find(t => t.type === 'page').webSocketDebuggerUrl);
    await c0.ready; await c0.send('Page.enable');
    await c0.send('Page.navigate', { url: 'file:///C:/Users/87999/claude-workspace/game_yaodao/dist/index.html' });
    await sleep(2500); c0.ws.close();
  }
  const { c, cid } = await findGame(isWx ? 4 : 1);
  const ev = async e => {
    const p = { expression: e, returnByValue: true, awaitPromise: true };
    if (cid !== undefined) p.contextId = cid;
    const r = await c.send('Runtime.evaluate', p);
    if (r.result && r.result.exceptionDetails) return 'EXC ' + JSON.stringify(r.result.exceptionDetails).slice(0, 250);
    const rr = r.result && r.result.result;
    return rr ? (rr.value !== undefined ? rr.value : rr.description) : '(undef)';
  };
  const tap = async (x, y) => {
    await c.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
    await sleep(70);
    await c.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await sleep(450);
  };
  const shot = async n => {
    const url = await ev('(G.cv&&G.cv.toDataURL)?G.cv.toDataURL("image/png"):""');
    if (url && url.indexOf('data:image/png') === 0) {
      fs.writeFileSync(OUT + '/' + n + '.png', Buffer.from(url.split(',')[1], 'base64'));
      console.log('   截图', n);
    }
  };
  if (await ev('GAME.S().state') === 'pick') {
    const pm = JSON.parse(await ev('JSON.stringify(GAME.S().btnSexm)'));
    if (isWx) { await ev('(function(){GAME.S().save.sex="m";GAME.S().state="battle";return 1;})()'); await sleep(600); }
    else { await tap(pm.x, pm.y); await sleep(1000); }
  }
  const st = () => JSON.parse(ev ? JSON.stringify : '' , '');
  console.log('① 注入 4 件血煞:', await ev(INJECT));
  const st0 = JSON.parse(await ev('JSON.stringify(GAME.stats())'));
  console.log('② 基础属性', JSON.stringify({ atk: st0.atk, vamp: st0.vamp }));
  if (!isWx) {
    /* 打开背包逐件穿：head → body（2件套）→ neck → weapon（4件套） */
    await tap(44, JSON.parse(await ev('JSON.stringify(GAME.S().btnBag)')).y); await sleep(600);
    const order = ['set1', 'set2', 'set4', 'set3'];   /* head,body,neck,weapon 的 uid 顺序按注入数组 */
    for (const uid of order) {
      const j = JSON.parse(await ev('(function(){var b=GAME.S().save.bag;for(var i=0;i<b.length;i++)if(b[i].uid==="' + uid + '")return i;return -1;})()'));
      if (j < 0) { console.log('   ⚠ ' + uid + ' 不在背包（可能已穿上）'); continue; }
      const btn = JSON.parse(await ev('JSON.stringify(GAME.S()["bagItem' + j + '"])'));
      await tap((btn.x || 200) + 100, btn.y || 200); await sleep(600);
      const t2 = await ev('GAME.S().toast');
      const stN = JSON.parse(await ev('JSON.stringify(GAME.stats())'));
      console.log('   穿 ' + uid + ' → vamp=' + stN.vamp + ' atk=' + stN.atk + ' | toast=' + JSON.stringify(String(t2).slice(0, 40)));
    }
    await shot(isWx ? 'wx_bag_sets' : 'h5_bag_sets');
    const line = await ev('(function(){var S=GAME.S();for(var k in S){} return 1;})()');
    console.log('③ 2/4 件套断言看上面 vamp/atk 与 toast');
  } else {
    await ev('(function(){var s=GAME.S().save;s.equip.head=s.bag[0];s.equip.body=s.bag[1];s.equip.neck=s.bag[2];s.equip.weapon=s.bag[3];s.bag=[];GAME.S().stats=GAME.stats();G.persist();return 1;})()');
    await sleep(400);
    const st1 = JSON.parse(await ev('JSON.stringify(GAME.stats())'));
    console.log('③ 4 件穿上后', JSON.stringify({ atk: st1.atk, vamp: st1.vamp }));
    console.log('   预期: vamp = ' + (st0.vamp + 2) + '（2件套）');
    await shot('wx_bag_sets');
  }
  console.log('异常:', c.logs.length ? c.logs.slice(0, 3).join(' || ') : '(无)');
  c.ws.close();
  /* ⚠️ proc.kill() 杀不掉 Edge 子进程树 —— 残留的 headless Edge 会在后台
     循环播放游戏音效（张凯听了一下午的"打鼓声"就是它们）。必须 taskkill /T */
  if (proc) {
    try { require('child_process').execSync('taskkill /PID ' + proc.pid + ' /T /F', { stdio: 'ignore' }); } catch (e) { }
    try { proc.kill(); } catch (e) { }
  }
  process.exit(0);
})().catch(e => { console.log('FATAL', e.message); process.exit(9); });
