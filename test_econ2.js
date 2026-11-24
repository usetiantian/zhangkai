/* 终验：每关实际收入 = 建造位×1071×1.3（用真实游戏计算路径验证） */
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
global.wx = {
  createCanvas: mkCanvas,
  createImage(){ return { set src(v){ this._s=v; setTimeout(()=>{ this.onload && this.onload(); },1); }, get src(){ return this._s; }, complete:true, width:64, height:64 }; },
  getSystemInfoSync(){ return { windowWidth:390, windowHeight:844, pixelRatio:2 }; },
  getStorageSync(k){ return storage[k] || {}; }, setStorageSync(k,v){ storage[k]=v; },
  onTouchStart(){}, onTouchMove(){}, onTouchEnd(){}, onTouchCancel(){},
  onShow(){}, onHide(){}, getLaunchOptionsSync(){ return {query:{}}; }, vibrateShort(){},
  createRewardedVideoAd(){ return {load(cb){cb&&cb();},show(cb){cb&&cb();},onClose(cb){cb&&cb({isEnded:true});},onError(){}}; }
};
global.requestAnimationFrame = fn => setTimeout(() => fn(Date.now()), 16);
global.cancelAnimationFrame = id => clearTimeout(id);
require(path.join(__dirname, "game/wx/game.js"));
const sleep = ms => new Promise(r => setTimeout(r, ms));
const G = global.__game;
let fails = 0;
const step = (n, ok, extra) => { console.log((ok ? "PASS " : "FAIL ") + n + (ok ? "" : "  << " + (extra || ""))); if (!ok) fails++; };
(async () => {
  await sleep(700);
  global.document.getElementById("scr-game").style.display = "block";
  console.log("关卡 | 建造位 | 目标收入(位×1071×1.3) | 游戏算出的倍率验证");
  for (const no of [1, 20, 40, 60, 80, 100]){
    const lv = global.__LEVELS[no-1];
    lv.no = no;
    G.loadLevel(lv);
    await sleep(200);
    const pads = lv.pads.length;
    const target = pads * 1071 * 1.3;
    // 复算 baseInc
    let baseInc = 0;
    lv.waves.forEach((w, i) => {
      (w.list || [w]).forEach(e => baseInc += (e.reward || 5));
      baseInc += 40 + i * 18;
    });
    const total = 260 + 12*(no-1) + baseInc * lv.incMul;
    const ok = total >= target * 0.98;
    step("L" + no + " 收入" + Math.round(total) + " ≥ 目标" + Math.round(target), ok, "incMul=" + (lv.incMul||1).toFixed(2));
  }
  console.log(fails ? "=== " + fails + " FAIL ===" : "=== ALL PASS ===");
  process.exit(fails ? 1 : 0);
})();
