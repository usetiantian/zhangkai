/* 抽卡：清空池子后继续抽 → 重复转资源不空手 */
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
const M = global.__meta;
let fails = 0;
const step = (n, ok, extra) => { console.log((ok ? "PASS " : "FAIL ") + n + (ok ? "" : "  << " + (extra || ""))); if (!ok) fails++; };
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  await sleep(600);
  // 抽到池子清空
  var allGot = [], dupCount = 0;
  for (var round = 0; round < 10; round++){
    var got = M.gacha(10);
    if (!got.length){ step("round" + round + "-empty", false, "gacha returned 0 items"); break; }
    for (var i = 0; i < got.length; i++){
      allGot.push(got[i]);
      if (got[i].dupMsg) dupCount++;
    }
  }
  step("gacha-never-empty", allGot.length >= 50, "total=" + allGot.length);
  step("dups-get-resources", dupCount > 0, "dupCount=" + dupCount);
  step("dup-msg-format", allGot.some(g => g.dupMsg && /灵果\+\d+ 灵晶\+\d+/.test(g.dupMsg)),
       allGot.filter(g=>g.dupMsg).map(g=>g.dupMsg).slice(0,3).join(" | "));
  // 确认资源确实加了
  step("coins-increased", M.save.coins > 100000, "coins=" + M.save.coins);
  step("gems-increased", M.save.gems > 100000, "gems=" + M.save.gems);
  console.log(fails ? "=== " + fails + " FAIL ===" : "=== ALL PASS ===");
  process.exit(fails ? 1 : 0);
})();
