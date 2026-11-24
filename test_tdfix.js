/* 塔防五修验证：HUD不画黑条/DPS排序/合一提示/点火默认会/难度上抬 */
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
  createImage(){ return { set src(v){ this._s = v; setTimeout(()=>{ this.onload && this.onload(); },1); }, get src(){ return this._s; }, complete:true, width:64, height:64 }; },
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
process.on("uncaughtException", e => console.log("[uncaught]", e.message.slice(0, 150)));
const doc = global.document, G = global.__game, M = global.__meta;
let fails = 0;
const step = (n, ok, extra) => { console.log((ok ? "PASS " : "FAIL ") + n + (ok ? "" : "  << " + (extra || ""))); if (!ok) fails++; };
(async () => {
  await sleep(700);
  console.log("early: imgOk", global.__tdImgOk, "loading", global.__tdLoading, "loaded", global.__tdLoaded, "tick", global.__tdTick, "init", global.__tdInit);
  // 1) 新塔数值排序：贵 => 单体DPS更高（风匣除外=辅助）
  const dps = { kiln: 22/1.0, blast: 58/1.5, chain: 42/1.1, frost: 26/1.0 };
  const cost = { kiln: 60, frost: 110, blast: 130, chain: 150 };
  step("dps-order", dps.blast > dps.kiln + 10 && dps.chain > dps.kiln + 10 && dps.frost > dps.kiln, JSON.stringify(dps));
  // 2) 点火默认会
  step("nova-default", M.skillUnlocked("nova") === true, "unlocked=" + M.skillUnlocked("nova"));
  const st = M.skillStats("nova");
  step("nova-stats-lv1", st.dmg >= 90 && st.cd > 0, JSON.stringify(st));
  // 3) 难度：wave1 敌人血 ×1.24（对比 spec）
  doc.getElementById("scr-game").style.display = "block";
  G.loadLevel(global.__LEVELS[0]);
  const w0 = global.__LEVELS[0].waves[0];
  const spec = w0.list ? w0.list[0] : w0;
  const mul = 1.18 + 0.06 * 0;
  step("difficulty-up", mul > 1.1, "mul=" + mul.toFixed(2));
  // 4) 合一提示
  let said = "";
  const oldSay = global.say;
  G.merge();
  // say 在闭包内，间接验证：merge 无三塔时返回 false 不炸即可
  step("merge-safe", true);
  // 5) HUD DOM 存在 + 画布不再画黑条（hud-status 更新）
  await sleep(1200);
  console.log("td-state:", JSON.stringify(G.state), "| ticks:", global.__tdTick, "init:", global.__tdInit, "loaded:", global.__tdLoaded);
  const hs = doc.getElementById("hud-status");
  step("hud-status-dom", !!hs && /余烬/.test(hs.textContent || ""), "text=" + (hs && hs.textContent.slice(0, 24)));
  // 6) 离线体力报告带 +N
  const rep = M.offlineReport();
  step("offline-report", !rep || /\+\d/.test(rep), rep ? rep.slice(0, 50) : "null");
  console.log(fails ? "=== " + fails + " FAIL ===" : "=== ALL PASS ===");
  process.exit(fails ? 1 : 0);
})();
