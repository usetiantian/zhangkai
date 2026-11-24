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
  const ev=async(e)=>{const r=await cmd("Runtime.evaluate",{expression:e,returnByValue:true});return r.result.result?r.result.result.value:"EX:"+(r.result.exceptionDetails||{}).text;};
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  await cmd("Page.enable"); await cmd("Runtime.enable");
  await cmd("Page.navigate",{url:"file:///C:/Users/87999/claude-workspace/game/%E6%9E%9C%E5%AD%90.html?nav="+Date.now()});
  await sleep(7000);
  // 依次点5个tab，验证屏幕切换
  const tabs5 = ["btn-arcade","btn-shop","btn-farm","btn-house","btn-codex"];
  for (const t of tabs5){
    await ev(`document.getElementById("${t}").click(); "clicked"`);
    await sleep(500);
    const scr = await ev(`(function(){
      var on = "";
      var ids = ["scr-map","scr-game","scr-shop","scr-grow","scr-codex","scr-farm","scr-arcade","scr-house"];
      for (var i=0;i<ids.length;i++){
        var el = document.getElementById(ids[i]);
        if (el && el.className.indexOf("on")>=0) on = ids[i];
      }
      return on;
    })()`);
    console.log(t, "→", scr);
  }
  ws.close(); process.exit(0);
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
