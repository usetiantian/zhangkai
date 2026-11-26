/* 地面特征（mp.fx）逐图截图验证：解锁全图 → 依次进入 map2~map7 战斗截图。
   跑法：node tools/yd_ground.js  （H5，headless Edge） */
const { spawn } = require('child_process');
const fs = require('fs');
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9471;
const OUT = 'C:/Users/87999/.claude/tmp/yd_ground';
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const proc = spawn(EDGE, ['--headless=new','--disable-gpu','--no-sandbox',
    '--remote-debugging-port='+PORT,'--window-size=390,844',
    '--user-data-dir='+OUT+'/profile_'+Date.now(),'about:blank'], {stdio:'ignore'});
  let list=null;
  for(let i=0;i<30;i++){await sleep(500);try{list=await(await fetch('http://127.0.0.1:'+PORT+'/json/list')).json();if(list.length)break;}catch(e){}}
  const page=list.find(t=>t.type==='page');
  const ws=new WebSocket(page.webSocketDebuggerUrl);
  let id=0;const pend=new Map();const logs=[];
  ws.onmessage=e=>{const m=JSON.parse(e.data);
   if(m.id&&pend.has(m.id)){pend.get(m.id)(m);pend.delete(m.id);}
   if(m.method==='Runtime.exceptionThrown')logs.push('[EXC] '+JSON.stringify(m.params.exceptionDetails).slice(0,250));};
  await new Promise(r=>ws.onopen=r);
  const send=(m,p)=>new Promise(r=>{const i=++id;pend.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});
  const ev=async e=>{const r=await send('Runtime.evaluate',{expression:e,returnByValue:true,awaitPromise:true});
   if(r.result&&r.result.exceptionDetails)return 'EXC '+JSON.stringify(r.result.exceptionDetails).slice(0,250);
   const rr=r.result&&r.result.result;return rr?(rr.value!==undefined?rr.value:rr.description):'(undef)';};
  const tap=async(x,y)=>{await send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y}]});await sleep(80);
   await send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await sleep(450);};
  const shot=async n=>{const r=await send('Page.captureScreenshot',{format:'png'});
   fs.writeFileSync(OUT+'/'+n+'.png',Buffer.from(r.result.data,'base64'));console.log('  截图',n);};
  await send('Runtime.enable');await send('Page.enable');
  await send('Network.enable');await send('Network.setCacheDisabled',{cacheDisabled:true});
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:2,mobile:true});
  await send('Page.navigate',{url:'file:///C:/Users/87999/claude-workspace/game_yaodao/dist/index.html'});
  await sleep(2500);
  const p0=JSON.parse(await ev('(function(){var S=GAME.S();return JSON.stringify({m:S.btnSexm});})()'));
  await tap(p0.m.x,p0.m.y); await sleep(1200);
  console.log('① 解锁全部地图');
  await ev('(function(){var S=GAME.S();S.save.maxWave=6;G.persist();return "ok";})()');
  for (var idx=1; idx<=6; idx++) {
    await tap(70,28); await sleep(600);            /* btnMap 打开选关 */
    const b=JSON.parse(await ev('(function(){var S=GAME.S();return JSON.stringify(S["mapBtn'+idx+'"]);})()'));
    if(!b||b.locked){console.log('  map'+(idx+1)+' LOCKED/SKIP',JSON.stringify(b));continue;}
    await tap(b.x,b.y); await sleep(1400);
    console.log('  map'+(idx+1)+' =',await ev('GAME.S().map.name'),'| fx =',await ev('GAME.S().map.fx||"(默认)"'));
    await shot('map'+(idx+1));
  }
  console.log('异常:',logs.length?logs.join(' || '):'(无)');
  proc.kill();process.exit(0);
})().catch(e=>{console.log('FATAL',e.message);process.exit(9);});
