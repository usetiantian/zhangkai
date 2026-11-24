/* 成语接龙 v2：谐音/同字判定、出题四选一、成语卡、胜负 */
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
const A = global.__arcade, Mini = global.__mini;
const sleep = ms => new Promise(r => setTimeout(r, ms));
let fails = 0;
const step = (n, ok, extra) => { console.log((ok ? "PASS " : "FAIL ") + n + (ok ? "" : "  << " + (extra || ""))); if (!ok) fails++; };
(async () => {
  await sleep(700);
  // 1) 词库加载
  step("bank-311", Object.keys(window.__IDIOM2).length >= 300, "n=" + Object.keys(window.__IDIOM2).length);
  // 2) 谐音/同字判定（用词库内真实对）
  //   一鼓作气(qì) → 气吞山河 同字
  const c = new A.Chenglong();
  c.start();
  c.last = "一鼓作气";
  step("match-same-char", chainOK(c, "气吞山河") === "同字");
  //   水滴石穿(chuān) → 川流不息? 不在库——找一个谐音对：穿(chuan)→ 传? 检验函数式：临时 last=水滴石穿, 找库中以 chuān/chuán 开头
  var L = Object.keys(window.__IDIOM2);
  var homo = null;
  outer:
  for (var a = 0; a < L.length; a++){
    for (var b = 0; b < L.length; b++){
      if (a !== b && chainMatchGlobal(L[a], L[b]) === "谐音"){ homo = L[a] + "→" + L[b]; break outer; }
    }
  }
  step("homophone-exists", !!homo, homo || "全库无谐音对");
  // 3) 不匹配拒绝
  c.last = "一鼓作气";
  step("reject-wrong", chainOK(c, "画蛇添足") === null);
  // 4) 游戏流程：进游戏 → 出题四选一
  A.startGame("chain", 1);
  Mini.mode = "game";
  await sleep(1000);
  const doc = global.__minidom.document;
  const opts = doc.querySelectorAll(".ch-opt");
  const head = doc.querySelector(".ch-head");
  step("quiz-render", opts.length === 4 && head && /【..□□】/.test(head.textContent.replace(/\s/g, "")),
       "opts=" + opts.length + " head=" + (head && head.textContent));
  const card = doc.querySelector(".ch-story");
  step("story-card", !!card && card.textContent.length > 10);
  // 5) 点对选项 → 链增长
  const before = doc.getElementById("ch-n").textContent;
  const gHook = A._chG;
  // 找到正确项：题目闭包不可见——逐个点，命中即链长+1
  var okClicked = false;
  for (var k = 0; k < opts.length; k++){
    if (doc.getElementById("ch-n").textContent !== before) break;
    global.__minidom.debugHits();
    var h = null;
    var hits = global.__minidom.debugHits().filter(function(x){ return x.el.className && x.el.className.indexOf("ch-opt") >= 0; });
    if (hits.length){ var hh = hits[Math.min(k, hits.length-1)]; global.__minidom.dispatch("click", hh.x + hh.w/2, hh.y + hh.h/2); }
    await sleep(1500);
  }
  step("answer-advances", doc.getElementById("ch-n").textContent !== before,
       "n=" + before + "→" + doc.getElementById("ch-n").textContent);
  console.log(fails ? "=== " + fails + " FAIL ===" : "=== ALL PASS ===");
  process.exit(fails ? 1 : 0);
  function chainOK(g, w){ try { return g.play(0, w).match || null; } catch(e){ return null; } }
  function chainMatchGlobal(a, b){ var g2 = new A.Chenglong(); g2.last = a; return chainOK(g2, b); }
})();
