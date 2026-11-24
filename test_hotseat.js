/* 实证：五子棋双人 = 同屏轮流（两次点击两色棋子，无AI自动落子、无网络对象） */
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
  createImage(){ return { set src(v){}, get src(){return "";}, complete:true, width:64, height:64 }; },
  getSystemInfoSync(){ return { windowWidth:390, windowHeight:844, pixelRatio:2 }; },
  getStorageSync(k){ return storage[k] || {}; }, setStorageSync(k,v){ storage[k]=v; },
  onTouchStart(f){ touch.start.push(f); }, onTouchMove(f){ touch.move.push(f); },
  onTouchEnd(f){ touch.end.push(f); }, onTouchCancel(f){ touch.cancel.push(f); },
  onShow(){}, onHide(){}, getLaunchOptionsSync(){ return {query:{}}; }, vibrateShort(){},
  createRewardedVideoAd(){ return {load(cb){cb&&cb();},show(cb){cb&&cb();},onClose(cb){cb&&cb({isEnded:true});},onError(){}}; }
};
global.requestAnimationFrame = fn => setTimeout(() => fn(Date.now()), 16);
global.cancelAnimationFrame = id => clearTimeout(id);
require(path.join(__dirname, "game/wx/game.js"));
const MD = global.__minidom, Mini = global.__mini;
const T = (x, y) => { const p = { touches: [{clientX:x, clientY:y}], changedTouches: [{clientX:x, clientY:y}] };
  touch.start.forEach(f => f(p)); touch.end.forEach(f => f(p)); };
const hit = sel => MD.debugHits().find(h => h.el.id === sel);
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  await sleep(700);
  // 乐园 → 五子棋 → 双人
  T(390/7*3.5, 844-28); await sleep(400);
  T(100, 98); await sleep(1000);
  const pm2 = hit("pm-2"); T(pm2.x + pm2.w/2, pm2.y + pm2.h/2); await sleep(1200);
  const g = global.__goG || global.__arcade._goG;   /* 调试句柄 */
  // 找 gm-c 命中框，算两个交叉点坐标
  const cv = hit("gm-c");
  const N = 15, S = 31, pad = 20;  /* 棋盘 465px，格31 */
  const pt = (x, y) => ({ x: cv.x + (pad + x * S) / 465 * cv.w, y: cv.y + (pad + y * S) / 465 * cv.h });
  const b1 = g ? JSON.parse(JSON.stringify(g.b)) : null;
  const a = pt(7, 7); T(a.x, a.y); await sleep(500);
  const after1 = g ? JSON.parse(JSON.stringify(g.b)) : null;
  const b2 = pt(8, 8); T(b2.x, b2.y); await sleep(500);
  const after2 = g ? JSON.parse(JSON.stringify(g.b)) : null;
  // 统计棋子数
  const count = bb => bb ? bb.flat().filter(v => v).length : -1;
  console.log("落子前:", count(b1), "→ 第一次点击后:", count(after1), "→ 第二次点击后:", count(after2));
  const blackAt = after2 && after2[7] && after2[7][7], whiteAt = after2 && after2[8] && after2[8][8];
  console.log("(7,7)=", blackAt, "(8,8)=", whiteAt, "| 当前轮到:", g && g.turn);
  const ok = count(b1) === 0 && count(after1) === 1 && count(after2) === 2 &&
             blackAt === 1 && whiteAt === 2 && g.turn === 1;
  console.log(ok ? "PASS 同屏双人：两人在同一台设备轮流落子，无AI、无网络" : "FAIL");
  process.exit(ok ? 0 : 1);
})();
