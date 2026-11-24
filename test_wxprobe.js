const path = require("path");
function mkCtx(){ const st = {};
  return new Proxy(st, { get(t,k){
    if (k==="measureText") return s=>({width:String(s).length*7});
    if (k==="createLinearGradient"||k==="createRadialGradient"||k==="createPattern") return ()=>({addColorStop(){}});
    if (typeof k==="symbol") return undefined; if (k in t) return t[k]; return function(){};
  }, set(t,k,v){t[k]=v;return true;} }); }
function mkCanvas(){ return { width:300, height:150, style:{}, _ctx:null,
  getContext(){ this._ctx=this._ctx||mkCtx(); return this._ctx; },
  addEventListener(){}, removeEventListener(){}, toDataURL(){return "data:,";} }; }
const storage = {};
const touch = { start: [], move: [], end: [], cancel: [] };
global.wx = {
  createCanvas: mkCanvas,
  createImage(){ return { set src(v){ this._s=v; setTimeout(()=>this.onload&&this.onload(),1); }, get src(){ return this._s; }, complete: true, width: 64, height: 64 }; },
  getSystemInfoSync(){ return { windowWidth: 390, windowHeight: 844, pixelRatio: 2 }; },
  getStorageSync(k){ return storage[k] || {}; }, setStorageSync(k, v){ storage[k] = v; },
  onTouchStart(f){ touch.start.push(f); }, onTouchMove(f){ touch.move.push(f); },
  onTouchEnd(f){ touch.end.push(f); }, onTouchCancel(f){ touch.cancel.push(f); },
  onShow(){}, onHide(){}, getLaunchOptionsSync(){ return { query: {} }; }, vibrateShort(){},
  createRewardedVideoAd(){ return { load(cb){cb&&cb();}, show(cb){cb&&cb();}, onClose(cb){cb&&cb({isEnded:true});}, onError(){} }; }
};
global.requestAnimationFrame = fn => setTimeout(() => fn(Date.now()), 16);
process.on("uncaughtException", e => console.log("[uncaught]", e.message.slice(0, 300)));
require(path.join(__dirname, "game/wx/game.js"));
setTimeout(() => {
  const Mini = global.__mini;
  console.log("handlers:", touch.start.length, touch.move.length, touch.end.length);
  console.log("screen:", Mini.screen, "mode:", Mini.mode, "toast:", Mini.toast);
  const p = (x, y) => { const e = { touches: [{clientX:x, clientY:y}], changedTouches: [{clientX:x, clientY:y}] };
    touch.start.forEach(f => f(e)); touch.end.forEach(f => f(e)); };
  p(39, 76);
  setTimeout(() => {
    console.log("after tap: mode=", Mini.mode, "toast=", Mini.toast, "lastGame=", Mini.lastGame);
    try { global.__ui.startLevel(1); console.log("direct startLevel ok, mode=", Mini.mode); }
    catch (e){ console.log("direct startLevel ERR:", e.message.slice(0, 300)); }
    setTimeout(() => {
      console.log("final mode=", Mini.mode, "hud=", global.document.getElementById("hud-level").textContent,
        "mini.mode=", Mini.mode);
      const hits = global.__minidom.debugHits();
      console.log("hits:", hits.length, hits.slice(0, 6).map(h => (h.el.id || h.el.className || h.el.tagName) + "@" + Math.round(h.x) + "," + Math.round(h.y)).join(" | "));
      process.exit(0);
    }, 800);
  }, 300);
}, 800);
