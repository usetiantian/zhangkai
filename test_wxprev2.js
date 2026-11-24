const http = require("http");
function httpGet(path){ return new Promise((res,rej)=>{ http.get({host:"127.0.0.1",port:9555,path},r=>{let d="";r.on("data",c=>d+=c);r.on("end",()=>res(d));}).on("error",rej); }); }
(async()=>{
  const tabs = JSON.parse(await httpGet("/json/list"));
  const page = tabs.find(x=>x.type==="page");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id=0; const pend=new Map();
  ws.onmessage = async m=>{ let r=m.data; if(typeof r!=="string") r=await r.text(); const o=JSON.parse(r); if(o.id&&pend.has(o.id)){pend.get(o.id)(o);pend.delete(o.id);} };
  await new Promise(r=>ws.onopen=r);
  const cmd=(m,p)=>new Promise(r=>{const i=++id;pend.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});
  const ev=async(e)=>{const r=await cmd("Runtime.evaluate",{expression:e,returnByValue:true});return r.result.result?r.result.result.value:"EX:"+(r.result.exceptionDetails&&r.result.exceptionDetails.text);};
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  const mouse=(t,x,y)=>cmd("Input.dispatchMouseEvent",{type:t,x,y,button:"left",clickCount:t==="mousePressed"?1:0});
  await cmd("Page.enable"); await cmd("Runtime.enable");
  await cmd("Emulation.clearDeviceMetricsOverride");
  await cmd("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:2,mobile:true});
  await cmd("Page.navigate",{url:"file:///C:/Users/87999/claude-workspace/game/wx/preview.html?t="+Date.now()});
  await sleep(6000);
  const st = async(tag) => console.log(tag, await ev(`(function(){var M=window.__mini;return JSON.stringify({mode:M.mode,screen:M.screen,toast:M.toast,last:M.lastGame})})()`));
  await st("boot:");
  // 1) 直接切乐园 tab
  await mouse("mousePressed", 390/7*3.5, 816); await mouse("mouseReleased", 390/7*3.5, 816);
  await sleep(800); await st("tab-arcade:");
  // 2) 点 match3 卡
  await mouse("mousePressed", 290, 298); await mouse("mouseReleased", 290, 298);
  await sleep(2200); await st("tap-match3:");
  console.log("m3:", await ev(`(function(){var D=window.__minidom.document;var c=D.getElementById("m3-c");return JSON.stringify({m3c:!!c,hook:!!(window.__arcade&&window.__arcade._m3),sub:(D.getElementById("arc-sub")||{}).textContent})})()`));
  // 3) 精灵（先回 shell）
  await ev(`(function(){var M=window.__mini;M.mode="shell";var ar=window.__minidom.document.getElementById("arcade-root");if(ar)ar.innerHTML="";})()`);
  await sleep(1500);
  await mouse("mousePressed", 368, 754); await mouse("mouseReleased", 368, 754);
  await sleep(700); await st("tap-fairy:");
  console.log("mood:", await ev(`(!!(window.__mini._moodBoxes&&window.__mini._moodBoxes.length))`));
  ws.close(); process.exit(0);
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
