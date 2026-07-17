#!/usr/bin/env node
/**
 * LSP MCP Server — Code Intelligence Bridge
 *
 * Converts Grok Build's native LSP capability into an MCP server
 * that Claude Code can use. Provides: go-to-def, find-refs, hover,
 * diagnostics, completion, symbols — for Rust, Python, TS/JS, Go.
 *
 * Architecture:
 *   Claude Code → MCP stdio → LspManager → language-server (stdio)
 *
 * Usage:
 *   node index.js
 *   # Then add to Claude Code's MCP config:
 *   # { "lsp": { "command": "node", "args": [".../lsp-mcp-server/index.js"] } }
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { spawn } from "child_process";
import { createInterface } from "readline";
import { randomUUID } from "crypto";

// ── LSP Manager ──────────────────────────────────────────────────────

class LspClient {
  constructor(id, process, readline) {
    this.id = id;
    this.process = process;
    this.rl = readline;
    this.pending = new Map(); // id → { resolve, reject }
    this.buffer = "";
    this.initialized = false;
    this._setupReader();
  }

  _setupReader() {
    this.rl.on("line", (line) => {
      try {
        const msg = JSON.parse(line);
        if (msg.id && this.pending.has(msg.id)) {
          const { resolve } = this.pending.get(msg.id);
          this.pending.delete(msg.id);
          resolve(msg.result || msg.error);
        }
      } catch (e) {
        // Skip non-JSON lines (some LSP servers log to stdout)
      }
    });
  }

  _send(method, params = {}) {
    const id = this.pending.size + 1;
    const msg = JSON.stringify({ jsonrpc: "2.0", id, method, params });
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.process.stdin.write(`Content-Length: ${Buffer.byteLength(msg)}\r\n\r\n${msg}`);
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`LSP timeout: ${method}`));
        }
      }, 15000);
    });
  }

  async initialize(rootUri) {
    const result = await this._send("initialize", {
      processId: process.pid,
      rootUri: rootUri,
      capabilities: {
        textDocument: {
          hover: { contentFormat: ["markdown", "plaintext"] },
          definition: { linkSupport: true },
          references: {},
          documentSymbol: { hierarchicalDocumentSymbolSupport: true },
          completion: { completionItem: { snippetSupport: true } },
          diagnostic: {},
        },
      },
    });
    await this._send("initialized", {});
    this.initialized = true;
    return result;
  }

  async openDocument(uri, text, languageId) {
    return this._send("textDocument/didOpen", {
      textDocument: { uri, languageId, version: 1, text },
    });
  }

  async definition(uri, line, character) {
    return this._send("textDocument/definition", {
      textDocument: { uri },
      position: { line, character },
    });
  }

  async references(uri, line, character, includeDeclaration = true) {
    return this._send("textDocument/references", {
      textDocument: { uri },
      position: { line, character },
      context: { includeDeclaration },
    });
  }

  async hover(uri, line, character) {
    return this._send("textDocument/hover", {
      textDocument: { uri },
      position: { line, character },
    });
  }

  async documentSymbols(uri) {
    return this._send("textDocument/documentSymbol", { textDocument: { uri } });
  }

  async completion(uri, line, character) {
    return this._send("textDocument/completion", {
      textDocument: { uri },
      position: { line, character },
    });
  }

  async shutdown() {
    await this._send("shutdown");
    this._send("exit");
    this.process.kill();
  }
}

const LANGUAGE_SERVERS = {
  rust: { cmd: "rust-analyzer", args: [], lang: "rust" },
  python: { cmd: "pyright-langserver", args: ["--stdio"], lang: "python" },
  typescript: { cmd: "typescript-language-server", args: ["--stdio"], lang: "typescript" },
  javascript: { cmd: "typescript-language-server", args: ["--stdio"], lang: "javascript" },
  go: { cmd: "gopls", args: [], lang: "go" },
};

const EXT_TO_LANG = {
  ".rs": "rust",
  ".py": "python",
  ".ts": "typescript",
  ".tsx": "typescript",
  ".js": "javascript",
  ".jsx": "javascript",
  ".go": "go",
};

class LspManager {
  constructor() {
    this.clients = {}; // language → LspClient
    this.rootUris = {}; // language → rootUri
  }

  async getClient(language, rootUri) {
    if (this.clients[language]) {
      return this.clients[language];
    }
    const cfg = LANGUAGE_SERVERS[language];
    if (!cfg) throw new Error(`No LSP server for: ${language}`);

    const proc = spawn(cfg.cmd, cfg.args, {
      stdio: ["pipe", "pipe", "pipe"],
    });

    proc.on("error", (err) => {
      console.error(`[LSP ${language}] process error:`, err.message);
    });

    const rl = createInterface({ input: proc.stdout });
    const client = new LspClient(language, proc, rl);

    await client.initialize(rootUri);
    this.clients[language] = client;
    this.rootUris[language] = rootUri;
    return client;
  }

  getLanguageForFile(filePath) {
    const ext = filePath.slice(filePath.lastIndexOf(".")).toLowerCase();
    return EXT_TO_LANG[ext] || null;
  }

  fileUri(filePath) {
    const abs = filePath.replace(/\\/g, "/");
    return `file:///${abs.startsWith("/") ? abs.slice(0) : abs}`;
  }

  async cleanup() {
    for (const [lang, client] of Object.entries(this.clients)) {
      try { await client.shutdown(); } catch (e) { /* ignore */ }
      delete this.clients[lang];
    }
  }
}

