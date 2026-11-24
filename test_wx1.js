/* wx 包浏览器模拟冒烟：启动 → 进塔防 → 建塔 → 进消除 → 滑动 */
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
    if(o.method==="Runtime.exceptionThrown") errs.push((o.params.exceptionDetails.exception&&o.params.exceptionDetails.exception.description)||o.params.exceptionDetails.text); };
  await new Promise(r=>ws.onopen=r);
  const cmd=(m,p)=>new Promise(r=>{const i=++id;pend.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});
  const ev=async(e)=>{const r=await cmd("Runtime.evaluate",{expression:e,returnByValue:true});if(r.result.exceptionDetails)throw new Error("eval: "+JSON.stringify(r.result.exceptionDetails.exception&&r.result.exceptionDetails.exception.description||r.result.exceptionDetails).slice(0,400));return r.result.result.value;};
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  const mouse=(t,x,y)=>cmd("Input.dispatchMouseEvent",{type:t,x,y,button:"left",clickCount:t==="mousePressed"?1:0});

  await cmd("Page.enable"); await cmd("Runtime.enable");
  await cmd("Emulation.clearDeviceMetricsOverride");
  await cmd("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:2,mobile:true});
  await cmd("Page.navigate",{url:"file:///C:/Users/87999/claude-workspace/game/wx/test.html?t="+Date.now()});
  await sleep(6000);

  const boot = await ev(`({mini:!!window.__mini, mode:window.__mini&&window.__mini.mode, md:!!window.__minidom,
    game:!!window.__game, arcade:!!window.__arcade, ui:!!window.__ui, meta:!!window.__meta,
    levels:(window.__LEVELS||[]).length, c:!!document.getElementById("c"),
    saveCoins:window.__meta&&window.__meta.save.coins, unlocked:window.__meta&&window.__meta.save.unlocked})`);
  console.log("BOOT:", JSON.stringify(boot));
  const shot0 = await cmd("Page.captureScreenshot",{format:"png"});
  fs.writeFileSync("game/shots/wx_boot.png", Buffer.from(shot0.result.data,"base64"));

  // ---- 点第1关（地图第1格：中心 ~ (39, HUD 40+10+26)）----
  await mouse("mousePressed", 39, 76); await mouse("mouseReleased", 39, 76);
  await sleep(1800);
  const td = await ev(`({mode:window.__mini.mode, last:window.__mini.lastGame,
    hud:document.getElementById("hud-level").textContent, paused:false,
    st:window.__game.state.waves, canvas:(function(){var c=document.getElementById("c");return c&&c._r?Math.round(c._r.w)+"x"+Math.round(c._r.h):"no-rect"})()})`);
  console.log("TD:", JSON.stringify(td));
  const shot1 = await cmd("Page.captureScreenshot",{format:"png"});
  fs.writeFileSync("game/shots/wx_td.png", Buffer.from(shot1.result.data,"base64"));

  // ---- 点一个建造按钮（.bk 第一个），再点画布建塔 ----
  const bk = await ev(`(function(){var els=document.querySelectorAll(".bk");var r=els[0].getBoundingClientRect();return r.left+","+r.top+","+r.width+","+r.height})()`);
  const [bl,bt,bw,bh] = bk.split(",").map(Number);
  await mouse("mousePressed", bl+bw/2, bt+bh/2); await mouse("mouseReleased", bl+bw/2, bt+bh/2);
  await sleep(400);
  const cvr = await ev(`(function(){var r=document.getElementById("c").getBoundingClientRect();return r.left+","+r.top+","+r.width+","+r.height})()`);
  const [cl,ct_,cw,ch] = cvr.split(",").map(Number);
  // 点画布中部一个建造位附近（第一个 pad 通常在路径旁）
  await mouse("mousePressed", cl+cw*0.3, ct_+ch*0.35); await mouse("mouseReleased", cl+cw*0.3, ct_+ch*0.35);
  await sleep(600);
  const built = await ev(`window.__game.state`);
  console.log("BUILD:", JSON.stringify(built));
  const shot2 = await cmd("Page.captureScreenshot",{format:"png"});
  fs.writeFileSync("game/shots/wx_td_build.png", Buffer.from(shot2.result.data,"base64"));

  // ---- 退出到乐园 → 消除 ----
  const menu = await ev(`(function(){var b=document.getElementById("btn-pause-menu");var r=b.getBoundingClientRect();return r.left+","+r.top+","+r.width+","+r.height})()`);
  const [ml,mt,mw,mh]=menu.split(",").map(Number);
  await mouse("mousePressed", ml+mw/2, mt+mh/2); await mouse("mouseReleased", ml+mw/2, mt+mh/2);
  await sleep(900);
  const back = await ev(`({mode:window.__mini.mode, screen:window.__mini.screen})`);
  console.log("EXIT TD:", JSON.stringify(back));
  // 切到乐园 tab（第4个 tab，x = 3.5/7*W）
  await mouse("mousePressed", 390/7*3.5, 844-28); await mouse("mouseReleased", 390/7*3.5, 844-28);
  await sleep(700);
  // 点第6张卡（match3 = GAMES[5]：row2,col0 → x=10+cw/2? cols=2: (W-30)/2=180 → x=10+90=100; rows: top=40+12=52, chh=92 → row2 y=52+2*102=256
  await mouse("mousePressed", 100, 52+2*102+46); await mouse("mouseReleased", 100, 52+2*102+46);
  await sleep(2000);
  const m3 = await ev(`({mode:window.__mini.mode, last:window.__mini.lastGame, sub:document.getElementById("arc-sub")?document.getElementById("arc-sub").textContent:"",
    hasCanvas:!!document.getElementById("m3-c"), errs:window.__mini.mode})`);
  console.log("M3:", JSON.stringify(m3));
  const shot3 = await cmd("Page.captureScreenshot",{format:"png"});
  fs.writeFileSync("game/shots/wx_m3.png", Buffer.from(shot3.result.data,"base64"));

  // ---- 滑动换位 ----
  const swap = await ev(`(function(){
    var A2=__arcade; var g=A2._m3&&A2._m3.g; if(!g) return null;
    function fp(){ for(var r=0;r<8;r++)for(var c=0;c<7;c++){ g.swapCell([r,c],[r,c+1]); var ok=g.findRuns().length>0; g.swapCell([r,c],[r,c+1]); if(ok)return [r,c,r,c+1]; }
      for(var r=0;r<7;r++)for(var c=0;c<8;c++){ g.swapCell([r,c],[r+1,c]); var ok=g.findRuns().length>0; g.swapCell([r,c],[r+1,c]); if(ok)return [r,c,r+1,c]; } return null; }
    var p=fp(); if(!p) return null;
    var cv=document.getElementById("m3-c"); var rc=cv.getBoundingClientRect();
    function ctr(r,c){ return {x:rc.left+(c+0.5)*rc.width/8, y:rc.top+(r+0.5)*rc.height/8}; }
    return {p:p, a:ctr(p[0],p[1]), b:ctr(p[2],p[3]), moves:document.getElementById("m3-x").textContent};
  })()`);
  if (swap){
    await mouse("mousePressed", swap.a.x, swap.a.y);
    await mouse("mouseMoved", (swap.a.x+swap.b.x)/2, (swap.a.y+swap.b.y)/2);
    await mouse("mouseMoved", swap.b.x, swap.b.y);
    await mouse("mouseReleased", swap.b.x, swap.b.y);
    await sleep(2600);
    const after = await ev(`({x:document.getElementById("m3-x").textContent, tip:document.getElementById("m3-tip").textContent})`);
    console.log("SWIPE:", swap.moves, "→", JSON.stringify(after));
  } else console.log("SWIPE: no pair");

  console.log("EXCEPTIONS(" + errs.length + "):", errs.slice(0,4).join(" | ").slice(0, 600));
  ws.close(); process.exit(0);
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
