#!/usr/bin/env node
/**
 * my-session-start.cjs — SessionStart hook for the claude-workspace.
 *
 * WHY THIS EXISTS
 * ---------------
 * Two parallel sources of medium-term memory need to be merged into every
 * new Claude session, and the pinned ECC plugin's `session:start` hook is
 * silently no-op'd on this host (the ECC plugin isn't actually installed).
 *
 * This hook:
 *   1. Loads up to N most recent files from `.claude/memory/` (cheap, always
 *      works, file-based). These are workspace-specific notes the user/maintainer
 *      has written by hand over time.
 *   2. Best-effort fetches claude-mem's `session_start_context` for the
 *      current project (semantic observations of past tool usage). Best-effort
 *      because that worker may not be running yet (e.g. cold start). Bounded
 *      timeout so it can never block session start.
 *
 * Output is bounded — never emit more than MAX_BYTES total.
 */

const fs = require("fs");
const path = require("path");
const http = require("http");

const MAX_FILES = 6;
const MAX_BYTES = 8_000;          // total hook stdout budget
const MEMORY_BUDGET = 5_500;      // bytes for .claude/memory/ section
const CLAUDEMEM_BUDGET = 2_400;   // bytes for claude-mem section
const MEMORY_DIR = path.join(__dirname, "..", "memory");
const CLAUDEMEM_URL = "http://127.0.0.1:37777";
const CLAUDEMEM_TIMEOUT_MS = 2500;
const PROJECT = process.env.CLAUDE_PROJECT || "claude-workspace";

function safeStat(p) {
  try { return fs.statSync(p); } catch { return null; }
}

function listMemoryFiles(dir) {
  const stat = safeStat(dir);
  if (!stat || !stat.isDirectory()) return [];
  return fs.readdirSync(dir)
    .filter(name => name.endsWith(".md"))
    .map(name => ({ name, path: path.join(dir, name) }))
    .filter(({ path: p }) => {
      const s = safeStat(p);
      return s && s.isFile();
    })
    .sort((a, b) => {
      const sa = safeStat(a.path).mtimeMs;
      const sb = safeStat(b.path).mtimeMs;
      return sb - sa;
    })
    .slice(0, MAX_FILES);
}

function renderMemory(files) {
  const lines = [];
  lines.push(`## Source 1: .claude/memory/ (${files.length} most recent note(s))`);
  lines.push("Read the full file when relevant. Path is included.");
  lines.push("");
  for (const f of files) {
    const stat = safeStat(f.path);
    const sizeKb = (stat.size / 1024).toFixed(1);
    const mtime = stat.mtime.toISOString().slice(0, 10);
    lines.push(`### ${f.name}  (${sizeKb} KB, ${mtime})`);
    lines.push(`Path: ${f.path}`);
    let preview;
    try {
      preview = fs.readFileSync(f.path, "utf8").split(/\r?\n/).slice(0, 30).join("\n");
    } catch {
      preview = "(failed to read preview)";
    }
    lines.push("```");
    lines.push(preview);
    lines.push("```");
    lines.push("");
  }
  let out = lines.join("\n");
  if (out.length > MEMORY_BUDGET) {
    out = out.slice(0, MEMORY_BUDGET) + "\n\n[...truncated — full files at paths above]\n";
  }
  return out;
}

function httpGetJson(url, timeoutMs) {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: timeoutMs }, (res) => {
      let data = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => { data += chunk; if (data.length > CLAUDEMEM_BUDGET * 4) { req.destroy(); } });
      res.on("end", () => {
        if (res.statusCode !== 200) return resolve(null);
        try { resolve(JSON.parse(data)); } catch { resolve(null); }
      });
    });
    req.on("error", () => resolve(null));
    req.on("timeout", () => { req.destroy(); resolve(null); });
  });
}