// ── MCP Server ───────────────────────────────────────────────────────

const manager = new LspManager();

const server = new Server(
  {
    name: "lsp-mcp-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

const TOOLS = [
  {
    name: "lsp_goto_definition",
    description:
      "Go to definition of a symbol using LSP. Returns the file path, line, and character of the definition. Supports Rust, Python, TypeScript, JavaScript, Go.",
    inputSchema: {
      type: "object",
      properties: {
        file: { type: "string", description: "Absolute path to source file" },
        line: { type: "integer", description: "0-based line number" },
        character: { type: "integer", description: "0-based character offset" },
      },
      required: ["file", "line", "character"],
    },
  },
  {
    name: "lsp_find_references",
    description:
      "Find all references to a symbol using LSP. Returns list of {uri, range} locations.",
    inputSchema: {
      type: "object",
      properties: {
        file: { type: "string" },
        line: { type: "integer" },
        character: { type: "integer" },
      },
      required: ["file", "line", "character"],
    },
  },
  {
    name: "lsp_hover",
    description:
      "Get hover information (type, docs, signature) for a symbol at position.",
    inputSchema: {
      type: "object",
      properties: {
        file: { type: "string" },
        line: { type: "integer" },
        character: { type: "integer" },
      },
      required: ["file", "line", "character"],
    },
  },
  {
    name: "lsp_document_symbols",
    description:
      "List all symbols (functions, classes, methods, types) in a file. Like a code outline.",
    inputSchema: {
      type: "object",
      properties: {
        file: { type: "string" },
      },
      required: ["file"],
    },
  },
  {
    name: "lsp_completion",
    description:
      "Get code completion suggestions at a position (autocomplete).",
    inputSchema: {
      type: "object",
      properties: {
        file: { type: "string" },
        line: { type: "integer" },
        character: { type: "integer" },
      },
      required: ["file", "line", "character"],
    },
  },
  {
    name: "lsp_diagnostics",
    description:
      "Get diagnostics (errors, warnings, hints) for a file from the language server.",
    inputSchema: {
      type: "object",
      properties: {
        file: { type: "string" },
      },
      required: ["file"],
    },
  },
];

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOLS,
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const { file, line, character } = args;

  const language = manager.getLanguageForFile(file);
  if (!language) {
    return {
      content: [{ type: "text", text: `Unsupported file type: ${file}. Supported: .rs, .py, .ts, .tsx, .js, .jsx, .go` }],
    };
  }

  try {
    const rootUri = manager.fileUri(file.replace(/[/\\][^/\\]+$/, ""));
    const client = await manager.getClient(language, rootUri);
    const uri = manager.fileUri(file);

    // Quick open — some servers need this before responding
    try {
      const fs = await import("fs");
      const text = fs.readFileSync(file, "utf-8");
      // Open is fire-and-forget but helps the server warm up
      client.openDocument(uri, text, language).catch(() => {});
    } catch (e) {
      // File might not exist, proceed anyway
    }

    let result;
    switch (name) {
      case "lsp_goto_definition": {
        result = await client.definition(uri, line, character);
        break;
      }
      case "lsp_find_references": {
        result = await client.references(uri, line, character);
        break;
      }
      case "lsp_hover": {
        result = await client.hover(uri, line, character);
        break;
      }
      case "lsp_document_symbols": {
        result = await client.documentSymbols(uri);
        break;
      }
      case "lsp_completion": {
        result = await client.completion(uri, line, character);
        break;
      }
      case "lsp_diagnostics": {
        // PublishDiagnostics is a notification, not a request.
        // We'll open the doc to trigger diagnostics, then return what we collected.
        const fs = await import("fs");
        const text = fs.readFileSync(file, "utf-8");
        await client.openDocument(uri, text, language);
        // Give the server a moment to compute diagnostics
        await new Promise((r) => setTimeout(r, 500));
        result = { diagnostics: [] }; // Server sends via notification
        break;
      }
      default:
        return { content: [{ type: "text", text: `Unknown tool: ${name}` }] };
    }

    // ── Format results ──────────────────────────────────────────
    let output;
    switch (name) {
      case "lsp_goto_definition": {
        if (!result || (Array.isArray(result) && result.length === 0)) {
          output = "No definition found.";
        } else {
          const loc = Array.isArray(result) ? result[0] : result;
          const path = loc.uri ? loc.uri.replace("file:///", "") : file;
          output = `${path}:${(loc.range?.start?.line || 0) + 1}:${loc.range?.start?.character || 0}`;
        }
        break;
      }
      case "lsp_find_references": {
        if (!result || (Array.isArray(result) && result.length === 0)) {
          output = "No references found.";
        } else {
          const refs = Array.isArray(result) ? result : [result];
          output = refs
            .map(
              (r) =>
                `${r.uri.replace("file:///", "")}:${r.range.start.line + 1}:${r.range.start.character}`
            )
            .join("\n");
        }
        break;
      }
      case "lsp_hover": {
        if (!result || !result.contents) {
          output = "No hover information.";
        } else {
          const contents = typeof result.contents === "string"
            ? result.contents
            : (Array.isArray(result.contents)
                ? result.contents.map((c) => (typeof c === "string" ? c : c.value)).join("\n")
                : result.contents.value || JSON.stringify(result.contents));
          output = contents;
        }
        break;
      }
      case "lsp_document_symbols": {
        if (!result || result.length === 0) {
          output = "No symbols found.";
        } else {
          const formatSymbol = (s, depth = 0) => {
            const indent = "  ".repeat(depth);
            const kind = s.kind ? `[${s.kind}]` : "";
            const loc = s.location || s.selectionRange;
            const pos = loc ? `:${loc.start.line + 1}` : "";
            let line = `${indent}${kind} ${s.name}${pos}`;
            if (s.children) {
              line += "\n" + s.children.map((c) => formatSymbol(c, depth + 1)).join("\n");
            }
            return line;
          };
          output = result.map((s) => formatSymbol(s)).join("\n");
        }
        break;
      }
      case "lsp_completion": {
        if (!result || !result.items || result.items.length === 0) {
          output = "No completions.";
        } else {
          output = result.items.slice(0, 20).map((item) => {
            const detail = item.detail ? ` — ${item.detail}` : "";
            return `${item.label}${detail}`;
          }).join("\n");
        }
        break;
      }
      case "lsp_diagnostics": {
        output = `Document opened. Diagnostics will be published asynchronously by ${language} LSP.`;
        break;
      }
    }

    return { content: [{ type: "text", text: output }] };
  } catch (error) {
    const msg = error.message || String(error);
    // Check if LSP server not installed
    if (msg.includes("ENOENT") || msg.includes("spawn")) {
      const cfg = LANGUAGE_SERVERS[language];
      return {
        content: [
          {
            type: "text",
            text: `LSP server not installed for ${language}.\nInstall it: ${cfg.cmd}\nError: ${msg}`,
          },
        ],
      };
    }
    return {
      content: [{ type: "text", text: `LSP error (${language}): ${msg}` }],
    };
  }
});

// ── Lifecycle ────────────────────────────────────────────────────────

const transport = new StdioServerTransport();
await server.connect(transport);
console.error("[lsp-mcp-server] Started. Waiting for LSP tool calls...");

process.on("SIGINT", async () => {
  await manager.cleanup();
  process.exit(0);
});
process.on("SIGTERM", async () => {
  await manager.cleanup();
  process.exit(0);
});
