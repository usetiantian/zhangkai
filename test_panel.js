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
const doc = global.document;
const variants = [
  ["title", ['<div class="p-title">土炉　Lv1</div>']],
  ["row", ['<div class="p-row"><span>伤害</span><span>26</span></div>']],
  ["row-empty", ['<div class="p-row"><span>升级</span><span></span></div>']],
  ["row-style", ['<div class="p-row" style="margin-top:6px;border-top:1px solid #443a2a;padding-top:6px"><span>花费</span><span class="p-up">90 余烬</span></div>']],
  ["act", ['<div class="p-act"><button id="p-up">升级</button><button id="p-sell" class="sell">拆除 +30</button></div>']],
  ["row-3span", ['<div class="p-row"><span>a</span><span>b</span><span>c</span></div>']]
];
const which = process.argv[2] || "title";
const h = variants.find(v => v[0] === which)[1];
const panel = doc.getElementById("panel");
console.log("panel:", !!panel);
panel.innerHTML = h.join("");
panel.className = "show";
console.log("children:", panel.children.length);
const t0 = Date.now();
const st = MD.debugStats();
console.log("layout ms:", Date.now() - t0, JSON.stringify(st));
console.log("DONE");
process.exit(0);
