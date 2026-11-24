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
  getSystemInfoSync(){ return { windowWidth: 390, windowHeight: 844, pixelRatio: 2 }; },
  getStorageSync(k){ return storage[k] || {}; }, setStorageSync(k, v){ storage[k] = v; },
  onTouchStart(f){ touch.start.push(f); }, onTouchMove(f){ touch.move.push(f); },
  onTouchEnd(f){ touch.end.push(f); }, onTouchCancel(f){ touch.cancel.push(f); },
  onShow(){}, onHide(){}, getLaunchOptionsSync(){ return { query: {} }; }, vibrateShort(){},
  createRewardedVideoAd(){ return { load(cb){cb&&cb();}, show(cb){cb&&cb();}, onClose(cb){cb&&cb({isEnded:true});}, onError(){} }; }
};
global.requestAnimationFrame = fn => setTimeout(() => fn(Date.now()), 16);
require(path.join(__dirname, "game/wx/game.js"));
setTimeout(() => {
  try {
    const Mini = global.__mini;
    const p = (x, y) => { const e = { touches: [{clientX:x, clientY:y}], changedTouches: [{clientX:x, clientY:y}] };
      touch.start.forEach(f => f(e)); touch.end.forEach(f => f(e)); };
    p(39, 76);
    setTimeout(() => {
      try {
        console.log("mode:", Mini.mode, "last:", Mini.lastGame);
        let n = 0;
        const memWatch = setInterval(() => {
          const mu = process.memoryUsage();
          console.log("mem", ++n, Math.round(mu.heapUsed/1048576) + "MB",
            "shots=", global.__game && global.__game.state ? "?" : "?",
            "bodyKids=", global.document.body.children.length);
          if (n > 8) clearInterval(memWatch);
        }, 1500);
        const doc = global.document;
        const walk = (el, d) => {
          console.log(" ".repeat(d) + "<" + el.tagName + " id=" + el.id + " cls='" + el.className + "' kids=" + el.children.length + (el._cv ? " [cv]" : ""));
          for (const c of el.children) walk(c, d + 2);
        };
        walk(doc.body, 0);
        const doc2 = global.document;
        console.log("app.display=", doc2.getElementById("app").style.display,
          "| topbar.display=", doc2.getElementById("topbar").style.display,
          "| scr-game.display=", doc2.getElementById("scr-game").style.display);
        console.log("STATS:", JSON.stringify(global.__minidom.debugStats()));
        const hits = global.__minidom.debugHits();
        console.log("HITS:", hits.length);
        hits.forEach(h => console.log("  hit:", h.el.id || h.el.className || h.el.tagName, Math.round(h.x), Math.round(h.y), Math.round(h.w) + "x" + Math.round(h.h)));
      } catch (e){ console.log("MIDDLE ERR:", e.stack && e.stack.split("\n").slice(0,3).join(" | ")); }
      process.exit(0);
    }, 500);
  } catch (e){ console.log("OUTER ERR:", e.message); process.exit(1); }
}, 800);
