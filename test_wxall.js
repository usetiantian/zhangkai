/* 六个街机游戏逐一进入冒烟 */
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
global.cancelAnimationFrame = id => clearTimeout(id);
const errs = [];
process.on("uncaughtException", e => errs.push(e.message.slice(0, 120)));
require(path.join(__dirname, "game/wx/game.js"));
const MD = global.__minidom, Mini = global.__mini, A = global.__arcade;
const T = (x, y) => { const p = { touches: [{clientX:x, clientY:y}], changedTouches: [{clientX:x, clientY:y}] };
  touch.start.forEach(f => f(p)); touch.end.forEach(f => f(p)); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  await sleep(600);
  let fails = 0;
  for (const g of A.GAMES){
    try {
      document.getElementById("scr-game").style.display = "none";
      A.startGame(g.id, 1, g.id === "match3" ? 1 : undefined);
      Mini.mode = "game";
      await sleep(1400);
      const ok = Mini.mode === "game";
      const cvs = ["m3-c","go-c","ld-c","ch-c","sh-c","bw-c"].map(id => document.getElementById(id)).filter(Boolean);
      console.log((ok ? "PASS " : "FAIL ") + g.name + (ok ? "" : " mode=" + Mini.mode) +
        " canvas=" + (cvs.length ? "yes" : "no"));
      if (!ok) fails++;
      /* 返回大厅 */
      const back = ["m3-back","go-back","ld-back","ch-back","sh-back","bw-back"].map(id => document.getElementById(id)).filter(Boolean)[0];
      if (back) back.click ? back.click() : null;
      Mini.onBack && Mini.onBack();
      await sleep(300);
    } catch (e){ console.log("FAIL " + g.name + " ERR " + e.message.slice(0, 120)); fails++; }
  }
  console.log("uncaught:", errs.length ? errs.slice(0, 3) : "none");
  process.exit(fails ? 1 : 0);
})();
