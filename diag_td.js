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
    if(o.method==="Runtime.exceptionThrown") errs.push(((o.params.exceptionDetails.exception||{}).description||"").slice(0,260));
    if(o.method==="Runtime.consoleAPICalled"&&o.params.type==="error") errs.push("console: "+o.params.args.map(a=>a.value||a.description||"").join(" ").slice(0,200)); };
  await new Promise(r=>ws.onopen=r);
  const cmd=(m,p)=>new Promise(r=>{const i=++id;pend.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});
  const ev=async(e)=>{const r=await cmd("Runtime.evaluate",{expression:e,returnByValue:true});return r.result.result?r.result.result.value:"EX:"+(r.result.exceptionDetails||{}).text;};
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  await cmd("Page.enable"); await cmd("Runtime.enable");
  await cmd("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:2,mobile:true});

  // H5 版
  await cmd("Page.navigate",{url:"file:///C:/Users/87999/claude-workspace/game/%E6%9E%9C%E5%AD%90.html?d="+Date.now()});
  await sleep(7000);
  const h5 = await ev(`(function(){
    try { window.__ui.startLevel(1); } catch(e){ return "startLevel EX: " + e.message; }
    return "ok";
  })()`);
  await sleep(2000);
  const h5state = await ev(`(function(){
    var c = document.getElementById("c");
    return JSON.stringify({canvas: !!c, cw: c && c.width, shown: c && c.getBoundingClientRect().width,
      state: window.__game.state, hud: (document.getElementById("hud-status")||{}).textContent});
  })()`);
  console.log("H5:", h5, h5state);
  let shot = await cmd("Page.captureScreenshot",{format:"png"});
  fs.writeFileSync("game/shots/diag_h5_td.png", Buffer.from(shot.result.data,"base64"));

  // wx 预览版
  await cmd("Page.navigate",{url:"file:///C:/Users/87999/claude-workspace/game/wx/preview.html?d="+Date.now()});
  await sleep(6000);
  const wxr = await ev(`(function(){
    var sg = window.__minidom.document.getElementById("scr-game");
    if (sg) sg.style.display = "block";
    try { window.__ui.startLevel(1); window.__mini.mode = "game"; } catch(e){ return "EX: " + e.message; }
    return "ok";
  })()`);
  await sleep(2000);
  const wxstate = await ev(`(function(){
    var D = window.__minidom.document;
    var c = D.getElementById("c");
    return JSON.stringify({canvas: !!c, state: window.__game.state,
      hud: (D.getElementById("hud-status")||{}).textContent, tick: globalThis.__tdTick});
  })()`);
  console.log("WX:", wxr, wxstate);
  shot = await cmd("Page.captureScreenshot",{format:"png"});
  fs.writeFileSync("game/shots/diag_wx_td.png", Buffer.from(shot.result.data,"base64"));
  console.log("ERRS:", errs.length ? errs.slice(0,3) : "none");
  ws.close(); process.exit(0);
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
