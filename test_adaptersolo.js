function mkCtx(){ const st = {};
  return new Proxy(st, { get(t,k){
    if (k==="measureText") return s=>({width:String(s).length*7});
    if (k==="createLinearGradient"||k==="createRadialGradient"||k==="createPattern") return ()=>({addColorStop(){}});
    if (typeof k==="symbol") return undefined; if (k in t) return t[k]; return function(){};
  }, set(t,k,v){t[k]=v;return true;} }); }
function mkCanvas(){ return { width:300, height:150, style:{}, _ctx:null,
  getContext(){ this._ctx=this._ctx||mkCtx(); return this._ctx; },
  addEventListener(){}, removeEventListener(){}, toDataURL(){return "data:,";} }; }
global.wx = {
  createCanvas: mkCanvas,
  createImage(){ return { set src(v){}, get src(){return "";}, complete:true, width:64, height:64 }; },
  getSystemInfoSync(){ return {windowWidth:390, windowHeight:844, pixelRatio:2}; },
  getStorageSync(){ return {}; }, setStorageSync(){},
  onTouchStart(){}, onTouchMove(){}, onTouchEnd(){}, onTouchCancel(){},
  onShow(){}, onHide(){}, getLaunchOptionsSync(){ return {query:{}}; }, vibrateShort(){},
  createRewardedVideoAd(){ return {load(cb){cb&&cb();},show(cb){cb&&cb();},onClose(cb){cb&&cb({isEnded:true});},onError(){}}; }
};
require("./game/wx/adapter.js");
const MD = global.__minidom;
const body = MD.body;
global.__MDTRACE = [];
const t = (html) => { global.__MDTRACE = []; body.innerHTML = html; const st = MD.debugStats(); console.log("STATS:", JSON.stringify(st), "| TRACE:", global.__MDTRACE.join(" > ")); };
t('<div id="t1"><canvas id="c" width="480" height="480"></canvas></div>');
t('<div id="t1"><div id="bar" class="arc-bar"><span class="who">A</span><button class="ctl" id="b1">退出</button></div></div>');
t('<div id="t1"><div class="arc-tip">提示文字</div></div>');
t('<div id="t1"><div id="bar" class="arc-bar"><span class="who">A</span><button class="ctl" id="b1">退出</button></div><canvas id="c" width="480" height="480"></canvas><div class="arc-tip">提示文字</div></div>');
const hits = MD.debugHits();
console.log('final HITS:', hits.map(h => (h.el.id||h.el.className)).join(' | '));
