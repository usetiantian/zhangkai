// 出「10 把武器佩戴效果」一览图：逐个换武器 → 截图 → 裁角色 → 拼成一张
const { spawn } = require('child_process');
const fs = require('fs');
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9457;
const URL = 'file:///C:/Users/87999/claude-workspace/game_yaodao/index.html';
const OUT = 'C:/Users/87999/.claude/tmp/yd_sheet';
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));

const SKINS = [
  ['ws_blade_1', '青锋'], ['ws_blade_2', '赤霄'], ['ws_sword_1', '流云'],
  ['ws_sword_2', '紫电'], ['ws_staff_1', '玄木'], ['ws_staff_2', '烈阳'],
  ['ws_fist_1', '金刚'], ['ws_fist_2', '血影'], ['ws_dagger_1', '月影'],
  ['ws_dagger_2', '星辰']
];

(async () => {
  const proc = spawn(EDGE, [
    '--headless=new', '--disable-gpu', '--no-sandbox',
    '--remote-debugging-port=' + PORT, '--window-size=390,844',
    '--user-data-dir=' + OUT + '/profile', 'about:blank'
  ], { stdio: 'ignore' });
  let list = null;
  for (let i = 0; i < 30; i++) {
    await sleep(500);
    try { list = await (await fetch('http://127.0.0.1:' + PORT + '/json/list')).json(); if (list.length) break; } catch (e) { }
  }
  const page = list.find(t => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pend = new Map();
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
  };
  await new Promise(r => ws.onopen = r);
  const send = (m, p) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method: m, params: p || {} })); });
  const ev = async expr => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    const rr = r.result && r.result.result;
    return rr ? rr.value : undefined;
  };

  await send('Runtime.enable'); await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
  await send('Page.navigate', { url: URL });
  await sleep(2500);

  // 走正常流程进战斗：点「男侠」→ newBattle() 会跑，主角才会存在
  const p0 = JSON.parse(await ev('(function(){var S=GAME.S();return JSON.stringify({m:S.btnSexm});})()'));
  await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: p0.m.x, y: p0.m.y }] });
  await sleep(80);
  await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await sleep(1500);
  console.log('  state =', await ev('GAME.S().state'), '| hero =', await ev('!!GAME.S().hero'));

  for (const [sid, name] of SKINS) {
    await ev('(function(){var S=GAME.S();S.save.wskin="' + sid + '";S.mobs=[];S.nums=[];S.eff=[];})()');
    await sleep(700);
    const r = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(OUT + '/' + sid + '.png', Buffer.from(r.result.data, 'base64'));
    console.log('  ✓', sid, name);
  }
  proc.kill();
  process.exit(0);
})().catch(e => { console.log('FATAL', e); process.exit(9); });
