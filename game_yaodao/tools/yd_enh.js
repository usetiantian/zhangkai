// 强化面板验证：进战斗 → 背包 → 点装备格 → 强化 → 分解
const { spawn } = require('child_process');
const fs = require('fs');
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9459;
const OUT = 'C:/Users/87999/.claude/tmp/yd_enh';
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const proc = spawn(EDGE, ['--headless=new', '--disable-gpu', '--no-sandbox',
    '--remote-debugging-port=' + PORT, '--window-size=390,844',
    '--user-data-dir=' + OUT + '/profile_' + Date.now(), 'about:blank'], { stdio: 'ignore' });
  let list = null;
  for (let i = 0; i < 30; i++) {
    await sleep(500);
    try { list = await (await fetch('http://127.0.0.1:' + PORT + '/json/list')).json(); if (list.length) break; } catch (e) { }
  }
  const page = list.find(t => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pend = new Map(); const logs = [];
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
    if (m.method === 'Runtime.consoleAPICalled')
      logs.push('[' + m.params.type + '] ' + (m.params.args || []).map(a => a.value !== undefined ? a.value : (a.description || a.type)).join(' ').slice(0, 250));
    if (m.method === 'Runtime.exceptionThrown')
      logs.push('[EXC] ' + JSON.stringify(m.params.exceptionDetails).slice(0, 300));
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
    await sleep(90);
    await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await sleep(450);
  };
  const shot = async n => {
    const r = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(OUT + '/' + n + '.png', Buffer.from(r.result.data, 'base64'));
    console.log('   截图', n);
  };

  await send('Runtime.enable'); await send('Page.enable');
  await send('Network.enable'); await send('Network.setCacheDisabled', { cacheDisabled: true });
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
  await send('Page.navigate', { url: 'file:///C:/Users/87999/claude-workspace/game_yaodao/index.html' });
  await sleep(2500);

  console.log('① 进战斗');
  const p0 = JSON.parse(await ev('(function(){var S=GAME.S();return JSON.stringify({m:S.btnSexm});})()'));
  await tap(p0.m.x, p0.m.y);
  await sleep(1500);
  console.log('   装备武器 =', await ev('JSON.stringify(GAME.S().save.equip.weapon)'));
  console.log('   金币 =', await ev('GAME.S().save.coins'), '| 精粹 =', await ev('GAME.S().save.essence'));

  console.log('② 打开背包');
  const bb = JSON.parse(await ev('(function(){var b=GAME.S().btnBag;return b?JSON.stringify(b):"none";})()'));
  await tap(bb.x, bb.y);
  await sleep(700);
  console.log('   state =', await ev('GAME.S().state'));
  await shot('01_背包');

  console.log('③ 点已装备的武器格 → 强化面板');
  const sb = JSON.parse(await ev('(function(){var S=GAME.S();var k=Object.keys(S).filter(function(x){return x.indexOf("slotBtn")===0;})[0];return k?JSON.stringify(S[k]):"none";})()'));
  console.log('   装备格 =', sb);
  await tap(sb.x, sb.y);
  await sleep(700);
  console.log('   state =', await ev('GAME.S().state'));
  await shot('02_强化面板');

  console.log('④ 给点资源再强化');
  await ev('GAME.S().save.coins=99999;GAME.S().save.essence=999;');
  await sleep(400);
  const eb = JSON.parse(await ev('(function(){var b=GAME.S().btnEnh;return b?JSON.stringify(b):"none";})()'));
  await tap(eb.x, eb.y);
  await sleep(700);
  console.log('   强化等级 =', await ev('GAME.S().save.equip.weapon.lv'), '| 战力 =', await ev('GAME.S().save.best'));
  await shot('03_强化后');

  console.log('⑤ 再点两次');
  await tap(eb.x, eb.y); await tap(eb.x, eb.y);
  console.log('   强化等级 =', await ev('GAME.S().save.equip.weapon.lv'), '| 武器攻击 =', await ev('GAME.S().save.equip.weapon.atk'));
  await shot('04_强化三级');

  console.log('⑥ 分解');
  const sb2 = JSON.parse(await ev('(function(){var b=GAME.S().btnSell;return b?JSON.stringify(b):"none";})()'));
  await tap(sb2.x, sb2.y);
  await sleep(700);
  console.log('   state =', await ev('GAME.S().state'), '| 精粹 =', await ev('GAME.S().save.essence'), '| 武器 =', await ev('JSON.stringify(GAME.S().save.equip.weapon)'));
  await shot('05_分解后');

  console.log('\n--- 控制台 ---');
  console.log(logs.length ? logs.slice(-10).join('\n') : '(无错误)');
  proc.kill(); process.exit(0);
})().catch(e => { console.log('FATAL', e); process.exit(9); });
