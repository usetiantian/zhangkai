#!/usr/bin/env node
/**
 * Safe Web Fetch — SSRF-protected URL fetcher
 *
 * Usage:
 *   node safe-fetch.js <url>
 *   cat urls.txt | node safe-fetch.js --stdin
 *
 * Safety checks:
 *   - Blocks internal/private IPs
 *   - Blocks file:// protocol
 *   - Blocks localhost
 *   - Max URL length 2048
 *   - Max response size 1MB
 *   - Timeout 15s
 */

const BLOCKED_HOSTS = [
  "localhost", "127.0.0.1", "0.0.0.0",
  "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
  "169.254.0.0/16", // link-local
  "100.64.0.0/10",   // CGN
  "0.0.0.0/8",        // current network
  "240.0.0.0/4",      // reserved
];

function isPrivateIP(hostname) {
  // IPv4 check
  const parts = hostname.split(".");
  if (parts.length === 4 && parts.every((p) => /^\d+$/.test(p) && parseInt(p) <= 255)) {
    const first = parseInt(parts[0]);
    const second = parseInt(parts[1]);
    if (hostname === "127.0.0.1" || hostname === "0.0.0.0") return true;
    if (first === 10) return true;                          // 10.0.0.0/8
    if (first === 172 && second >= 16 && second <= 31) return true; // 172.16.0.0/12
    if (first === 192 && second === 168) return true;       // 192.168.0.0/16
    if (first === 169 && second === 254) return true;       // 169.254.0.0/16
    if (first >= 224) return true;                          // multicast/reserved
  }
  // IPv6 loopback
  if (hostname === "::1" || hostname === "[::1]") return true;
  return false;
}

function validateURL(rawUrl) {
  const url = rawUrl.trim();

  if (url.length > 2048) {
    return { valid: false, reason: "URL too long (>2048 chars)" };
  }

  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return { valid: false, reason: "Invalid URL format" };
  }

  if (parsed.protocol === "file:") {
    return { valid: false, reason: "file:// protocol blocked" };
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return { valid: false, reason: `Protocol ${parsed.protocol} not allowed (only http/https)` };
  }

  const hostname = parsed.hostname.toLowerCase();

  if (hostname === "localhost" || hostname.endsWith(".localhost")) {
    return { valid: false, reason: "localhost blocked" };
  }

  if (isPrivateIP(hostname)) {
    return { valid: false, reason: `Private/reserved IP blocked: ${hostname}` };
  }

  return { valid: true, url: parsed.href };
}

async function fetchURL(url) {
  const validation = validateURL(url);
  if (!validation.valid) {
    console.log(JSON.stringify({ error: validation.reason, url }));
    return;
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  try {
    const response = await fetch(validation.url, {
      signal: controller.signal,
      headers: { "User-Agent": "CC-SafeFetch/1.0" },
      redirect: "follow",
    });

    clearTimeout(timeout);

    // Read up to 1MB
    const reader = response.body.getReader();
    const chunks = [];
    let totalSize = 0;
    const MAX_SIZE = 1024 * 1024;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      totalSize += value.length;
      if (totalSize > MAX_SIZE) {
        console.log(JSON.stringify({
          url: validation.url,
          status: response.status,
          truncated: true,
          size: totalSize,
          content: new TextDecoder().decode(
            new Uint8Array(chunks.flatMap((c) => Array.from(c)).concat(Array.from(value)).slice(0, MAX_SIZE))
          ),
          note: `Response truncated at 1MB (total: ${totalSize} bytes)`,
        }));
        return;
      }
      chunks.push(value);
    }

    const body = new TextDecoder().decode(
      new Uint8Array(chunks.flatMap((c) => Array.from(c)))
    );

    console.log(JSON.stringify({
      url: validation.url,
      status: response.status,
      size: totalSize,
      content: body.slice(0, 50000), // max output
    }));
  } catch (err) {
    clearTimeout(timeout);
    console.log(JSON.stringify({
      error: err.name === "AbortError" ? "Timeout (15s)" : err.message,
      url: validation.url,
    }));
  }
}

// ── Main ─────────────────────────────────────────────────────────────
const args = process.argv.slice(2);

if (args.includes("--stdin")) {
  // Read URLs from stdin
  const readline = await import("readline");
  const rl = readline.createInterface({ input: process.stdin });
  const urls = [];
  for await (const line of rl) {
    if (line.trim()) urls.push(line.trim());
  }
  for (const url of urls) {
    await fetchURL(url);
  }
} else if (args.length > 0) {
  await fetchURL(args[0]);
} else {
  console.log(JSON.stringify({ error: "Usage: node safe-fetch.js <url> or --stdin" }));
}
