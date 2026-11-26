const { spawn } = require('child_process');
const fs = require('fs');
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9461;
const OUT = 'C:/Users/87999/.claude/tmp/yd_pet';
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
  const tap=async(x,y)=>{await send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y}]});await sleep(80);
   await send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await sleep(400);};
  const shot=async n=>{const r=await send('Page.captureScreenshot',{format:'png'});
   fs.writeFileSync(OUT+'/'+n+'.png',Buffer.from(r.result.data,'base64'));console.log('  截图',n);};
  await send('Runtime.enable');await send('Page.enable');
  await send('Network.enable');await send('Network.setCacheDisabled',{cacheDisabled:true});
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:2,mobile:true});
  await send('Page.navigate',{url:'file:///C:/Users/87999/claude-workspace/game_yaodao/index.html'});
  await sleep(2500);
  const p0=JSON.parse(await ev('(function(){var S=GAME.S();return JSON.stringify({m:S.btnSexm});})()'));
  await tap(p0.m.x,p0.m.y); await sleep(1200);
  console.log('进战斗:',await ev('GAME.S().state'));
  // 反复抽卡直到出宠物
  for(let i=0;i<40;i++){
    const has=await ev('!!GAME.S().save.pet');
    if(has==='true'){console.log('第'+(i+1)+'次抽到宠物！');break;}
    await ev('(function(){var G=window.GAME;G.S().pullRes=G.S().pullRes;})()');
    await ev('(function(){var s=GAME.S().save;for(var k=0;k<10;k++){var ev2=Math.random()<0.06;if(ev2&&!s.pet){s.pet={slot:"beast"};s.petLv=1;s.petMood=70;s.petMoodAt=Date.now();break;}}}())()');
  }
  console.log('宠物 =',await ev('JSON.stringify(GAME.S().save.pet)'),'| 等级',await ev('GAME.S().save.petLv'));
  // 打开宠物面板
  const pb=JSON.parse(await ev('(function(){var b=GAME.S().btnPet;return b?JSON.stringify(b):"none";})()'));
  await tap(pb.x,pb.y); await sleep(700);
  console.log('state =',await ev('GAME.S().state'));
  await shot('01_宠物');
  console.log('日志:',logs.slice(-4).join(' || ')||'(无)');
  proc.kill();process.exit(0);
})().catch(e=>{console.log('FATAL',e.message);process.exit(9);});
