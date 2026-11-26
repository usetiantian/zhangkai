// 看怪物贴图：进战斗 → 等怪刷出来 → 截图
const { spawn } = require('child_process');
const fs = require('fs');
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9458;
const OUT = 'C:/Users/87999/.claude/tmp/yd_mob';
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
   if(m.method==='Runtime.consoleAPICalled')logs.push('['+m.params.type+'] '+(m.params.args||[]).map(a=>a.value!==undefined?a.value:(a.description||a.type)).join(' ').slice(0,200));
   if(m.method==='Runtime.exceptionThrown')logs.push('[EXC] '+JSON.stringify(m.params.exceptionDetails).slice(0,250));};
  await new Promise(r=>ws.onopen=r);
  const send=(m,p)=>new Promise(r=>{const i=++id;pend.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});
  const ev=async e=>{const r=await send('Runtime.evaluate',{expression:e,returnByValue:true,awaitPromise:true});
   if(r.result&&r.result.exceptionDetails)return 'EXC '+JSON.stringify(r.result.exceptionDetails).slice(0,250);
   const rr=r.result&&r.result.result;return rr?(rr.value!==undefined?rr.value:rr.description):'(undef)';};
  const shot=async n=>{const r=await send('Page.captureScreenshot',{format:'png'});
   fs.writeFileSync(OUT+'/'+n+'.png',Buffer.from(r.result.data,'base64'));console.log('  截图',n);};
  await send('Runtime.enable');await send('Page.enable');
  await send('Network.enable');
  await send('Network.setCacheDisabled', {cacheDisabled: true});
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:2,mobile:true});
  await send('Page.navigate',{url:'file:///C:/Users/87999/claude-workspace/game_yaodao/index.html'});
  await sleep(2500);
  const p=JSON.parse(await ev('(function(){var S=GAME.S();return JSON.stringify({m:S.btnSexm});})()'));
  await send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:p.m.x,y:p.m.y}]});
  await sleep(80);
  await send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await sleep(1500);
  console.log('怪图加载数 =',await ev('Object.keys(GAME.S().mobImg||{}).length'));
  console.log('地图图数 =',await ev('Object.keys(GAME.S().mapImg||{}).length'));
  for(let i=1;i<=4;i++){
    await sleep(2500);
    console.log('  怪数=',await ev('GAME.S().mobs.length'),'| 波=',await ev('GAME.S().wave'),'| id=',await ev('JSON.stringify(GAME.S().mobs.map(function(m){return m.id;}))'));
    await shot('t'+i);
  }
  console.log('日志:',logs.slice(-6).join(' || ')||'(无)');
  proc.kill();process.exit(0);
})().catch(e=>{console.log('FATAL',e.message);process.exit(9);});
