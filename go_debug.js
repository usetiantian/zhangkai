const http = require("http");
function httpGet(p){ return new Promise((res,rej)=>{ http.get({host:"127.0.0.1",port:9555,path:p},r=>{let d="";r.on("data",c=>d+=c);r.on("end",()=>res(d));}).on("error",rej); }); }
(async()=>{
  const tabs = JSON.parse(await httpGet("/json/list"));
  const page = tabs.find(x=>x.type==="page");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id=0; const pend=new Map(); const errs=[];
  ws.onmessage = async m=>{ let r=m.data; if(typeof r!=="string") r=await r.text(); const o=JSON.parse(r);
    if(o.id&&pend.has(o.id)){pend.get(o.id)(o);pend.delete(o.id);}
    if(o.method==="Runtime.exceptionThrown") errs.push(((o.params.exceptionDetails.exception||{}).description||"").slice(0,300));
    if(o.method==="Runtime.consoleAPICalled" && o.params.type==="error") errs.push("console: "+o.params.args.map(a=>a.value||a.description||"").join(" ").slice(0,200)); };
  await new Promise(r=>ws.onopen=r);
  const cmd=(m,p)=>new Promise(r=>{const i=++id;pend.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});
  const ev=async(e)=>{const r=await cmd("Runtime.evaluate",{expression:e,returnByValue:true});
    if(r.result.exceptionDetails) return "EX: "+((r.result.exceptionDetails.exception||{}).description||"").slice(0,250);
    return r.result.result ? r.result.result.value : undefined;};
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  const mouse=(t,x,y)=>cmd("Input.dispatchMouseEvent",{type:t,x,y,button:"left",clickCount:t==="mousePressed"?1:0});
  await cmd("Page.enable"); await cmd("Runtime.enable");
  await cmd("Page.navigate",{url:"file:///C:/Users/87999/claude-workspace/game/%E6%9E%9C%E5%AD%90.html?dbg="+Date.now()});
  await sleep(7000);

  // 卸载所有皮肤（先测试默认情况）
  await ev('window.__meta.save.skinEquipped = {}; window.__meta.persist(); "cleared"');

  // 进五子棋
  await ev('var cs=document.querySelectorAll(".hub-card"); for(var i=0;i<cs.length;i++){if(cs[i].getAttribute("data-id")==="gomoku"){cs[i].click();break}}');
  await sleep(500);
  await ev('var pm=document.querySelector("#pm-1"); if(pm)pm.click(); "started"');
  await sleep(1200);

  // 检查 goCol
  var goCol = await ev('(function(){try{return JSON.stringify({v:typeof goCol==="undefined"?"undef":goCol})}catch(e){return "no-var:"+e.message}})()');
  console.log("goCol in scope:", goCol);

  // 找画布并点击棋盘中心
  var cvInfo = await ev('(function(){var c=document.getElementById("gm-c");if(!c)return "no-canvas";var r=c.getBoundingClientRect();return JSON.stringify({w:r.width,h:r.height,x:r.x,y:r.y})})()');
  console.log("canvas:", cvInfo);
  var info = JSON.parse(cvInfo || "{}");
  if (info.w){
    var cx = info.x + info.w/2;
    var cy = info.y + info.h/2;
    console.log("clicking at", cx, cy);
    await mouse("mousePressed", cx, cy);
    await mouse("mouseReleased", cx, cy);
    await sleep(600);
    // 检查棋盘状态
    var b77 = await ev('window.__goG ? window.__goG.b[7][7] : "no-goG"');
    var turn = await ev('window.__goG ? window.__goG.turn : "?"');
    console.log("place(7,7):", b77, "| turn:", turn);

    // 截图看棋子
    const fs = require("fs");
    var shot = await cmd("Page.captureScreenshot",{format:"png"});
    fs.writeFileSync("game/shots/go_debug.png", Buffer.from(shot.result.data,"base64"));
    console.log("shot saved");
  }

  console.log("ERRORS:", errs.length ? errs.slice(0,3).join("\n---\n") : "none");
  ws.close(); process.exit(0);
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
