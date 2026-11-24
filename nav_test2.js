const http = require("http");
function httpGet(path){ return new Promise((res,rej)=>{ http.get({host:"127.0.0.1",port:9555,path},r=>{let d="";r.on("data",c=>d+=c);r.on("end",()=>res(d));}).on("error",rej); }); }
(async()=>{
  const tabs = JSON.parse(await httpGet("/json/list"));
  const page = tabs.find(x=>x.type==="page");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id=0; const pend=new Map(); const errs=[];
  ws.onmessage = async m=>{ let r=m.data; if(typeof r!=="string") r=await r.text(); const o=JSON.parse(r);
    if(o.id&&pend.has(o.id)){pend.get(o.id)(o);pend.delete(o.id);}
    if(o.method==="Runtime.exceptionThrown") errs.push(((o.params.exceptionDetails.exception||{}).description||"").slice(0,200)); };
  await new Promise(r=>ws.onopen=r);
  const cmd=(m,p)=>new Promise(r=>{const i=++id;pend.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:p||{}}));});
  const ev=async(e)=>{const r=await cmd("Runtime.evaluate",{expression:e,returnByValue:true});return r.result.result?r.result.result.value:"EX:"+(r.result.exceptionDetails||{}).text;};
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  await cmd("Page.enable"); await cmd("Runtime.enable");
  await cmd("Page.navigate",{url:"file:///C:/Users/87999/claude-workspace/game/%E6%9E%9C%E5%AD%90.html?nav2="+Date.now()});
  await sleep(7000);
  // 点乐园 tab
  await ev('document.getElementById("btn-arcade").click(); "ok"');
  await sleep(800);
  // 验证 hub 渲染了 6 张卡
  const cards = await ev('(function(){
    var cards = document.querySelectorAll(".hub-card");
    var ids = [];
    for (var i=0;i<cards.length;i++) ids.push(cards[i].getAttribute("data-id"));
    return ids.join(",");
  })()');
  console.log("hub cards:", cards);
  // 验证无特殊TD按钮
  const hasTD = await ev('!!document.getElementById("hub-td")');
  console.log("hub-td special:", hasTD);
  // 点 TD 卡
  await ev('(function(){
    var cards = document.querySelectorAll(".hub-card");
    for (var i=0;i<cards.length;i++)
      if (cards[i].getAttribute("data-id") === "td"){ cards[i].click(); return "clicked"; }
    return "not-found";
  })()');
  await sleep(800);
  // 验证进了关卡页
  const scr = await ev('(function(){
    var ids = ["scr-map","scr-arcade","scr-game"];
    for (var i=0;i<ids.length;i++){
      var el = document.getElementById(ids[i]);
      if (el && el.className.indexOf("on")>=0) return ids[i];
    }
    return "none";
  })()');
  console.log("TD click → screen:", scr);
  console.log("errs:", errs.length ? errs.slice(0,2) : "none");
  ws.close(); process.exit(0);
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
