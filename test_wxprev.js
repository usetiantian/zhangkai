/* 浏览器预览器实测：加载 wx/preview.html → 点关卡 → 塔防 → 截图 */
const http = require("http");
const fs = require("fs");
function httpGet(path){ return new Promise((res,rej)=>{ http.get({host:"127.0.0.1",port:9555,path},r=>{let d="";r.on("data",c=>d+=c);r.on("end",()=>res(d));}).on("error",rej); }); }
(async()=>{
  const tabs = JSON.parse(await httpGet("/json/list"));
  const page = tabs.find(x=>x.type==="page");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id=0; const pend=new Map(); const errs=[];
  ws.onmessage = async m=>{ let r=m.data; if(typeof r!=="string") r=await r.text(); const o=JSON.parse(r);
    if(o.id&&pend.has(o.id)){pend.get(o.id)(o);pend.delete(o.id);}
    if(o.method==="Runtime.exceptionThrown") errs.push(((o.params.exceptionDetails.exception||{}).description||o.params.exceptionDetails.text||"").slice(0,150)); };
  await new Promise(r=>ws.onopen=r);
  const cmd=(m,p)=>new Promise(r=>{const i=++id;pend.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});
  const ev=async(e)=>{const r=await cmd("Runtime.evaluate",{expression:e,returnByValue:true});
    if(r.result.exceptionDetails) throw new Error("eval: "+JSON.stringify(r.result.exceptionDetails.exception&&r.result.exceptionDetails.exception.description||r.result.exceptionDetails).slice(0,300));
    return r.result.result.value;};
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  const mouse=(t,x,y)=>cmd("Input.dispatchMouseEvent",{type:t,x,y,button:"left",clickCount:t==="mousePressed"?1:0});

  await cmd("Page.enable"); await cmd("Runtime.enable");
  await cmd("Emulation.clearDeviceMetricsOverride");
  await cmd("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:2,mobile:true});
  await cmd("Page.navigate",{url:"file:///C:/Users/87999/claude-workspace/game/wx/preview.html?t="+Date.now()});
  await sleep(6000);
  const boot = await ev(`({mini:!!window.__mini, mode:window.__mini&&window.__mini.mode, md:!!window.__minidom,
    game:!!window.__game, meta:!!window.__meta, title:document.title})`);
  console.log("BOOT:", JSON.stringify(boot));
  let shot = await cmd("Page.captureScreenshot",{format:"png"});
  fs.writeFileSync("game/shots/wxprev_shell.png", Buffer.from(shot.result.data,"base64"));

  // 点第1关 → 塔防
  await mouse("mousePressed", 39, 96); await mouse("mouseReleased", 39, 96);
  await sleep(2200);
  const td = await ev(`({mode:window.__mini.mode, last:window.__mini.lastGame,
    waves:window.__game.state.waves, canvasRect:(window.__minidom.debugHits().find(h=>h.el.id==="c")||{}).w})`);
  console.log("TD:", JSON.stringify(td));
  shot = await cmd("Page.captureScreenshot",{format:"png"});
  fs.writeFileSync("game/shots/wxprev_td.png", Buffer.from(shot.result.data,"base64"));

  // 退出 → 乐园 → 消除 → 滑一下
  const menuHit = await ev(`(function(){var h=window.__minidom.debugHits().find(h=>h.el.id==="btn-pause-menu");return h?[h.x+h.w/2,h.y+h.h/2]:null})()`);
  if (menuHit){ await mouse("mousePressed", menuHit[0], menuHit[1]); await mouse("mouseReleased", menuHit[0], menuHit[1]); }
  await sleep(900);
  await mouse("mousePressed", 390/7*3.5, 816); await mouse("mouseReleased", 390/7*3.5, 816);
  await sleep(600);
  await mouse("mousePressed", 290, 298); await mouse("mouseReleased", 290, 298);
  await sleep(2000);
  const m3 = await ev(`({mode:window.__mini.mode, hasM3:!!window.__minidom.document.getElementById("m3-c"), m3hook:!!(window.__arcade&&window.__arcade._m3), viaDom:(window.__wxSim?1:0)})`);
  console.log("M3:", JSON.stringify(m3));
  shot = await cmd("Page.captureScreenshot",{format:"png"});
  fs.writeFileSync("game/shots/wxprev_m3.png", Buffer.from(shot.result.data,"base64"));

  // 精灵心情
  await ev(`(function(){var m=window.__mini; m.mode="shell"; var ar=window.__minidom.document.getElementById("arcade-root"); if(ar) ar.innerHTML=""; if(window.__game) window.__game.setPaused(true);})()`);
  await sleep(1200);
  await mouse("mousePressed", 368, 754); await mouse("mouseReleased", 368, 754);
  await sleep(600);
  const mood = await ev(`({open:!!(window.__mini._moodBoxes&&window.__mini._moodBoxes.length===4)})`);
  console.log("MOOD:", JSON.stringify(mood));
  shot = await cmd("Page.captureScreenshot",{format:"png"});
  fs.writeFileSync("game/shots/wxprev_mood.png", Buffer.from(shot.result.data,"base64"));

  console.log("EXCEPTIONS:", errs.length ? errs.slice(0,3) : "none");
  ws.close(); process.exit(0);
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
