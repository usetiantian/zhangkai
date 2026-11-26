/* ============ 《妖刀录》运行时（微信小游戏垫片 + 画布 + 输入 + 存档） ============
 * P0 不引 MiniDom：全部 canvas 画，自己写这层。
 * 浏览器跑 H5 时同一套代码（wx 垫片在浏览器里是空实现）。
 */
(function () {
  'use strict';

  /* ---------- 微信垫片：浏览器里补一套最小实现 ---------- */
  if (typeof window.wx === 'undefined') {
    var mem = {};
    window.wx = {
      /* 浏览器里 wx.createCanvas() 不会自动进画面，必须自己挂上去 */
      createCanvas: function () {
        var c = document.createElement('canvas');
        c.style.cssText = 'position:fixed;left:0;top:0;';
        document.body.appendChild(c);
        return c;
      },
      getSystemInfoSync: function () {
        return { windowWidth: innerWidth, windowHeight: innerHeight, pixelRatio: devicePixelRatio || 1 };
      },
      onTouchStart: function (f) { addEventListener('touchstart', f, { passive: false }); },
      onTouchMove: function (f) { addEventListener('touchmove', f, { passive: false }); },
      onTouchEnd: function (f) { addEventListener('touchend', f, { passive: false }); },
      onTouchCancel: function (f) { addEventListener('touchcancel', f, { passive: false }); },
      setStorageSync: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { mem[k] = v; } },
      getStorageSync: function (k) { try { return JSON.parse(localStorage.getItem(k)) || {}; } catch (e) { return mem[k] || {}; } },
      removeStorageSync: function (k) { try { localStorage.removeItem(k); } catch (e) { delete mem[k]; } },
      vibrateShort: function () { },
      createImage: function () { return new Image(); },
      onShow: function () { }, onHide: function () { },
      getLaunchOptionsSync: function () { return { query: {} }; }
    };
  }
  var WX = window.wx;

  var SYS = WX.getSystemInfoSync();
  var DPR = Math.min(3, SYS.pixelRatio || 1);
  var W = SYS.windowWidth, H = SYS.windowHeight;

  /* 设计分辨率：世界坐标 750 宽，屏幕窄时整体缩放 */
  var SCALE = W / 750;
  var VW = 750, VH = H / SCALE;

  var cv = WX.createCanvas();
  var ctx = cv.getContext('2d');
  if (cv.width !== Math.round(W * DPR) || cv.height !== Math.round(H * DPR)) {
    cv.width = Math.round(W * DPR);
    cv.height = Math.round(H * DPR);
  }
  if (typeof cv.style !== 'undefined' && cv.style) {
    cv.style.width = W + 'px';
    cv.style.height = H + 'px';
    if (cv.style.setProperty) { cv.style.setProperty('width', W + 'px'); cv.style.setProperty('height', H + 'px'); }
  }
  ctx.scale(DPR, DPR);

  /* ---------- 输入 ---------- */
  var T = {
    down: false, x: 0, y: 0, sx: 0, sy: 0, dx: 0, dy: 0,
    moved: false, lastInput: 0, t0: Date.now()
  };
  function pt(e) {
    var t = (e.touches && e.touches[0]) || (e.changedTouches && e.changedTouches[0]);
    if (!t) return null;
    return { x: (t.clientX !== undefined ? t.clientX : t.x), y: (t.clientY !== undefined ? t.clientY : t.y) };
  }
  WX.onTouchStart(function (e) {
    var p = pt(e); if (!p) return;
    e.preventDefault && e.preventDefault();
    T.down = true; T.moved = false;
    T.x = T.sx = p.x; T.y = T.sy = p.y;
    T.dx = 0; T.dy = 0;
    T.lastInput = Date.now();
    BOOT.onDown && BOOT.onDown(p.x, p.y);
  });
  WX.onTouchMove(function (e) {
    var p = pt(e); if (!p) return;
    e.preventDefault && e.preventDefault();
    T.x = p.x; T.y = p.y;
    T.dx = (p.x - T.sx) / SCALE; T.dy = (p.y - T.sy) / SCALE;
    if (Math.abs(T.dx) > 4 || Math.abs(T.dy) > 4) T.moved = true;
    T.lastInput = Date.now();
  });
  WX.onTouchEnd(function (e) {
    var p = pt(e);
    T.down = false;
    T.lastInput = Date.now();
    BOOT.onUp && BOOT.onUp(p ? p.x : T.x, p ? p.y : T.y);
  });

  /* ---------- 存档 ---------- */
  var SAVE_KEY = 'yaodao_save_v1';
  var save = null;
  function loadSave() {
    try { save = WX.getStorageSync(SAVE_KEY); } catch (e) { save = {}; }
    if (!save || typeof save !== 'object') save = {};
    return save;
  }
  function persist() { try { WX.setStorageSync(SAVE_KEY, save); } catch (e) { } }

  /* ---------- 画布辅助 ---------- */
  var G = {
    ctx: ctx, W: W, H: H, SCALE: SCALE, VW: VW, VH: VH, DPR: DPR,
    T: T, save: save, persist: persist, loadSave: loadSave,
    now: function () { return Date.now(); }
  };

  function rr(x, y, w, h, r) {
    r = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }
  G.round = function (x, y, w, h, r, fill, stroke, lw) {
    rr(x, y, w, h, r);
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lw || 1; ctx.stroke(); }
  };
  G.circle = function (x, y, r, fill, stroke, lw) {
    ctx.beginPath(); ctx.arc(x, y, r, 0, 6.2832);
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lw || 1; ctx.stroke(); }
  };
  G.text = function (s, x, y, size, col, align, bold) {
    ctx.font = (bold ? 'bold ' : '') + size + 'px sans-serif';
    ctx.fillStyle = col || '#fff';
    ctx.textAlign = align || 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(s, x, y);
    ctx.textAlign = 'left';
  };
  G.bar = function (x, y, w, h, p, col, bg) {
    G.round(x, y, w, h, h / 2, bg || 'rgba(0,0,0,.45)');
    if (p > 0) G.round(x, y, Math.max(h, w * Math.min(1, p)), h, h / 2, col);
  };
  G.shadowText = function (s, x, y, size, col, stroke) {
    ctx.font = 'bold ' + size + 'px sans-serif';
    ctx.lineWidth = Math.max(2, size / 8);
    ctx.strokeStyle = stroke || 'rgba(0,0,0,.85)';
    ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
    ctx.strokeText(s, x, y);
    ctx.fillStyle = col || '#fff';
    ctx.fillText(s, x, y);
    ctx.textAlign = 'left';
  };

  var BOOT = { onDown: null, onUp: null };
  G.BOOT = BOOT;
  G.setHandlers = function (h) { if (h.down) BOOT.onDown = h.down; if (h.up) BOOT.onUp = h.up; };

  /* ---------- 主循环 ---------- */
  var last = 0, acc = 0, fps = 60, frames = 0, fpsT = 0;
  function loop(ts) {
    lastTick = Date.now();
    if (!last) last = ts;
    var dt = Math.min(0.05, (ts - last) / 1000);
    last = ts;
    frames++; fpsT += dt;
    if (fpsT >= 0.5) { fps = frames / fpsT; frames = 0; fpsT = 0; }
    G.dt = dt; G.fps = fps;
    /* ⚠️ update/draw 抛异常的话，后面的 requestAnimationFrame 就排不上了
       → 循环在第一帧后静默死掉（表现为"画面还停着但什么都不动了"）。
       所以这里必须 try/catch 并把错误打出来。 */
    try {
      if (G.update) G.update(dt);
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
      ctx.clearRect(0, 0, W, H);
      if (G.draw) G.draw();
    } catch (err) {
      if (!loop.err) {
        loop.err = err;
        try { console.error('[loop] ' + (err && (err.stack || err.message) || err)); } catch (e) { }
      }
    }
    requestAnimationFrame(loop);
  }
  /* rAF 看门狗：rAF 在「页面不可见 / 无头浏览器 / 切后台」时会被节流甚至不跑，
     表现就是"画面停着但什么都不动"。这里用一个 setInterval 兜底：
     超过 300ms 没跑过就手动驱动一次。 */
  var lastTick = Date.now();
  setInterval(function () {
    var now = Date.now();
    if (now - lastTick > 300) { lastTick = now; try { loop(now); } catch (e) { } }
  }, 120);
  G.loop = function () { lastTick = Date.now(); requestAnimationFrame(loop); };

  window.G = G;
  window.BOOT = BOOT;
})();
