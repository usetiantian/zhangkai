/* 飞行棋：H5 双人入口 + wx pickMode 双人开局 */
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
require(path.join(__dirname, "game/wx/game.js"));
const MD = global.__minidom, Mini = global.__mini, A = global.__arcade;
const T = (x, y) => { const p = { touches: [{clientX:x, clientY:y}], changedTouches: [{clientX:x, clientY:y}] };
  touch.start.forEach(f => f(p)); touch.end.forEach(f => f(p)); };
const hit = sel => MD.debugHits().find(h => h.el.id === sel || (" " + h.el.className + " ").indexOf(" " + sel + " ") >= 0);
const sleep = ms => new Promise(r => setTimeout(r, ms));
let fails = 0;
const step = (n, ok, extra) => { console.log((ok ? "PASS " : "FAIL ") + n + (ok ? "" : "  << " + (extra || ""))); if (!ok) fails++; };
(async () => {
  await sleep(700);
  // 乐园 tab → 飞行棋卡（GAMES[1] = row0 col1 → x=10+190+90=290, y=52+46=98）
  T(390 / 7 * 3.5, 844 - 28); await sleep(500);
  T(290, 98); await sleep(1200);
  step("ludo-pickmode", Mini.mode === "game" && !!document.getElementById("pm-2"),
       "mode=" + Mini.mode + " pm2=" + !!document.getElementById("pm-2"));
  const pm2 = hit("pm-2");
  if (pm2){ T(pm2.x + pm2.w / 2, pm2.y + pm2.h / 2); await sleep(1500); }
  const t0 = document.getElementById("ld-t0");
  step("ludo-duo-started", !!t0 && /玩家1/.test(t0.textContent), "t0=" + (t0 && t0.textContent));
  const cvs = ["ld-c","ludo-c"].map(i => document.getElementById(i)).filter(Boolean)[0];
  step("ludo-canvas", !!cvs, "none");
  const back = document.getElementById("ld-back");
  if (back){ const bh2 = hit("ld-back"); if (bh2){ T(bh2.x + bh2.w / 2, bh2.y + bh2.h / 2); await sleep(700); } }
  step("back-hub", Mini.mode === "shell", "mode=" + Mini.mode);
  console.log(fails ? "=== " + fails + " FAIL ===" : "=== ALL PASS ===");
  process.exit(fails ? 1 : 0);
})();
