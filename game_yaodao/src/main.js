/* 《妖刀录》启动 */
(function () {
  function boot() {
    try {
      window.GAME.start();
    } catch (e) {
      var c = document.createElement('div');
      c.style.cssText = 'position:fixed;left:8px;top:8px;color:#f66;font:12px monospace;z-index:9;white-space:pre-wrap';
      c.textContent = '启动失败: ' + (e && (e.stack || e.message) || e);
      document.body.appendChild(c);
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
