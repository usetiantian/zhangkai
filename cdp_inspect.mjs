import { spawn } from "node:child_process";
import fs from "node:fs";
const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const PORT = 9335;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const proc = spawn(EDGE, ["--headless=new", `--remote-debugging-port=${PORT}`,
  "--user-data-dir=C:/Users/87999/claude-workspace/_edge_p3", "--no-first-run",
  "--no-default-browser-check", "--disable-gpu", "--window-size=1696,1169", "about:blank"], { stdio: "ignore" });
async function findPage() {
  for (let i = 0; i < 40; i++) {
    try { const j = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const p = j.find((t) => t.type === "page"); if (p) return p; } catch {}
    await sleep(500);
  }
  throw new Error("no cdp");
}
let id = 0;
function rpc(ws, method, params = {}) {
  const mid = ++id;
  return new Promise((res, rej) => {
    const on = (ev) => { const m = JSON.parse(ev.data);
      if (m.id === mid) { ws.removeEventListener("message", on); m.error ? rej(new Error(method + " " + JSON.stringify(m.error))) : res(m.result); } };
    ws.addEventListener("message", on);
    ws.send(JSON.stringify({ id: mid, method, params }));
    setTimeout(() => { ws.removeEventListener("message", on); rej(new Error(method + " timeout")); }, 45000);
  });
}
const page = await findPage();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
await rpc(ws, "Runtime.enable");
await rpc(ws, "Page.enable");
await rpc(ws, "Page.navigate", { url: "http://127.0.0.1:8188" });
await sleep(15000);
const met = await rpc(ws, "Page.getLayoutMetrics");
const cs = met.cssContentSize || met.contentSize;
// 右下角那个小窗的位置（从截图量：x 1085-1340, y 745-940，截图 1666x1074）
const px = Math.round(1085 / 1666 * cs.width), py = Math.round(745 / 1074 * cs.height);
const evalJs = async (expr) => {
  const r = await rpc(ws, "Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  return r.result && r.result.value;
};
const info = await evalJs(`(() => {
  const el = document.elementFromPoint(${px + 120}, ${py + 90});
  const chain = [];
  let n = el;
  for (let i = 0; i < 9 && n; i++) {
    chain.push(n.tagName + (n.className && typeof n.className === 'string' ? '.' + n.className.split(' ').filter(Boolean).slice(0,3).join('.') : '') + (n.id ? '#' + n.id : ''));
    n = n.parentElement;
  }
  const root = document.querySelector('.comfy-modal, .litegraph, [class*="search"], [class*="Search"]');
  return JSON.stringify({
    hit: el ? el.tagName + '.' + (el.className||'').toString().split(' ').slice(0,3).join('.') : null,
    chain,
    hasInput: !!document.querySelector('input[placeholder*="Search"], input[placeholder*="search"], .comfy-search input'),
    inputs: Array.from(document.querySelectorAll('input')).map(i => (i.placeholder||i.className||i.type||'?')).slice(0,40),
    dialogs: Array.from(document.querySelectorAll('[class*="modal"],[class*="Modal"],[class*="dialog"],[class*="popover"]')).map(d => (d.className||'').toString().slice(0,60)).slice(0,12),
  }, null, 1);
})()`);
console.log(info);
ws.close(); proc.kill(); process.exit(0);

