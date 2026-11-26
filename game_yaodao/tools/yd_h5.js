// 《妖刀录》· 浏览器端（H5）视觉验证：选性别 → 战斗 → 换武器 → 截图
// 用法: node tools/yd_h5.js
const { spawn } = require('child_process');
const fs = require('fs');
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9455;
const URL = 'file:///C:/Users/87999/claude-workspace/game_yaodao/index.html';
const OUT = 'C:/Users/87999/.claude/tmp/yd_h5';
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const proc = spawn(EDGE, [
    '--headless=new', '--disable-gpu', '--no-sandbox',
    '--remote-debugging-port=' + PORT,
    '--window-size=390,844',
    '--user-data-dir=' + OUT + '/profile_' + Date.now(),
    'about:blank'
  ], { stdio: 'ignore' });

  let list = null;
  for (let i = 0; i < 30; i++) {
    await sleep(500);
    try {
      const r = await fetch('http://127.0.0.1:' + PORT + '/json/list');
      list = await r.json();
      if (list.length) break;
    } catch (e) { }
  }
  if (!list) { console.log('EDGE 没起来'); process.exit(1); }
  const page = list.find(t => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pend = new Map(); const logs = [];
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
    if (m.method === 'Runtime.consoleAPICalled')
      logs.push('[' + m.params.type + '] ' + (m.params.args || []).map(a => a.value !== undefined ? a.value : (a.description || a.type)).join(' ').slice(0, 300));
    if (m.method === 'Runtime.exceptionThrown')
      logs.push('[EXC] ' + JSON.stringify(m.params.exceptionDetails).slice(0, 400));
  };
  await new Promise(r => ws.onopen = r);
  const send = (method, params) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params: params || {} })); });
  const ev = async expr => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.result && r.result.exceptionDetails) return 'EXC ' + JSON.stringify(r.result.exceptionDetails).slice(0, 300);
    const rr = r.result && r.result.result;
    return rr ? (rr.value !== undefined ? rr.value : rr.description) : '(undef)';
  };
  const tap = async (x, y) => {
    await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
    await sleep(80);
    await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await sleep(400);
  };
  const shot = async name => {
    const r = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(OUT + '/' + name + '.png', Buffer.from(r.result.data, 'base64'));
    console.log('   截图', name);
  };

  await send('Runtime.enable');
  await send('Page.enable');
  await send('Network.enable');
  await send('Network.setCacheDisabled', {cacheDisabled: true});
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
  await send('Page.navigate', { url: URL });
  await sleep(2500);

  console.log('① 首屏 state:', await ev('typeof GAME!=="undefined"?GAME.S().state:"no GAME"'));
  await shot('01_选性别');

  // 点女侠（女侠 x = 390/2 - 130 + 140 + 55 = 210）
  console.log('② 点女侠');
  const p = JSON.parse(await ev('(function(){var S=GAME.S();return JSON.stringify({m:S.btnSexm,f:S.btnSexf});})()'));
  await tap(p.f.x, p.f.y);
  await sleep(1500);
  console.log('   state =', await ev('GAME.S().state'), '| sex =', await ev('GAME.S().save.sex'));
  console.log('   主角图加载? m=', await ev('!!(GAME.S().heroImg&&GAME.S().heroImg.m)'),
    '| 武器图加载? =', await ev('Object.keys(GAME.S().wskinImg||{}).length'));
  await shot('02_战斗_女侠');

  console.log('③ 等自动战斗打一刀');
  await sleep(2500);
  await shot('03_战斗中');

  console.log('④ 换武器：赤霄刀');
  await ev('GAME.S().save.wskin="ws_blade_2"');
  await sleep(1200);
  await shot('04_赤霄刀');

  console.log('⑤ 换武器：玄木杖');
  await ev('GAME.S().save.wskin="ws_staff_1"');
  await sleep(1200);
  await shot('05_玄木杖');

  console.log('⑥ 换武器：金刚拳套');
  await ev('GAME.S().save.wskin="ws_fist_1"');
  await sleep(1200);
  await shot('06_金刚拳套');

  console.log('\n--- 控制台 ---');
  console.log(logs.length ? logs.slice(-10).join('\n') : '(无错误)');
  proc.kill();
  process.exit(0);
})().catch(e => { console.log('FATAL', e); process.exit(9); });
