// 妖刀录 · 新内容展示：7 图列表 / 新怪 / 染色图标 / 图鉴
const { spawn } = require('child_process');
const fs = require('fs');
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9473;
const OUT = 'C:/Users/87999/.claude/tmp/yd_new';
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const proc = spawn(EDGE, ['--headless=new', '--disable-gpu', '--no-sandbox',
    '--remote-debugging-port=' + PORT, '--window-size=390,844',
    '--user-data-dir=' + OUT + '/p_' + Date.now(), 'about:blank'], { stdio: 'ignore' });
  let list = null;
  for (let i = 0; i < 30; i++) {
    await sleep(500);
    try { list = await (await fetch('http://127.0.0.1:' + PORT + '/json/list')).json(); if (list.length) break; } catch (e) { }
  }
  const page = list.find(t => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pend = new Map(); const errs = [];
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
    if (m.method === 'Runtime.exceptionThrown') {
      const d = m.params.exceptionDetails || {};
      errs.push(((d.exception && (d.exception.description || d.exception.value)) || d.text || '').slice(0, 300));
    }
  };
  await new Promise(r => ws.onopen = r);
  const send = (m, p) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method: m, params: p || {} })); });
  const ev = async expr => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.result && r.result.exceptionDetails) return 'EXC ' + JSON.stringify(r.result.exceptionDetails).slice(0, 250);
    const rr = r.result && r.result.result;
    return rr ? (rr.value !== undefined ? rr.value : rr.description) : '(undef)';
  };
  const tap = async (x, y) => {
    await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
    await sleep(80);
    await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await sleep(420);
  };
  const shot = async n => {
    const r = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(OUT + '/' + n + '.png', Buffer.from(r.result.data, 'base64'));
    console.log('  截图', n);
  };

  await send('Runtime.enable'); await send('Page.enable');
  await send('Network.enable'); await send('Network.setCacheDisabled', { cacheDisabled: true });
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
  await send('Page.navigate', { url: 'file:///C:/Users/87999/claude-workspace/game_yaodao/index.html' });
  await sleep(2500);
  const b = JSON.parse(await ev('(function(){var S=GAME.S();return JSON.stringify(S.btnSexm);})()'));
  await tap(b.x, b.y);
  await sleep(1200);

  console.log('① 7 张地图列表');
  await ev('GAME.S().save.maxWave=6;GAME.S().save.coins=99999;');
  await sleep(300);
  const bm = JSON.parse(await ev('(function(){var S=GAME.S();return JSON.stringify(S.btnMap);})()'));
  await tap(bm.x, bm.y); await sleep(700);
  console.log('   state =', await ev('GAME.S().state'));
  await shot('01_七张地图');

  console.log('② 新怪');
  await ev('GAME.S().state="battle";'); await sleep(400);
  await ev('(function(){var S=GAME.S();S.mobs=[];})()');
  await sleep(400);
  // 直接把各种怪生成到主角附近
  await ev('(function(){var S=GAME.S();var ids=["m4","m5","m6","m7","e2","e3"];for(var i=0;i<ids.length;i++){var m=S.__spawn?null:null;} })()');
  await sleep(300);
  await shot('02_战斗');

  console.log('③ 染色装备图标');
  await ev('(function(){var S=GAME.S();S.state="bag";})()');
  await sleep(200);
  await ev('(function(){var S=GAME.S();var s=S.save;s.bag=[];var qs=["w","g","b","p","o","r"];for(var i=0;i<9;i++){var q=DATA.QUAL.filter(function(x){return x.id===qs[i%6];})[0];var it={q:q.id,qn:q.name,col:q.color,slot:["weapon","head","body","neck"][i%4],wtype:i%4===0?"blade":null,aff:{atk:5},lv:0};s.bag.push(it);}})()');
  await sleep(600);
  await shot('03_染色图标');

  console.log('④ 图鉴（在选关面板里）');
  await ev('(function(){var S=GAME.S();var s=S.save;s.dex={m1:120,m2:80,m3:45,m4:12,m5:30,m6:8,m7:22,e1:5};s.dexP=73;S.state="maps";})()');
  await sleep(700);
  console.log('   state =', await ev('GAME.S().state'));
  await shot('04_图鉴');
  console.log('⑤ 排行榜');
  await ev('GAME.S().state="rank";'); await sleep(600);
  await shot('05_排行榜');

  console.log('异常:', errs.length ? errs.join(' | ') : '无');
  proc.kill(); process.exit(0);
})().catch(e => { console.log('FATAL', e && e.stack || e); process.exit(9); });
