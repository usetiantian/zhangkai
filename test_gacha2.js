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
(async () => {
  await new Promise(r => setTimeout(r, 600));
  let fails = 0;
  const step = (n, ok, extra) => { console.log((ok?"PASS ":"FAIL ")+n+(ok?"":" << "+(extra||""))); if(!ok) fails++; };

  // 模拟100次十连（1000抽），统计回收率
  let skinCount = 0, resCount = 0, coinsBack = 0, gemsBack = 0;
  const gemsBefore = M.save.gems;
  for (let round = 0; round < 100; round++){
    const got = M.gacha(10);
    for (const g of got){
      if (g.kind === "res"){
        resCount++;
        if (g.type === "coins") coinsBack += g.amount;
        else gemsBack += g.amount;
      } else {
        skinCount++;
        if (g.dupMsg){
          const m = g.dupMsg.match(/灵果\+(\d+) 灵晶\+(\d+)/);
          if (m){ coinsBack += +m[1]; gemsBack += +m[2]; }
        }
      }
    }
  }
  const total = skinCount + resCount;
  console.log(`1000抽结果: 皮肤${skinCount} 资源${resCount} (${(resCount/total*100).toFixed(1)}%资源)`);
  console.log(`回收: 灵果+${coinsBack} 灵晶+${gemsBack}`);
  console.log(`十连成本: 270玉 × 100 = 27000玉, 回收灵晶: ${gemsBack} (${(gemsBack/27000*100).toFixed(1)}%返玉率)`);
  step("资源占比>55%", resCount/total > 0.55, `${(resCount/total*100).toFixed(1)}%`);
  step("有灵晶回收", gemsBack > 0, gemsBack + "灵晶");
  step("有灵果回收", coinsBack > 0, coinsBack + "灵果");
  step("从不空手", total >= 900, `${total}结果`);
  console.log(fails ? "=== FAIL ===" : "=== ALL PASS ===");
  process.exit(fails ? 1 : 0);
})();
