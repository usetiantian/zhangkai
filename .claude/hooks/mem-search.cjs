#!/usr/bin/env node
/**
 * mem-search.cjs - keyword + structural search across .claude/memory/.
 *
 * WHY THIS EXISTS
 * ---------------
 * claude-mem's semantic search is the dream (vector search over observations)
 * but its worker is currently OAuth-broken in this env, so the DB stays
 * empty and search returns nothing. This is the cheap, always-works
 * fallback: split each .md file into sections (## headings), and for each
 * query token return sections that contain it in title OR body.
 *
 * Pure stdlib, no deps, runs in <100ms even on dozens of files. Not as
 * good as vector search, but ALWAYS answers. Use it before guessing.
 *
 * Usage:
 *   node mem-search.cjs "PR 44591"
 *   node mem-search.cjs --files "PR 44591"     # only show file paths
 *   node mem-search.cjs --md "PR 44591"        # markdown output
 */

const fs = require("fs");
const path = require("path");

const MEMORY_DIR = path.join(__dirname, "..", "memory");

function parseSections(md) {
  // Split on lines starting with "## " (h2). Each section: { title, body, lineStart }
  const lines = md.split(/\r?\n/);
  const sections = [];
  let current = null;
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^##\s+(.+?)\s*$/);
    if (m) {
      if (current) sections.push(current);
      current = { title: m[1], body: "", startLine: i + 1 };
    } else if (current) {
      current.body += lines[i] + "\n";
    } else {
      // Pre-heading intro (before any ## heading) - treat as one section
      if (!sections._intro) sections._intro = { title: "(intro)", body: "", startLine: 1 };
      sections._intro.body += lines[i] + "\n";
    }
  }
  if (current) sections.push(current);
  if (sections._intro) sections.unshift(sections._intro);
  delete sections._intro;
  return sections;
}

function tokenize(q) {
  return q.toLowerCase().split(/[\s,;]+/).filter(t => t.length >= 2);
}

function scoreSection(section, tokens) {
  const titleLower = section.title.toLowerCase();
  const bodyLower = section.body.toLowerCase();
  let score = 0;
  const matched = [];
  for (const t of tokens) {
    const inTitle = titleLower.includes(t);
    const inBody = bodyLower.includes(t);
    if (inTitle) score += 10;
    if (inBody) score += 1;
    if (inTitle || inBody) matched.push(t);
  }
  return { score, matched };
}

function listFiles() {
  if (!fs.existsSync(MEMORY_DIR)) return [];
  return fs.readdirSync(MEMORY_DIR)
    .filter(n => n.endsWith(".md"))
    .map(n => ({
      name: n,
      path: path.join(MEMORY_DIR, n),
      stat: fs.statSync(path.join(MEMORY_DIR, n)),
    }))
    .sort((a, b) => b.stat.mtimeMs - a.stat.mtimeMs);
}

function search(query, opts) {
  const tokens = tokenize(query);
  if (tokens.length === 0) return [];
  const results = [];
  for (const f of listFiles()) {
    let md;
    try { md = fs.readFileSync(f.path, "utf8"); } catch { continue; }
    const sections = parseSections(md);
    for (const s of sections) {
      const { score, matched } = scoreSection(s, tokens);
      if (score === 0) continue;
      results.push({
        file: f.name,
        path: f.path,
        mtime: f.stat.mtime.toISOString().slice(0, 10),
        title: s.title,
        lineStart: s.startLine,
        score,
        matched,
        // Trim body to the snippet around the first match for readability
        snippet: extractSnippet(s.body, tokens),
      });
    }
  }
  results.sort((a, b) => b.score - a.score);
  return results;
}

function extractSnippet(body, tokens, ctx = 80) {
  const lower = body.toLowerCase();
  let firstHit = body.length;
  for (const t of tokens) {
    const i = lower.indexOf(t);
    if (i >= 0 && i < firstHit) firstHit = i;
  }
  if (firstHit >= body.length) return body.trim().split("\n").slice(0, 3).join("\n");
  const start = Math.max(0, firstHit - ctx);
  const end = Math.min(body.length, firstHit + ctx * 2);
  let snip = body.slice(start, end).trim();
  if (start > 0) snip = "..." + snip;
  if (end < body.length) snip += "...";
  return snip;
}

function render(results, query, opts) {
  if (results.length === 0) {
    process.stdout.write(`(no matches for "${query}" in .claude/memory/)\n`);
    return;
  }
  process.stdout.write(`## mem-search: "${query}" — ${results.length} hit(s)\n\n`);
  let lastFile = "";
  for (const r of results) {
    if (opts.filesOnly) {
      process.stdout.write(`${r.path}\n`);
      continue;
    }
    if (r.file !== lastFile) {
      process.stdout.write(`### ${r.file}  (${r.mtime})\n`);
      process.stdout.write(`Path: ${r.path}\n\n`);
      lastFile = r.file;
    }
    process.stdout.write(`#### ${r.title}  (line ~${r.lineStart}, score=${r.score}, matched=${r.matched.join(",")})\n`);
    process.stdout.write("```\n");
    process.stdout.write(r.snippet + "\n");
    process.stdout.write("```\n\n");
  }
}

(function main() {
  const argv = process.argv.slice(2);
  const opts = { filesOnly: false };
  const positional = [];
  for (const a of argv) {
    if (a === "--files") opts.filesOnly = true;
    else positional.push(a);
  }
  const query = positional.join(" ").trim();
  if (!query) {
    process.stderr.write('Usage: node mem-search.cjs [--files] "search terms"\n');
    process.exit(2);
  }
  const results = search(query, opts);
  render(results, query, opts);
})();
