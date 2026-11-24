/* wx 包 Node 无头交互测试 */
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
  createImage(){ return { set src(v){ this._s = v; setTimeout(()=>this.onload&&this.onload(),1); }, get src(){ return this._s; }, complete: true, width: 64, height: 64 }; },
  getSystemInfoSync(){ return { windowWidth: 390, windowHeight: 844, pixelRatio: 2 }; },
  getStorageSync(k){ return storage[k] || {}; },
  setStorageSync(k, v){ storage[k] = v; },
  onTouchStart(f){ touch.start.push(f); }, onTouchMove(f){ touch.move.push(f); },
  onTouchEnd(f){ touch.end.push(f); }, onTouchCancel(f){ touch.cancel.push(f); },
  onShow(){}, onHide(){}, getLaunchOptionsSync(){ return { query: {} }; }, vibrateShort(){},
  createRewardedVideoAd(){ return { load(cb){cb&&cb();}, show(cb){cb&&cb();}, onClose(cb){cb&&cb({isEnded:true});}, onError(){} }; }
};
global.requestAnimationFrame = fn => setTimeout(() => fn(Date.now()), 16);
process.on("uncaughtException", e => console.log("[uncaught]", e.message.slice(0, 200)));
process.on("unhandledRejection", e => console.log("[unhandled]", String(e && e.message || e).slice(0, 200)));

require(path.join(__dirname, "game/wx/game.js"));
const MD = global.__minidom, Mini = global.__mini;
function T(list, x, y){ const p = { touches: [{clientX:x, clientY:y}], changedTouches: [{clientX:x, clientY:y}], timeStamp: Date.now() }; list.forEach(f => { try { f(p); } catch (e){ console.log("[touch-err]", e.message.slice(0,200)); } }); }
function tap(x, y){ T(touch.start, x, y); T(touch.end, x, y); }
function hit(sel){
  for (const h of MD.debugHits()){
    const e = h.el;
    if (e.id === sel || (" " + e.className + " ").indexOf(" " + sel + " ") >= 0) return h;
  }
  return null;
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
let fails = 0;
function step(name, ok, extra){
  const line = (ok === true ? "PASS " : "FAIL ") + name + (extra !== undefined && ok !== true ? "  << " + extra : "");
  console.log(line);
  if (ok !== true) fails++;
}
const watchdog = setTimeout(() => { console.log("WATCHDOG TIMEOUT"); process.exit(2); }, 30000);

(async () => {
  await sleep(800);
  Mini.screen = "arcade";
  await sleep(300);
  const doc = global.document, G = global.__game, A = global.__arcade, UI = global.__ui;
  step("boot", !!Mini && !!MD && !!G && !!A && !!UI && (global.__LEVELS || []).length === 100, "mini=" + !!Mini + " game=" + !!G + " ui=" + !!UI);

  try {
  // 1) 地图 → 第1关
  tap(100, 52 + 46); await sleep(800);
  step("enter-td", Mini.mode === "game" && /第 1 关/.test(doc.getElementById("hud-level").textContent),
       "mode=" + Mini.mode + " hud=" + (doc.getElementById("hud-level") && doc.getElementById("hud-level").textContent));

  // 2) 选炉 → 点建造位
  const bk = hit("bk");
  step("bk-visible", !!bk);
  if (bk){ tap(bk.x + bk.w / 2, bk.y + bk.h / 2); await sleep(300); }
  const ch = hit("c");
  step("td-canvas-visible", !!ch && ch.w > 100, ch ? "w=" + Math.round(ch.w) : "none");
  if (ch){
    const pad = global.__LEVELS[0].pads[0];
    const px = ch.x + (pad[0] + 0.5) / 20 * ch.w, py = ch.y + (pad[1] + 0.5) / 12 * ch.h;
    tap(px, py); await sleep(400);
    step("build-tower", G.stoves && G.stoves.length === 1, "stoves=" + (G.stoves ? G.stoves.length : "?"));
    tap(px, py); await sleep(400);
    step("panel-show", (" " + doc.getElementById("panel").className + " ").indexOf(" show") >= 0,
         "cls=" + doc.getElementById("panel").className);
  }

  // 3) 退出 TD
  const menu = hit("btn-pause-menu");
  if (menu){ tap(menu.x + menu.w / 2, menu.y + menu.h / 2); await sleep(600); }
  step("exit-td", Mini.mode === "shell", "mode=" + Mini.mode);

  // 4) 乐园 → 消除
  tap(39, 816); await sleep(500);
  tap(100, 52 + 2 * 102 + 46); await sleep(1500);
  step("enter-m3", Mini.mode === "game" && !!doc.getElementById("m3-c") && !!(A._m3 && A._m3.g),
       "mode=" + Mini.mode + " m3c=" + !!doc.getElementById("m3-c") + " hook=" + !!(A._m3 && A._m3.g));

  // 5) 滑动
  if (A._m3 && A._m3.g){
    const g = A._m3.g;
    let pair = null;
    for (let r = 0; r < 8 && !pair; r++) for (let c = 0; c < 7 && !pair; c++){
      g.swapCell([r, c], [r, c + 1]); if (g.findRuns().length) pair = [r, c, r, c + 1]; g.swapCell([r, c], [r, c + 1]);
    }
    for (let r = 0; r < 7 && !pair; r++) for (let c = 0; c < 8 && !pair; c++){
      g.swapCell([r, c], [r + 1, c]); if (g.findRuns().length) pair = [r, c, r + 1, c]; g.swapCell([r, c], [r + 1, c]);
    }
    if (pair){
      const m3h = hit("m3-c");
      const ctr = (r, c) => ({ x: m3h.x + (c + 0.5) * m3h.w / 8, y: m3h.y + (r + 0.5) * m3h.h / 8 });
      const a = ctr(pair[0], pair[1]), b = ctr(pair[2], pair[3]);
      const before = doc.getElementById("m3-x").textContent;
      T(touch.start, a.x, a.y);
      T(touch.move, (a.x + b.x) / 2, (a.y + b.y) / 2);
      T(touch.move, b.x, b.y);
      T(touch.end, b.x, b.y);
      await sleep(2800);
      step("m3-swipe", before !== doc.getElementById("m3-x").textContent,
           before + " → " + doc.getElementById("m3-x").textContent + " tip=" + doc.getElementById("m3-tip").textContent.slice(0, 20));
    } else step("m3-swipe", false, "no pair");
  }

  // 6) 过关 → 下一关
  if (A._m3){
    A._m3.win(); await sleep(1800);
    step("m3-result", !!doc.getElementById("ar-next"));
    const nx = hit("ar-next");
    if (nx){
      tap(nx.x + nx.w / 2, nx.y + nx.h / 2); await sleep(1500);
      step("m3-next", /第 2 关/.test(doc.getElementById("arc-sub").textContent),
           "sub=" + doc.getElementById("arc-sub").textContent);
    }
    const back = hit("m3-back");
    if (back){ tap(back.x + back.w / 2, back.y + back.h / 2); await sleep(700); }
    step("back-hub", Mini.mode === "shell", "mode=" + Mini.mode);
  }
  } catch (e){ step("flow-error", false, e.message + " @ " + (e.stack || "").split("\n")[1]); }

  clearTimeout(watchdog);
  console.log(fails ? "=== " + fails + " FAIL ===" : "=== ALL PASS ===");
  process.exit(fails ? 1 : 0);
})();
