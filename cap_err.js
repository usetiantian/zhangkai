const http = require("http");
function httpGet(path){ return new Promise((res,rej)=>{ http.get({host:"127.0.0.1",port:9555,path},r=>{let d="";r.on("data",c=>d+=c);r.on("end",()=>res(d));}).on("error",rej); }); }
(async()=>{
  const tabs = JSON.parse(await httpGet("/json/list"));
  const page = tabs.find(x=>x.type==="page");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id=0; const pend=new Map(); const errs=[];
  ws.onmessage = async m=>{ let r=m.data; if(typeof r!=="string") r=await r.text(); const o=JSON.parse(r);
    if(o.id&&pend.has(o.id)){pend.get(o.id)(o);pend.delete(o.id);}
    if(o.method==="Runtime.consoleAPICalled" && (o.params.type==="error"||o.params.type==="warning"))
      errs.push(o.params.type + ": " + o.params.args.map(a=>a.value||a.description||a.type).join(" ").slice(0,200));
    if(o.method==="Runtime.exceptionThrown") errs.push("EX: " + ((o.params.exceptionDetails.exception||{}).description||"").slice(0,900)); };
  await new Promise(r=>ws.onopen=r);
  const cmd=(m,p)=>new Promise(r=>{const i=++id;pend.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});
  const ev=async(e)=>{const r=await cmd("Runtime.evaluate",{expression:e,returnByValue:true});return r.result.result?r.result.result.value:"EX";};
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  await cmd("Page.enable"); await cmd("Runtime.enable");
  await cmd("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:2,mobile:true});
  await cmd("Page.navigate",{url:"file:///C:/Users/87999/claude-workspace/game/wx/preview.html?e="+Date.now()});
  await sleep(5000);
  await ev(`window.__arcade.loadArcImgs(); (function(){var sg=window.__minidom.document.getElementById("scr-game"); if(sg) sg.style.display="none"; return 1;})()`);
  await sleep(1500);
  await ev(`window.__arcade.startGame("brawl", 1); window.__mini.mode="game"; "go"`);
  await sleep(4000);
  console.log("ERRORS:", errs.length ? errs.slice(0,6).join("\n---\n") : "none");
  console.log("bwErr:", await ev("window.__bwErr || 'none'"));
  console.log("IMG2:", await ev("Object.keys(window.__arcade._IMG2||{}).length"));
  console.log("groundArt:", await ev("(function(){var g=window.__bwG; return g?'g-ok':'no-g'})()"));
  ws.close(); process.exit(0);
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
