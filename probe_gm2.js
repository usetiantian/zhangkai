const http = require("http");
function httpGet(path){ return new Promise((res,rej)=>{ http.get({host:"127.0.0.1",port:9555,path},r=>{let d="";r.on("data",c=>d+=c);r.on("end",()=>res(d));}).on("error",rej); }); }
(async()=>{
  const tabs = JSON.parse(await httpGet("/json/list"));
  const page = tabs.find(x=>x.type==="page");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id=0; const pend=new Map(); const errs=[];
  ws.onmessage = async m=>{ let r=m.data; if(typeof r!=="string") r=await r.text(); const o=JSON.parse(r);
    if(o.id&&pend.has(o.id)){pend.get(o.id)(o);pend.delete(o.id);}
    if(o.method==="Runtime.exceptionThrown") errs.push(((o.params.exceptionDetails.exception||{}).description||"").slice(0,250)); };
  await new Promise(r=>ws.onopen=r);
  const cmd=(m,p)=>new Promise(r=>{const i=++id;pend.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});
  const ev=async(e)=>{const r=await cmd("Runtime.evaluate",{expression:e,returnByValue:true});
    if (r.result.exceptionDetails) return "EX: " + ((r.result.exceptionDetails.exception||{}).description||r.result.exceptionDetails.text).slice(0,220);
    return JSON.stringify(r.result.result.value);};
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  await cmd("Page.enable"); await cmd("Runtime.enable");
  await cmd("Page.navigate",{url:"file:///C:/Users/87999/claude-workspace/game/%E6%9E%9C%E5%AD%90.html?p2="+Date.now()});
  await sleep(7000);
  console.log("arc:", await ev("typeof __arcade"));
  console.log("games:", await ev("__arcade.GAMES.length"));
  console.log("startGame type:", await ev("typeof __arcade.startGame"));
  console.log("uiGomoku:", await ev("try { __arcade.startGame('gomoku', 1); 'ran'; } catch(e){ 'THROW: ' + e.message + ' | ' + (e.stack||'').split(String.fromCharCode(10))[1]; }"));
  await sleep(1200);
  console.log("gm-c:", await ev("!!document.getElementById('gm-c')"));
  console.log("root html len:", await ev("(document.getElementById('arcade-root')||{innerHTML:''}).innerHTML.length"));
  console.log("errs:", errs.length ? errs.slice(0,2).join(" || ") : "none");
  ws.close(); process.exit(0);
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
