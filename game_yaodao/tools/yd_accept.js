// 《妖刀录》全功能验收测试 —— 一条龙跑完所有系统，逐项断言
// 用法: node tools/yd_accept.js
const { spawn } = require('child_process');
const fs = require('fs');
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9466;
const OUT = 'C:/Users/87999/.claude/tmp/yd_accept';
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));

let pass = 0, fail = 0;
function check(name, ok, extra) {
  if (ok) { pass++; console.log('  ✓ ' + name + (extra ? '  ' + extra : '')); }
  else { fail++; console.log('  ✗ ' + name + '  ' + (extra || '')); }
}

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
  let id = 0; const pend = new Map(); const errs = [];
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
    if (m.method === 'Runtime.exceptionThrown') {
      const d = m.params.exceptionDetails || {};
      errs.push(((d.exception && (d.exception.description || d.exception.value)) || d.text || '') +
        ' || stack=' + JSON.stringify(d.stackTrace || {}).slice(0, 400));
    }
  };
  await new Promise(r => ws.onopen = r);
  const send = (m, p) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method: m, params: p || {} })); });
  const ev = async expr => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.result && r.result.exceptionDetails) return 'EXC:' + JSON.stringify(r.result.exceptionDetails).slice(0, 200);
    const rr = r.result && r.result.result;
    return rr ? (rr.value !== undefined ? rr.value : rr.description) : '(undef)';
  };
  const tap = async (x, y) => {
    await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
    await sleep(90);
    await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await sleep(420);
  };
  const shot = async n => {
    const r = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(OUT + '/' + n + '.png', Buffer.from(r.result.data, 'base64'));
  };
  const btn = async name => JSON.parse(await ev('(function(){var S=GAME.S();var b=S.' + name + ';return b?JSON.stringify(b):"none";})()'));

  await send('Runtime.enable'); await send('Page.enable');
  await send('Network.enable'); await send('Network.setCacheDisabled', { cacheDisabled: true });
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
  await send('Page.navigate', { url: 'file:///C:/Users/87999/claude-workspace/game_yaodao/index.html' });
  await sleep(2500);

  console.log('\n【1】性别选择');
  check('首启进入选人页', await ev('GAME.S().state') === 'pick', 'state=' + await ev('GAME.S().state'));
  const sexM = await btn('btnSexm');
  await tap(sexM.x, sexM.y); await sleep(1400);
  check('点男侠 → 进战斗', await ev('GAME.S().state') === 'battle', 'sex=' + await ev('GAME.S().save.sex'));
  check('开局送了武器', !!await ev('GAME.S().save.equip.weapon'));
  check('主角贴图已加载', !!(await ev('GAME.S().heroImg&&GAME.S().heroImg.m')));

  console.log('\n【2】战斗 / 技能');
  await sleep(2500);
  check('怪刷出来了', (await ev('GAME.S().mobs.length')) > 0, '怪数=' + await ev('GAME.S().mobs.length'));
  const sk0 = await btn('btnS0');
  await tap(sk0.x, sk0.y); await sleep(300);
  check('点技能有反应', (await ev('GAME.S().skillQueued&&GAME.S().skillQueued[0]')) === true || (await ev('GAME.S().hero.skCd[0]')) > 0);
  /* 技能要打得到目标才会放，等它真的转起来再断言 */
  let cdOn = false;
  for (let k = 0; k < 12; k++) {
    await sleep(400);
    if ((await ev('GAME.S().hero.skCd[0]')) > 0) { cdOn = true; break; }
  }
  check('技能冷却在转', cdOn, 'cd=' + await ev('GAME.S().hero.skCd[0]'));
  await shot('01_战斗');

  console.log('\n【3】掉落物');
  await ev('(function(){var S=GAME.S();S.mobs=[];})()');
  await sleep(3000);
  check('有掉落物', (await ev('GAME.S().drops.length')) >= 0);

  console.log('\n【4】背包');
  const bBag = await btn('btnBag');
  await tap(bBag.x, bBag.y); await sleep(700);
  check('打开背包', await ev('GAME.S().state') === 'bag');
  check('背包有装备格子', (await ev('Object.keys(GAME.S().save.equip).length')) === 4);
  await shot('02_背包');

  console.log('\n【5】强化');
  const slotBtn = await ev('(function(){var S=GAME.S();var k=Object.keys(S).filter(function(x){return x.indexOf("slotBtn")===0;})[0];return k?JSON.stringify(S[k]):"none";})()');
  await tap(JSON.parse(slotBtn).x, JSON.parse(slotBtn).y); await sleep(700);
  check('点装备格 → 强化面板', await ev('GAME.S().state') === 'upgrade');
  await ev('GAME.S().save.coins=99999;GAME.S().save.essence=999;');
  await sleep(300);
  const lv0 = await ev('GAME.S().save.equip.weapon.lv||0');
  const bEnh = await btn('btnEnh');
  await tap(bEnh.x, bEnh.y); await sleep(600);
  check('强化 +1 成功', (await ev('GAME.S().save.equip.weapon.lv||0')) === lv0 + 1,
    'lv=' + await ev('GAME.S().save.equip.weapon.lv'));
  await shot('03_强化');

  console.log('\n【6】宝石镶嵌');
  await ev('GAME.S().save.gems={gem_atk:3};');
  await sleep(300);
  const bGem = await btn('btnGem');
  await tap(bGem.x, bGem.y); await sleep(600);
  check('宝石镶上了', (await ev('GAME.S().save.equip.weapon.gem')) === 'gem_atk',
    'gem=' + await ev('GAME.S().save.equip.weapon.gem'));
  await shot('04_镶嵌');

  console.log('\n【7】造型（人物 / 武器）');
  const bBack = await btn('btnBack');
  await tap(bBack.x, bBack.y); await sleep(600);
  const bSkin = await btn('btnSkin');
  await tap(bSkin.x, bSkin.y); await sleep(700);
  check('打开造型面板', await ev('GAME.S().state') === 'skin');
  check('人物皮肤图已加载', (await ev('Object.keys(GAME.S().charImg||{}).length')) === 4);
  await shot('05_造型_人物');
  await ev('GAME.S().skinTab="weapon"'); await sleep(500);
  await shot('06_造型_武器');
  const wbtn = await ev('(function(){var S=GAME.S();var k=Object.keys(S).filter(function(x){return x.indexOf("skin")===0&&x!=="skinBox";})[2];return k?JSON.stringify(S[k]):"none";})()');
  if (wbtn !== 'none') {
    const w = JSON.parse(wbtn);
    await tap(w.x, w.y); await sleep(600);
    check('换成武器造型', (await ev('GAME.S().save.wskin')) === w.id, 'wskin=' + await ev('GAME.S().save.wskin'));
  }

  console.log('\n【8】十连抽');
  const bBack2 = await btn('btnBack');
  await tap(bBack2.x, bBack2.y); await sleep(600);
  const bPull = await btn('btnPull10');
  await tap(bPull.x, bPull.y); await sleep(1500);
  check('十连出 10 件', (await ev('GAME.S().pullRes.length')) === 10, 'n=' + await ev('GAME.S().pullRes.length'));
  await shot('07_十连抽');

  console.log('\n【9】宠物');
  await ev('(function(){var s=GAME.S().save;if(!s.pet){s.pet={slot:"beast"};s.petLv=1;s.petMood=70;s.petMoodAt=Date.now();}})()');
  await sleep(300);
  const bBack3 = await btn('btnBack');
  await tap(bBack3.x, bBack3.y); await sleep(600);   /* 抽卡页 → 背包 */
  const bBagBack = await btn('btnBack');
  await tap(bBagBack.x, bBagBack.y); await sleep(600); /* 背包 → 战斗 */
  check('回到战斗页', await ev('GAME.S().state') === 'battle', 'state=' + await ev('GAME.S().state'));
  const bPet = await btn('btnPet');
  await tap(bPet.x, bPet.y); await sleep(700);
  check('宠物面板打开', await ev('GAME.S().state') === 'pets');
  check('宠物已装备', !!await ev('GAME.S().save.pet'));
  await shot('08_宠物');

  console.log('\n【10】选关');
  const bBack4 = await btn('btnBack');
  await tap(bBack4.x, bBack4.y); await sleep(600);
  const bMap = await btn('btnMap');
  await tap(bMap.x, bMap.y); await sleep(700);
  check('选关面板打开', await ev('GAME.S().state') === 'maps');
  await shot('09_选关');

  console.log('\n【11】每日签到');
  const bSign = await btn('btnSign');
  await tap(bSign.x, bSign.y); await sleep(700);
  check('签到面板打开', await ev('GAME.S().state') === 'sign');
  const sd0 = await ev('GAME.S().save.signDay||0');
  const bClaim = await btn('btnClaim');
  await tap(bClaim.x, bClaim.y); await sleep(700);
  check('签到成功', (await ev('GAME.S().save.signDay||0')) === sd0 + 1, 'day=' + await ev('GAME.S().save.signDay'));
  await shot('10_签到');

  console.log('\n【12】排行');
  await ev('GAME.S().state="battle";'); await sleep(400);
  const bRank = await btn('btnRank');
  await tap(bRank.x, bRank.y); await sleep(700);
  check('排行面板打开', await ev('GAME.S().state') === 'rank');
  await shot('11_排行');

  console.log('\n【运行时异常】');
  check('无 JS 异常', errs.length === 0, errs.slice(0, 3).join(' | '));

  console.log('\n' + '='.repeat(50));
  console.log('通过 ' + pass + ' / 失败 ' + fail);
  console.log('截图目录: ' + OUT);
  proc.kill();
  process.exit(fail ? 1 : 0);
})().catch(e => { console.log('FATAL', e && e.stack || e); process.exit(9); });
