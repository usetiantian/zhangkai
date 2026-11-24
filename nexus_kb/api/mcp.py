"""
MCP Server — stdio JSON-RPC，供 Claude Code 等 Agent 调用

工具:
  kb_search(query, k=10)           → 搜索知识库
  kb_ingest(path)                  → 摄入文件
  kb_ingest_text(text, source)     → 摄入文本
  kb_status()                      → 知识库状态
  kb_graph_neighbors(node_id)      → 图谱邻居
  kb_rescan()                      → 重新扫描数据湖
  kb_detect_communities()          → 社区检测

MCP 配置 (mcp_config.json):
{
  "mcpServers": {
    "nexus-kb": {
      "command": "python",
      "args": ["-m", "nexus_kb.api.mcp", "--data-dir", "~/nexus_library"]
    }
  }
}
"""

import sys, os, json, logging

logger = logging.getLogger("nexus_kb.mcp")

_kb = None


def handle_request(request: dict) -> dict:
    """处理单个 JSON-RPC 请求。"""
    method = request.get("method", "")
    req_id = request.get("id")

    if method == "tools/list":
        return _tool_list(req_id)
    if method == "tools/call":
        return _tool_call(request.get("params", {}), req_id)
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "nexus-kb", "version": "0.1.0"},
            "capabilities": {"tools": {}}
        }}
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}


def _tool_list(req_id):
    return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": [
        {"name": "kb_search", "description": "Search the knowledge base. Returns ranked results with scores and source files.",
         "inputSchema": {"type": "object", "properties": {
             "query": {"type": "string", "description": "Search query"},
             "k": {"type": "integer", "description": "Max results", "default": 10}
         }, "required": ["query"]}},
        {"name": "kb_ingest", "description": "Ingest a file into the knowledge base. Supports PDF/Word/PPT/Excel/Markdown/text/code.",
         "inputSchema": {"type": "object", "properties": {
             "path": {"type": "string", "description": "Absolute path to file"}
         }, "required": ["path"]}},
        {"name": "kb_ingest_text", "description": "Ingest raw text into the knowledge base.",
         "inputSchema": {"type": "object", "properties": {
             "text": {"type": "string", "description": "Text content"},
             "source": {"type": "string", "description": "Source identifier (e.g. filename)"}
         }, "required": ["text", "source"]}},
        {"name": "kb_status", "description": "Get knowledge base status: node count, edge count, document count, ingest count.",
         "inputSchema": {"type": "object", "properties": {}}},
        {"name": "kb_graph_neighbors", "description": "Get neighbors of a node in the knowledge graph.",
         "inputSchema": {"type": "object", "properties": {
             "node_id": {"type": "string", "description": "Node ID (filepath or entity name)"}
         }, "required": ["node_id"]}},
        {"name": "kb_rescan", "description": "Rescan the entire data lake directory and ingest new/changed files.",
         "inputSchema": {"type": "object", "properties": {}}},
        {"name": "kb_detect_communities", "description": "Run Louvain community detection on the knowledge graph.",
         "inputSchema": {"type": "object", "properties": {}}},
        {"name": "kb_web_search", "description": "Search the web and optionally ingest results into the knowledge base.",
         "inputSchema": {"type": "object", "properties": {
             "query": {"type": "string", "description": "Search query"},
             "max_results": {"type": "integer", "description": "Max results", "default": 5},
             "ingest": {"type": "boolean", "description": "Whether to ingest results into KB", "default": False}
         }, "required": ["query"]}},
        {"name": "kb_web_fetch", "description": "Fetch and extract text content from a URL.",
         "inputSchema": {"type": "object", "properties": {
             "url": {"type": "string", "description": "URL to fetch"}
         }, "required": ["url"]}},
    ]}}


def _tool_call(params: dict, req_id):
    name = params.get("name", "")
    args = params.get("arguments", {})
    result = ""

    try:
        if name == "kb_search":
            r = _kb.search(args.get("query", ""), args.get("k", 10))
            result = json.dumps(r, ensure_ascii=False, indent=2)
        elif name == "kb_ingest":
            r = _kb.ingest_file(args.get("path", ""))
            result = json.dumps(r, ensure_ascii=False)
        elif name == "kb_ingest_text":
            _kb.ingest_text(args.get("text", ""), args.get("source", "mcp"))
            result = json.dumps({"status": "ok"})
        elif name == "kb_status":
            result = json.dumps(_kb.status(), ensure_ascii=False)
        elif name == "kb_graph_neighbors":
            r = _kb.graph_neighbors(args.get("node_id", ""))
            result = json.dumps(r, ensure_ascii=False, indent=2)
        elif name == "kb_rescan":
            r = _kb.rescan()
            result = json.dumps({"count": len(r)}, ensure_ascii=False)
        elif name == "kb_detect_communities":
            r = _kb.detect_communities()
            result = json.dumps(r, ensure_ascii=False)
        elif name == "kb_web_search":
            try:
                if args.get("ingest"):
                    r = _kb.web_search_and_ingest(args["query"], args.get("max_results", 3))
                else:
                    r = _kb.web_search(args["query"], args.get("max_results", 5))
            except Exception as e:
                r = {"error": str(e), "results": []}
            result = json.dumps(r, ensure_ascii=False, indent=2)
        elif name == "kb_web_fetch":
            r = _kb.web_fetch(args["url"])
            result = json.dumps(r, ensure_ascii=False)
        else:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown tool: {name}"}}
    except Exception as e:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(e)}}

    return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": result}]}}


def serve(data_dir: str = None):
    """MCP stdio 主循环。"""
    global _kb
    from nexus_kb import KnowledgeBase
    _kb = KnowledgeBase(data_dir)

    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            response = handle_request(request)
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}) + "\n")
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"MCP error: {e}")


def set_kb(kb):
    """注入 KnowledgeBase 实例（测试用）。"""
    global _kb
    _kb = kb
