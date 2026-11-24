/* 合一最终规则：三座满级(Lv4)同类 → 觉醒Lv5(×3.4) */
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
  onShow(){}, onHide:{}, getLaunchOptionsSync(){ return {query:{}}; }, vibrateShort(){},
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
  G.loadLevel(global.__LEVELS[0]);
  await sleep(400);
  const pads = global.__LEVELS[0].pads;
  G.build(pads[0][0], pads[0][1], "kiln");
  G.build(pads[1][0], pads[1][1], "kiln");
  G.build(pads[2][0], pads[2][1], "kiln");
  await sleep(300);
  // 1) 未满级 → 不可合一
  step("no-merge-unmaxed", G.merge() === false && G.stoves.length === 3);
  // 2) 两座满级 + 一座Lv3 → 仍不可
  G.stoves[0].lv = 4; G.stoves[1].lv = 4; G.stoves[2].lv = 3;
  step("no-merge-mixed", G.merge() === false && G.stoves.length === 3);
  // 3) 三座满级 → 觉醒 Lv5
  G.stoves[2].lv = 4;
  const ok = G.merge();
  step("merge-3max", ok === true);
  step("awaken-lv5", G.stoves.length === 1 && G.stoves[0].lv === 5, "stoves=" + G.stoves.length + " lv=" + (G.stoves[0] && G.stoves[0].lv));
  const kiln5 = Math.round(22 * 3.4);
  step("lv5-dmg", G.stoves[0].dmg === kiln5, "dmg=" + G.stoves[0].dmg + " 期望" + kiln5);
  // 4) Lv5 不能再普通升级（tryBuild 升级路径）
  G.stoves[0].lv = 5;
  const embersBefore = global.__game.state.embers;
  G.build(pads[0][0], pads[0][1], "kiln");
  step("lv5-no-upgrade", G.stoves[0].lv === 5);
  // 5) 再合一（已无三座满级）→ 安全失败
  step("merge-after-safe", G.merge() === false);
  console.log(fails ? "=== " + fails + " FAIL ===" : "=== ALL PASS ===");
  process.exit(fails ? 1 : 0);
})();
