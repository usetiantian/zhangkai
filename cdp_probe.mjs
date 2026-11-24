// 用 CDP 驱动 Edge 无头浏览器：打开 ComfyUI -> 截图 -> 双击画布加节点 -> 抓控制台错误
import { spawn } from "node:child_process";
import fs from "node:fs";

const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const PORT = 9333;
const URL = "http://127.0.0.1:8188";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const proc = spawn(EDGE, [
  "--headless=new", `--remote-debugging-port=${PORT}`,
  "--user-data-dir=C:/Users/87999/claude-workspace/_edge_profile",
  "--no-first-run", "--no-default-browser-check", "--disable-gpu",
  "--window-size=1696,1169", "about:blank",
], { stdio: "ignore" });

async function targets() {
  for (let i = 0; i < 40; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const j = await r.json();
      const page = j.find((t) => t.type === "page");
      if (page) return page;
    } catch {}
    await sleep(500);
  }
  throw new Error("无法连接 Edge CDP");
}

let id = 0;
function rpc(ws, method, params = {}) {
  const mid = ++id;
  return new Promise((resolve, reject) => {
    const onMsg = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id === mid) {
        ws.removeEventListener("message", onMsg);
        m.error ? reject(new Error(method + ": " + JSON.stringify(m.error))) : resolve(m.result);
      }
    };
    ws.addEventListener("message", onMsg);
    ws.send(JSON.stringify({ id: mid, method, params }));
    setTimeout(() => { ws.removeEventListener("message", onMsg); reject(new Error(method + " 超时")); }, 60000);
  });
}

const page = await targets();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));

const logs = [];
ws.addEventListener("message", (ev) => {
  const m = JSON.parse(ev.data);
  if (m.method === "Runtime.consoleAPICalled" && ["error", "warning"].includes(m.params.type)) {
    const txt = (m.params.args || []).map((a) => a.value ?? a.description ?? "").join(" ").slice(0, 300);
    logs.push("[" + m.params.type + "] " + txt);
  }
  if (m.method === "Runtime.exceptionThrown") {
    const d = m.params.exceptionDetails || {};
    logs.push("[EXCEPTION] " + (d.exception?.description || d.text || "").slice(0, 400));
  }
  if (m.method === "Log.entryAdded") {
    const e = m.params.entry;
    if (e.level === "error") logs.push("[log:" + e.level + "] " + String(e.text).slice(0, 200));
  }
});

await rpc(ws, "Runtime.enable");
await rpc(ws, "Log.enable");
await rpc(ws, "Page.enable");
console.log("打开", URL);
await rpc(ws, "Page.navigate", { url: URL });
await sleep(14000);

const shot1 = await rpc(ws, "Page.captureScreenshot", { format: "png" });
fs.writeFileSync("_cdp_1_loaded.png", Buffer.from(shot1.data, "base64"));
console.log("已截图 _cdp_1_loaded.png");

// 找到画布尺寸，双击画布中心
const metrics = await rpc(ws, "Page.getLayoutMetrics");
const cs = metrics.cssContentSize || metrics.contentSize;
const x = Math.round(cs.width / 2), y = Math.round(cs.height / 2);
console.log("画布尺寸", cs.width, "x", cs.height, "-> 双击", x, y);
for (const type of ["mousePressed", "mouseReleased"]) {
  await rpc(ws, "Input.dispatchMouseEvent", { type, x, y, button: "left", clickCount: 2, buttons: type === "mousePressed" ? 1 : 0 });
  await sleep(60);
}
await sleep(6000);
const shot2 = await rpc(ws, "Page.captureScreenshot", { format: "png" });
fs.writeFileSync("_cdp_2_afterdblclick.png", Buffer.from(shot2.data, "base64"));
console.log("已截图 _cdp_2_afterdblclick.png");

console.log("\n=== 控制台错误/警告 (" + logs.length + ") ===");
logs.slice(-25).forEach((l) => console.log("  " + l));
ws.close();
proc.kill();
process.exit(0);

