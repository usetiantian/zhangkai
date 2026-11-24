/* 精灵心情系统：wx包 tap精灵→选心情→回应 */
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
  getSystemInfoSync(){ return { windowWidth:390, windowHeight:844, pixelRatio:2 }; },
  getStorageSync(k){ return storage[k] || {}; }, setStorageSync(k,v){ storage[k]=v; },
  onTouchStart(f){ touch.start.push(f); }, onTouchMove(f){ touch.move.push(f); },
  onTouchEnd(f){ touch.end.push(f); }, onTouchCancel(f){ touch.cancel.push(f); },
  onShow(){}, onHide(){}, getLaunchOptionsSync(){ return {query:{}}; }, vibrateShort(){},
  createRewardedVideoAd(){ return {load(cb){cb&&cb();},show(cb){cb&&cb();},onClose(cb){cb&&cb({isEnded:true});},onError(){}}; }
};
global.requestAnimationFrame = fn => setTimeout(() => fn(Date.now()), 16);
global.cancelAnimationFrame = id => clearTimeout(id);
require(path.join(__dirname, "game/wx/game.js"));
const Mini = global.__mini, M = global.__meta;
const T = (x, y) => { const p = { touches: [{clientX:x, clientY:y}], changedTouches: [{clientX:x, clientY:y}] };
  touch.start.forEach(f => f(p)); touch.end.forEach(f => f(p)); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
let fails = 0;
const step = (n, ok, extra) => { console.log((ok ? "PASS " : "FAIL ") + n + (ok ? "" : "  << " + (extra || ""))); if (!ok) fails++; };
(async () => {
  await sleep(800);
  // 点精灵（右下角 W-44+20, H-56-56+20 = 366, 732）
  T(366, 732); await sleep(300);
  step("mood-panel-open", Mini._moodBoxes && Mini._moodBoxes.length === 4, "boxes=" + (Mini._moodBoxes && Mini._moodBoxes.length));
  // 点“难过”
  const sad = Mini._moodBoxes[3];
  Mini.say(""); /* 清掉旧toast */
  T(sad.x + sad.w / 2, sad.y + sad.h / 2); await sleep(400);
  step("mood-sad-reply", typeof Mini.toast === "string" && Mini.toast.length > 4, "toast=" + Mini.toast);
  // 直调 fairyMood 各心情
  const rs = ["happy", "ok", "tired", "sad"].map(m => M.fairyMood(m));
  step("all-moods-reply", rs.every(r => r && r.length > 4), rs.map(r => r && r.slice(0, 8)).join(" / "));
  // 连败安慰：直接调 fairySay("soloLose") 3 次（无冷却强制? soloLose 非强制，先清冷却）
  global.__fairyLastT = 0;
  const r1 = M.fairySay("soloLose");
  global.__fairyLastT = 0;
  const r2 = M.fairySay("soloLose");
  global.__fairyLastT = 0;
  const r3 = M.fairySay("soloLose");
  step("lose-comfort", r3 && /运气在攒|铺路|抱抱自己/.test(r3), "第3次=" + r3);
  console.log(fails ? "=== " + fails + " FAIL ===" : "=== ALL PASS ===");
  process.exit(fails ? 1 : 0);
})();
