"""LSP Client — Language Server Protocol 客户端 (移植自 grok-build LspClient)"""

import json, subprocess, threading, time, os
from pathlib import Path
from dataclasses import dataclass, field


REQUEST_TIMEOUT = 15.0  # 秒


@dataclass
class Location:
    """代码位置"""
    uri: str
    range_start_line: int = 0
    range_start_char: int = 0
    range_end_line: int = 0
    range_end_char: int = 0

    def to_dict(self) -> dict:
        return {
            "uri": self.uri,
            "line": self.range_start_line,
            "column": self.range_start_char,
        }


@dataclass
class Diagnostic:
    """诊断信息"""
    message: str
    severity: int  # 1=Error, 2=Warning, 3=Info
    line: int
    column: int
    source: str = ""


class LspClient:
    """
    LSP 客户端 — 连接语言服务器.
    
    移植自 grok-build LspClient:
    - goto_definition: 跳转到定义
    - hover: 悬停信息
    - diagnostics: 诊断/错误
    - 支持 Python (pyright), JavaScript (typescript), 通用
    """

    def __init__(self, language: str = "python"):
        self.language = language
        self._process: subprocess.Popen | None = None
        self._id_counter: int = 0
        self._lock = threading.Lock()

    def _get_server_cmd(self) -> list[str]:
        """获取 LSP server 命令"""
        servers = {
            "python": ["pyright-langserver", "--stdio"],
            "typescript": ["typescript-language-server", "--stdio"],
            "rust": ["rust-analyzer"],
        }
        return servers.get(self.language, ["pyright-langserver", "--stdio"])

    def start(self) -> bool:
        """启动 LSP server"""
        try:
            cmd = self._get_server_cmd()
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self._send_initialize()
            return True
        except FileNotFoundError:
            # LSP server 未安装
            return False
        except Exception:
            return False

    def _send_initialize(self):
        """发送初始化请求"""
        self._send_request("initialize", {
            "processId": os.getpid(),
            "rootUri": f"file:///D:/qiankun",
            "capabilities": {},
        })
        self._send_notification("initialized", {})

    def _send_request(self, method: str, params: dict) -> dict | None:
        """发送 JSON-RPC 请求"""
        with self._lock:
            self._id_counter += 1
            msg = json.dumps({
                "jsonrpc": "2.0",
                "id": self._id_counter,
                "method": method,
                "params": params,
            })
            content = f"Content-Length: {len(msg)}\r\n\r\n{msg}"
            try:
                self._process.stdin.write(content)
                self._process.stdin.flush()
                # 读取响应 (简化: 读一行)
                header = self._process.stdout.readline()
                if "Content-Length:" in header:
                    length = int(header.split(":")[1].strip())
                    self._process.stdout.readline()  # 空行
                    body = self._process.stdout.read(length)
                    return json.loads(body)
            except Exception:
                pass
        return None

    def _send_notification(self, method: str, params: dict):
        """发送通知"""
        with self._lock:
            msg = json.dumps({
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
            })
            content = f"Content-Length: {len(msg)}\r\n\r\n{msg}"
            try:
                self._process.stdin.write(content)
                self._process.stdin.flush()
            except Exception:
                pass

    def goto_definition(self, path: str, line: int = 0, column: int = 0) -> list[Location]:
        """
        跳转到定义 (移植自 grok-build goto_definition).
        """
        uri = f"file:///{path.replace(chr(92), '/')}"
        result = self._send_request("textDocument/definition", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": column},
        })
        if not result or "result" not in result:
            return []
        
        locations = result["result"]
        if isinstance(locations, dict):
            locations = [locations]
        
        locs = []
        for loc in (locations or []):
            rng = loc.get("range", {})
            start = rng.get("start", {})
            end = rng.get("end", {})
            locs.append(Location(
                uri=loc.get("uri", ""),
                range_start_line=start.get("line", 0),
                range_start_char=start.get("character", 0),
                range_end_line=end.get("line", 0),
                range_end_char=end.get("character", 0),
            ))
        return locs

    def hover(self, path: str, line: int, column: int) -> str:
        """悬停信息"""
        uri = f"file:///{path.replace(chr(92), '/')}"
        result = self._send_request("textDocument/hover", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": column},
        })
        if result and "result" in result:
            contents = result["result"].get("contents", {})
            if isinstance(contents, dict):
                return contents.get("value", "")
            return str(contents)
        return ""

    def did_open(self, path: str, text: str):
        """通知 server 打开了文件"""
        uri = f"file:///{path.replace(chr(92), '/')}"
        self._send_notification("textDocument/didOpen", {
            "textDocument": {
                "uri": uri,
                "languageId": self.language,
                "version": 1,
                "text": text,
            },
        })

    def stop(self):
        """关闭"""
        if self._process:
            self._send_notification("exit", {})
            try:
                self._process.terminate()
            except Exception:
                pass


@dataclass
class CodeIntelligence:
    """
    乾坤的代码智能层.
    内置: 基于 AST 的本地分析 (不依赖 LSP server).
    可选: 连接外部 LSP server.
    """
    lsp: LspClient | None = None
    language: str = "python"

    def __post_init__(self):
        if self.language == "python":
            self.lsp = LspClient("python")

    def analyze_file(self, path: str) -> dict:
        """分析 Python 文件 — AST 级"""
        try:
            import ast
            tree = ast.parse(Path(path).read_text(encoding="utf-8"))
            
            functions = []
            classes = []
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append({
                        "name": node.name,
                        "line": node.lineno,
                        "args": [a.arg for a in node.args.args],
                    })
                elif isinstance(node, ast.ClassDef):
                    classes.append({
                        "name": node.name,
                        "line": node.lineno,
                    })
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imports.append(f"{node.module}.{alias.name}")
            
            return {
                "path": path,
                "functions": functions,
                "classes": classes,
                "imports": list(set(imports)),
            }
        except Exception as e:
            return {"error": str(e)}

    def find_references(self, path: str, name: str) -> list[dict]:
        """在文件中查找引用"""
        try:
            import ast
            tree = ast.parse(Path(path).read_text(encoding="utf-8"))
            refs = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id == name:
                    refs.append({"line": node.lineno, "col": node.col_offset})
            return refs
        except Exception:
            return []