function httpPostJson(url, body, timeoutMs) {
  return new Promise((resolve) => {
    const data = JSON.stringify(body);
    const u = new URL(url);
    const req = http.request({
      hostname: u.hostname, port: u.port, path: u.pathname + u.search,
      method: "POST", timeout: timeoutMs,
      headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(data) },
    }, (res) => {
      let buf = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => { buf += chunk; if (buf.length > CLAUDEMEM_BUDGET * 4) { req.destroy(); } });
      res.on("end", () => {
        if (res.statusCode !== 200) return resolve(null);
        try { resolve(JSON.parse(buf)); } catch { resolve(null); }
      });
    });
    req.on("error", () => resolve(null));
    req.on("timeout", () => { req.destroy(); resolve(null); });
    req.write(data);
    req.end();
  });
}

async function fetchClaudeMemContext() {
  // claude-mem's MCP tool session_start_context ultimately hits an HTTP
  // endpoint. Probe the well-known routes until one responds; degrade
  // gracefully if the worker isn't running.
  const tries = [
    () => httpGetJson(`${CLAUDEMEM_URL}/api/session-context?project=${encodeURIComponent(PROJECT)}`, CLAUDEMEM_TIMEOUT_MS),
    () => httpGetJson(`${CLAUDEMEM_URL}/api/context?project=${encodeURIComponent(PROJECT)}`, CLAUDEMEM_TIMEOUT_MS),
    () => httpPostJson(`${CLAUDEMEM_URL}/api/mcp/session_start_context`, { project: PROJECT }, CLAUDEMEM_TIMEOUT_MS),
    () => httpPostJson(`${CLAUDEMEM_URL}/mcp`, {
      jsonrpc: "2.0", id: 1, method: "tools/call",
      params: { name: "session_start_context", arguments: { project: PROJECT } },
    }, CLAUDEMEM_TIMEOUT_MS),
  ];
  for (const t of tries) {
    try {
      const r = await t();
      if (r && (r.context || r.content || r.result || r.observations || r.message)) {
        return r;
      }
    } catch { /* keep trying */ }
  }
  return null;
}

function renderClaudeMem(ctx) {
  if (!ctx) {
    return [
      "## Source 2: claude-mem semantic memory",
      "(claude-mem worker not reachable on http://127.0.0.1:37777 — search/timeline tools unavailable this session)",
      "To enable:  cd ~/.claude/plugins/cache/thedotmack/claude-mem/<version> && bun scripts/worker-service.cjs start",
      "",
    ].join("\n");
  }
  const lines = ["## Source 2: claude-mem semantic memory (worker reachable)", ""];
  // Try to extract text-ish content from whatever shape came back.
  const text = (ctx.context?.text) || (ctx.content && ctx.content[0]?.text) ||
               (ctx.result?.content && ctx.result.content[0]?.text) ||
               (typeof ctx === "string" ? ctx : JSON.stringify(ctx, null, 2));
  let body = String(text);
  if (body.length > CLAUDEMEM_BUDGET) {
    body = body.slice(0, CLAUDEMEM_BUDGET) + "\n[...truncated]";
  }
  lines.push(body);
  return lines.join("\n");
}

(async function main() {
  // Drain stdin (Claude Code hooks contract)
  try { fs.readFileSync(0, "utf8"); } catch { /* optional */ }

  const out = [];
  out.push("# SessionStart context (assembled by my-session-start.cjs)");
  out.push("");

  const files = listMemoryFiles(MEMORY_DIR);
  if (files.length === 0) {
    out.push("## Source 1: .claude/memory/");
    out.push("(empty — no notes yet)");
    out.push("");
  } else {
    out.push(renderMemory(files));
  }

  const cm = await fetchClaudeMemContext();
  out.push(renderClaudeMem(cm));

  let body = out.join("\n");
  if (body.length > MAX_BYTES) {
    body = body.slice(0, MAX_BYTES) + "\n\n[...total context truncated — read source files directly]";
  }
  process.stdout.write(body);
  process.exit(0);
})();
