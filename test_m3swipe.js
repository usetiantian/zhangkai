/* 消消乐：滑动换位 / 点选换位 / 下一关按钮 */
const http = require("http");
const fs = require("fs");
function httpGet(path){ return new Promise((res,rej)=>{ http.get({host:"127.0.0.1",port:9555,path},r=>{let d="";r.on("data",c=>d+=c);r.on("end",()=>res(d));}).on("error",rej); }); }
(async()=>{
  const tabs = JSON.parse(await httpGet("/json/list"));
  const page = tabs.find(x=>x.type==="page");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id=0; const pend=new Map();
  ws.onmessage = async m=>{ let r=m.data; if(typeof r!=="string") r=await r.text(); const o=JSON.parse(r); if(o.id&&pend.has(o.id)){pend.get(o.id)(o);pend.delete(o.id);} };
  await new Promise(r=>ws.onopen=r);
  const cmd=(m,p)=>new Promise(r=>{const i=++id;pend.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});
  const ev=async(expr)=>{const r=await cmd("Runtime.evaluate",{expression:expr,returnByValue:true});if(r.result.exceptionDetails)throw new Error(JSON.stringify(r.result.exceptionDetails.exception||r.result.exceptionDetails).slice(0,300));return r.result.result.value;};
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  const mouse=(t,x,y,btn)=>cmd("Input.dispatchMouseEvent",{type:t,x,y,button:btn||"left",clickCount:t==="mousePressed"?1:0});

  await cmd("Page.enable"); await cmd("Runtime.enable");
  await cmd("Emulation.clearDeviceMetricsOverride");
  await cmd("Emulation.setDeviceMetricsOverride",{width:1280,height:1600,deviceScaleFactor:1,mobile:false});
  await cmd("Page.navigate",{url:"file:///C:/Users/87999/claude-workspace/game/%E6%9E%9C%E5%AD%90.html?t="+Date.now()});
  await sleep(7000);

  await ev("window.__ui.showScreen('arcade'); __arcade.startGame('match3',1,1); 'started'");
  await sleep(1200);
  console.log("关卡副标题:", await ev("document.getElementById('arc-sub').textContent"));

  // 找一个可消的相邻对 + 画布坐标
  const info = await ev(`(function(){
    var g=__arcade._m3.g;
    function findPair(){
      for(var r=0;r<8;r++)for(var c=0;c<7;c++){ g.swapCell([r,c],[r,c+1]); var ok=g.findRuns().length>0; g.swapCell([r,c],[r,c+1]); if(ok)return [r,c,r,c+1]; }
      for(var r=0;r<7;r++)for(var c=0;c<8;c++){ g.swapCell([r,c],[r+1,c]); var ok=g.findRuns().length>0; g.swapCell([r,c],[r+1,c]); if(ok)return [r,c,r+1,c]; }
      return null;
    }
    var p=findPair();
    var cv=document.getElementById('m3-c'); var rc=cv.getBoundingClientRect();
    function ctr(r,c){ return {x:rc.left+(c+0.5)*rc.width/8, y:rc.top+(r+0.5)*rc.height/8}; }
    return {pair:p, a:ctr(p[0],p[1]), b:ctr(p[2],p[3]), rect:[rc.left,rc.top,rc.width,rc.height], moves:document.getElementById('m3-x').textContent};
  })()`);
  console.log("可消对:", info.pair, "初始", info.moves);

  // ---- 1) 滑动换位 ----
  await mouse("mousePressed", info.a.x, info.a.y);
  await mouse("mouseMoved", (info.a.x+info.b.x)/2, (info.a.y+info.b.y)/2);
  await mouse("mouseMoved", info.b.x, info.b.y);
  await mouse("mouseReleased", info.b.x, info.b.y);
  await sleep(2600);
  const t1 = await ev(`({x:document.getElementById('m3-x').textContent, tip:document.getElementById('m3-tip').textContent, s:document.getElementById('m3-s0').textContent})`);
  console.log("滑动后:", JSON.stringify(t1));
  const swipeOK = t1.x !== info.moves && /消了/.test(t1.tip);
  console.log("滑动换位:", swipeOK ? "PASS" : "FAIL");

  // ---- 2) 点选换位（老交互保留） ----
  const info2 = await ev(`(function(){
    var g=__arcade._m3.g;
    function findPair(){
      for(var r=0;r<8;r++)for(var c=0;c<7;c++){ g.swapCell([r,c],[r,c+1]); var ok=g.findRuns().length>0; g.swapCell([r,c],[r,c+1]); if(ok)return [r,c,r,c+1]; }
      for(var r=0;r<7;r++)for(var c=0;c<8;c++){ g.swapCell([r,c],[r+1,c]); var ok=g.findRuns().length>0; g.swapCell([r,c],[r+1,c]); if(ok)return [r,c,r+1,c]; }
      return null;
    }
    var p=findPair(); if(!p) return null;
    var cv=document.getElementById('m3-c'); var rc=cv.getBoundingClientRect();
    function ctr(r,c){ return {x:rc.left+(c+0.5)*rc.width/8, y:rc.top+(r+0.5)*rc.height/8}; }
    return {pair:p, a:ctr(p[0],p[1]), b:ctr(p[2],p[3]), moves:document.getElementById('m3-x').textContent};
  })()`);
  if (info2 && info2.pair){
    await mouse("mousePressed", info2.a.x, info2.a.y); await mouse("mouseReleased", info2.a.x, info2.a.y);
    await sleep(150);
    await mouse("mousePressed", info2.b.x, info2.b.y); await mouse("mouseReleased", info2.b.x, info2.b.y);
    await sleep(2600);
    const t2 = await ev(`({x:document.getElementById('m3-x').textContent, tip:document.getElementById('m3-tip').textContent})`);
    const tapOK = t2.x !== info2.moves && /消了/.test(t2.tip);
    console.log("点选换位:", tapOK ? "PASS" : "FAIL", JSON.stringify(t2));
  } else console.log("点选换位: SKIP(无可消对)");

  // ---- 3) 过关 → 下一关按钮 ----
  await ev("__arcade._m3.win()");
  await sleep(2200);
  const card = await ev(`(function(){var n=document.getElementById('ar-next');var w=document.getElementById('arcres-wrap');
    return {hasNext:!!n, nextText:n?n.textContent:'', cardShown:!!w, title:w?w.querySelector('.ar-title').textContent:'', progress:__meta.m3Progress().lv};})()`);
  console.log("结算卡:", JSON.stringify(card));
  const nextOK = card.hasNext && /下一关/.test(card.nextText);
  console.log("下一关按钮:", nextOK ? "PASS" : "FAIL");
  await ev("document.getElementById('ar-next').click()");
  await sleep(1500);
  const after = await ev(`({sub:document.getElementById('arc-sub').textContent, cardGone:!document.getElementById('arcres-wrap'), lastLv:window.__arcLastLv})`);
  console.log("点下一关后:", JSON.stringify(after));
  const jumpOK = /第 2 关/.test(after.sub) && after.cardGone && after.lastLv===2;
  console.log("直达第2关:", jumpOK ? "PASS" : "FAIL");

  const all = swipeOK && nextOK && jumpOK;
  console.log(all ? "\n=== ALL PASS ===" : "\n=== SOME FAIL ===");
  ws.close(); process.exit(all?0:1);
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
