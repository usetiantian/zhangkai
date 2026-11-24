// 自动二分：复现「双击加节点 → 选择器卡死」，并可用 CDP 屏蔽某个扩展的 JS 来定位元凶
import { spawn } from "node:child_process";
import fs from "node:fs";

const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const PORT = 9334;
const URL = "http://127.0.0.1:8188";
const BLOCK = (process.argv[2] || "").split(",").filter(Boolean);   // 要屏蔽的 URL 片段
const TAG = process.argv[3] || "base";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const proc = spawn(EDGE, [
  "--headless=new", `--remote-debugging-port=${PORT}`,
  "--user-data-dir=C:/Users/87999/claude-workspace/_edge_p2",
  "--no-first-run", "--no-default-browser-check", "--disable-gpu",
  "--window-size=1696,1169", "about:blank",
], { stdio: "ignore" });

async function findPage() {
  for (let i = 0; i < 40; i++) {
    try {
      const j = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const p = j.find((t) => t.type === "page");
      if (p) return p;
    } catch {}
    await sleep(500);
  }
  throw new Error("CDP 连接失败");
}
let id = 0;
function rpc(ws, method, params = {}) {
  const mid = ++id;
  return new Promise((res, rej) => {
    const on = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id === mid) { ws.removeEventListener("message", on); m.error ? rej(new Error(method + " " + JSON.stringify(m.error))) : res(m.result); }
    };
    ws.addEventListener("message", on);
    ws.send(JSON.stringify({ id: mid, method, params }));
    setTimeout(() => { ws.removeEventListener("message", on); rej(new Error(method + " 超时")); }, 45000);
  });
}
const page = await findPage();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
const errs = [];
ws.addEventListener("message", (ev) => {
  const m = JSON.parse(ev.data);
  if (m.method === "Runtime.exceptionThrown") {
    const d = m.params.exceptionDetails || {};
    errs.push("[EXCEPTION] " + String(d.exception?.description || d.text || "").split("\n").slice(0, 3).join(" | "));
  }
  if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") {
    errs.push("[console.error] " + (m.params.args || []).map((a) => a.value ?? a.description ?? "").join(" ").slice(0, 260));
  }
});
await rpc(ws, "Runtime.enable");
await rpc(ws, "Page.enable");
await rpc(ws, "Network.enable");
if (BLOCK.length) {
  await rpc(ws, "Network.setBlockedURLs", { urls: BLOCK.map((b) => "*" + b + "*") });
  console.log("已屏蔽:", BLOCK.join(", "));
}
await rpc(ws, "Page.navigate", { url: URL });
await sleep(15000);

const met = await rpc(ws, "Page.getLayoutMetrics");
const cs = met.cssContentSize || met.contentSize;
const cx = Math.round(cs.width / 2), cy = Math.round(cs.height / 2);
const dbl = async (x, y) => {
  for (const type of ["mousePressed", "mouseReleased"]) {
    await rpc(ws, "Input.dispatchMouseEvent", { type, x, y, button: "left", clickCount: 2, buttons: type === "mousePressed" ? 1 : 0 });
    await sleep(70);
  }
};
await dbl(cx, cy);              // 打开选择器
await sleep(5000);
await rpc(ws, "Input.insertText", { text: "KSampler" });   // 搜索
await sleep(2500);
const s1 = await rpc(ws, "Page.captureScreenshot", { format: "png" });
fs.writeFileSync(`_cdp_${TAG}_1picker.png`, Buffer.from(s1.data, "base64"));
console.log("已截图 _cdp_" + TAG + "_1picker.png");
// 点结果行（列表通常在输入框下方）
await dbl(cx, cy + 70);
await sleep(6000);
const s2 = await rpc(ws, "Page.captureScreenshot", { format: "png" });
fs.writeFileSync(`_cdp_${TAG}_2after.png`, Buffer.from(s2.data, "base64"));
console.log("已截图 _cdp_" + TAG + "_2after.png");
console.log("\n=== 错误 (" + errs.length + ") ===");
errs.slice(0, 14).forEach((e) => console.log("  " + e));
ws.close(); proc.kill(); process.exit(0);

