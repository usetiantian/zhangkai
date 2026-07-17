# CC Extended Capabilities (from Grok Build Conversion)

## 1. PLAN MODE — Enter before large changes

When user asks for a complex change, use this workflow:

```
Phase 0: PLAN — summarize what will be done, files affected, risks
Phase 1: SURVEY — read all relevant files before touching code
Phase 2: EXECUTE — make changes, one file at a time, verify each
Phase 3: REVIEW — git diff, verify no regressions
Phase 4: EXIT PLAN — summarize what was done, what to verify
```

Invocation: user says "plan mode" or CC detects multi-file change.
Signal: prefix messages with `[PLAN]`, `[SURVEY]`, `[EXEC]`, `[REVIEW]`.

## 2. CODE GRAPH — Query project structure

Codebase-memory is indexed. For any repo:
- `search_graph` for function/class lookup (BM25 + semantic)
- `query_graph` for Cypher queries (dependencies, call chains, complexity)
- `trace_path` for call/data-flow tracing
- `get_architecture` for high-level structure with Leiden clusters

**Default**: Before modifying any function, trace its callers (`trace_path` direction=outbound depth=1).

## 3. ripgrep FIRST

Always prefer ripgrep over grep for code search:
```
rg --type rust "pattern" path/           # language-aware
rg -l "pattern"                          # file names only
rg -C 3 "pattern"                        # 3 lines context
rg -g "!node_modules/" "pattern" .       # exclude dirs
rg --json "pattern"                      # structured output
```

## 4. MEMORY — Persistent session knowledge

Use the `memory` MCP server for long-lived project knowledge:
- `search_nodes`: find what we already know
- `create_entities`: record new findings (architecture decisions, bug patterns, fixes)
- `create_relations`: connect entities

**When to record**: after any architecture decision, major bug fix, or pattern discovery.

## 5. SSRF PROTECTION — Safe web fetching

When fetching URLs, validate:
- No internal IPs (127.0.0.1, 10.x, 172.16-31.x, 192.168.x)
- No file:// protocol
- No localhost hostnames
- URL length < 2048 chars

## 6. SCHEDULER — Background task management

For long-running tasks (builds, indexing, training):
1. Start in background: `Bash(run_in_background=true)`
2. Check status: `Bash` to tail logs
3. Notify on completion: tail -f with timeout

## 7. CODE INTELLIGENCE — LSP via MCP

Available LSP tools via `lsp-mcp-server`:
- `lsp_goto_definition`: jump to definition
- `lsp_find_references`: find all usages
- `lsp_hover`: type/docs on hover
- `lsp_document_symbols`: file outline/symbols
- `lsp_completion`: autocomplete suggestions

Requires: rust-analyzer, pyright, typescript-language-server, gopls installed.

## 8. SKILLS — Reusable capability modules

Loaded from `./skills/` directory. Each skill is a markdown file with:
- `# Skill: Name` header
- `## Trigger` — when to activate
- `## Workflow` — step-by-step
- `## Tools` — which tools to use
- `## Output` — expected result format

Active skills:
- `./skills/code-audit.md` — Five-step quality audit
- `./skills/debug-root-cause.md` — Chase three layers before fixing
- `./skills/architecture-review.md` — Cluster analysis + ADR
