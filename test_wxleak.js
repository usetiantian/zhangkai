const path = require("path");
const v8 = require("v8");
let snapTaken = false;
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
const rafCount = {}; let rafTotal = 0;
global.requestAnimationFrame = fn => {
  rafTotal++;
  const k = String(fn).replace(/\s+/g, " ").slice(0, 70);
  rafCount[k] = (rafCount[k] || 0) + 1;
  return setTimeout(() => fn(Date.now()), 16);
};
let cvCount = 0;
const origCv = global.wx.createCanvas;
global.wx.createCanvas = function(){ cvCount++; return origCv(); };
setInterval(() => {
  const top = Object.keys(rafCount).sort((a, b) => rafCount[b] - rafCount[a]).slice(0, 3)
    .map(k => rafCount[k] + "x " + k.slice(0, 56));
  console.log("RF rafTotal=" + rafTotal + " canvases=" + cvCount + " | " + top.join(" ;; "));
}, 2000);
process.on("uncaughtException", e => console.log("[uncaught]", e.message, String(e.stack || "").slice(0, 500)));
require(path.join(__dirname, "game/wx/game.js"));
const MD = global.__minidom, Mini = global.__mini;
const T = (x, y) => { const p = { touches: [{clientX:x, clientY:y}], changedTouches: [{clientX:x, clientY:y}] };
  touch.start.forEach(f => f(p)); touch.end.forEach(f => f(p)); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  await sleep(600);
  T(39, 76);  // 进塔防
  await sleep(1200);
  const stats = () => {
    const mu = process.memoryUsage();
    const st = MD.debugStats();
    const G = global.__game;
    console.log("mem=" + Math.round(mu.heapUsed/1048576) + "MB ops=" + st.ops + " hits=" + st.hits +
      " bodyKids=" + global.document.body.children.length + " stoves=" + (G.stoves ? G.stoves.length : "?") +
      " enemies=" + (G.enemies ? G.enemies.length : "?"));
  };
  stats();
  await sleep(3000); stats();
  // 建塔
  const hits = MD.debugHits();
  const c = hits.find(h => h.el.id === "c");
  const pad = global.__LEVELS[0].pads[0];
  T(c.x + (pad[0]+0.5)/20*c.w, c.y + (pad[1]+0.5)/12*c.h);
  console.log("TAP-DONE sync");
  try { v8.writeHeapSnapshot("C:/Users/87999/AppData/Local/Temp/wxA.heapsnapshot"); console.log("SNAP-A"); } catch (e){ console.log("snapA err", e.message); }
  await sleep(1500); stats();
  await sleep(3000); stats();
  await sleep(4000); stats();
  process.exit(0);
})();
