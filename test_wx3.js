/* 逐段加载 wx 包定位挂点 */
const path = require("path"); const fs = require("fs");
function mkCtx(){ const st = {};
  return new Proxy(st, { get(t,k){
    if (k==="measureText") return s=>({width:String(s).length*7});
    if (k==="createLinearGradient"||k==="createRadialGradient"||k==="createPattern") return ()=>({addColorStop(){}});
    if (typeof k==="symbol") return undefined; if (k in t) return t[k]; return function(){};
  }, set(t,k,v){t[k]=v;return true;} }); }
function mkCanvas(){ return { width:300, height:150, style:{}, _ctx:null,
  getContext(){ this._ctx=this._ctx||mkCtx(); return this._ctx; },
  addEventListener(){}, removeEventListener(){}, toDataURL(){return "data:,";} }; }
const storage={};
global.wx={ createCanvas:mkCanvas,
  createImage(){ return { set src(v){ this._s=v; setTimeout(()=>this.onload&&this.onload(),1); }, get src(){return this._s;}, complete:true,width:64,height:64 }; },
  getSystemInfoSync(){ return {windowWidth:390,windowHeight:844,pixelRatio:2}; },
  getStorageSync:k=>storage[k]||{}, setStorageSync:(k,v)=>{storage[k]=v;},
  onTouchStart(){},onTouchMove(){},onTouchEnd(){},onTouchCancel(){},
  onShow(){},onHide(){},getLaunchOptionsSync:()=>({query:{}}),vibrateShort(){},
  createRewardedVideoAd(){return {load(cb){cb&&cb();},show(cb){cb&&cb();},onClose(cb){cb&&cb({isEnded:true});},onError(){}};} };
global.requestAnimationFrame = fn => setTimeout(()=>fn(Date.now()),16);
process.on("uncaughtException", e => console.log("  [uncaught]", e.message));

const SRC = p => fs.readFileSync(path.join(__dirname, "game/src", p), "utf8");
const parts = [
  ["__WX", "var __WX=1;"],
  ["adapter", fs.readFileSync(path.join(__dirname, "game/wx/adapter.js"), "utf8")],
  ["levels", SRC("levels.js")], ["shop", SRC("shop.js")], ["map", SRC("map.js")],
  ["meta", SRC("meta.js")], ["games", SRC("games.js")], ["game", SRC("game.js")],
  ["mini", SRC("mini.js").replace("/[?&]mini=1/.test(location.search)", "true")],
  ["ui", SRC("ui.js")]
];
for (const [name, code] of parts){
  console.log("loading", name, "…");
  const t = Date.now();
  try { (0, eval)(code); } catch (e){ console.log("  ERROR in", name, ":", e.message.slice(0, 300)); break; }
  console.log("  ok", Date.now() - t, "ms");
}
setTimeout(()=>{ console.log("alive; mini:", !!global.__mini, "game:", !!global.__game, "mode:", global.__mini && global.__mini.mode); process.exit(0); }, 3000);
