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
    if(o.method==="Runtime.exceptionThrown") errs.push(((o.params.exceptionDetails.exception||{}).description||"").slice(0,240)); };
  await new Promise(r=>ws.onopen=r);
  const cmd=(m,p)=>new Promise(r=>{const i=++id;pend.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});
  const ev=async(e)=>{const r=await cmd("Runtime.evaluate",{expression:e,returnByValue:true});return r.result.result?r.result.result.value:"EX:"+(r.result.exceptionDetails||{}).text;};
  const mouse=(t,x,y)=>cmd("Input.dispatchMouseEvent",{type:t,x,y,button:"left",clickCount:t==="mousePressed"?1:0});
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  await cmd("Page.enable"); await cmd("Runtime.enable");
  await cmd("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:2,mobile:true});

  // ===== H5 真实点击路径 =====
  await cmd("Page.navigate",{url:"file:///C:/Users/87999/claude-workspace/game/%E6%9E%9C%E5%AD%90.html?c="+Date.now()});
  await sleep(7500);
  // 等地图渲染完，找第1关格子中心（H5：lv-cell 第1个）
  const cell = await ev(`(function(){
    var cells = document.querySelectorAll(".lv-cell");
    if (!cells.length) return "no-cells";
    var r = cells[0].getBoundingClientRect();
    return [Math.round(r.left+r.width/2), Math.round(r.top+r.height/2)].join(",");
  })()`);
  console.log("H5 level1 cell:", cell);
  if (cell !== "no-cells"){
    const [x, y] = cell.split(",").map(Number);
    await mouse("mousePressed", x, y); await mouse("mouseReleased", x, y);
    await sleep(1800);
    console.log("H5 after click:", await ev(`(function(){
      var sg = document.getElementById("scr-game");
      var on = sg && sg.className.indexOf("on") >= 0;
      var c = document.getElementById("c");
      return JSON.stringify({scrGameOn: on, canvasShown: c ? Math.round(c.getBoundingClientRect().width) : 0,
        hud: (document.getElementById("hud-level")||{}).textContent, state: window.__game.state.waves});
    })()`));
    const shot = await cmd("Page.captureScreenshot",{format:"png"});
    fs.writeFileSync("game/shots/diag_click_h5.png", Buffer.from(shot.result.data,"base64"));
  }
  console.log("ERRS:", errs.length ? errs.slice(0,2) : "none");
  ws.close(); process.exit(0);
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
