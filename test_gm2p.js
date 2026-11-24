/* 五子棋双人入口（wx 包） */
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
const MD = global.__minidom, Mini = global.__mini;
const T = (x, y) => { const p = { touches: [{clientX:x, clientY:y}], changedTouches: [{clientX:x, clientY:y}] };
  touch.start.forEach(f => f(p)); touch.end.forEach(f => f(p)); };
const hit = sel => MD.debugHits().find(h => h.el.id === sel || (" " + h.el.className + " ").indexOf(" " + sel + " ") >= 0);
const sleep = ms => new Promise(r => setTimeout(r, ms));
let fails = 0;
const step = (n, ok, extra) => { console.log((ok ? "PASS " : "FAIL ") + n + (ok ? "" : "  << " + (extra || ""))); if (!ok) fails++; };
(async () => {
  await sleep(700);
  // 乐园 → 五子棋卡（GAMES[0] row0 col0 → x=100, y=98）
  T(390 / 7 * 3.5, 844 - 28); await sleep(500);
  T(100, 98); await sleep(1200);
  step("gomoku-pickmode", Mini.mode === "game" && !!document.getElementById("pm-2"),
       "mode=" + Mini.mode + " pm2=" + !!document.getElementById("pm-2"));
  // 单人先测
  let pm1 = hit("pm-1");
  if (pm1){ T(pm1.x + pm1.w / 2, pm1.y + pm1.h / 2); await sleep(1200); }
  const t1 = document.getElementById("gm-t1");
  step("solo-started", !!t1 && /黑\(你\)/.test(t1.textContent), "t1=" + (t1 && t1.textContent));
  // 退出再进双人
  let gb = hit("gm-back");
  if (gb){ T(gb.x + gb.w / 2, gb.y + gb.h / 2); await sleep(800); }
  T(100, 98); await sleep(1000);
  const pm2 = hit("pm-2");
  if (pm2){ T(pm2.x + pm2.w / 2, pm2.y + pm2.h / 2); await sleep(1200); }
  const t2 = document.getElementById("gm-t1");
  step("duo-started", !!t2 && /玩家1/.test(t2.textContent), "t2=" + (t2 && t2.textContent));
  console.log(fails ? "=== " + fails + " FAIL ===" : "=== ALL PASS ===");
  process.exit(fails ? 1 : 0);
})();
