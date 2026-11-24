"""LSP Manager — 完整 LSP 管理 (移植自 grok-build LspManager + bootstrap_lsp)"""

import json, subprocess, threading, time, os
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum


REQUEST_TIMEOUT = 15.0


class LspServerStatus(Enum):
    STARTING = "starting"
    READY = "ready"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class LspServerInfo:
    """LSP Server 信息"""
    name: str
    language: str
    command: list
    process: subprocess.Popen | None = None
    status: LspServerStatus = LspServerStatus.STARTING
    capabilities: dict = field(default_factory=dict)
    diagnostics: dict[str, list] = field(default_factory=dict)  # path → diagnostics

    def restartable(self) -> bool:
        return self.status in (LspServerStatus.ERROR, LspServerStatus.STOPPED)


class LspJsonRpc:
    """JSON-RPC 2.0 传输层"""
    def __init__(self, process: subprocess.Popen):
        self._proc = process
        self._id = 0
        self._lock = threading.Lock()

    def request(self, method: str, params: dict = None) -> dict | None:
        with self._lock:
            self._id += 1
            msg = json.dumps({
                "jsonrpc": "2.0", "id": self._id,
                "method": method, "params": params or {},
            })
            return self._send(msg)

    def notify(self, method: str, params: dict = None):
        with self._lock:
            msg = json.dumps({
                "jsonrpc": "2.0",
                "method": method, "params": params or {},
            })
            self._send(msg, expect_response=False)

    def _send(self, msg: str, expect_response: bool = True) -> dict | None:
        try:
            content = f"Content-Length: {len(msg)}\r\n\r\n{msg}"
            self._proc.stdin.write(content)
            self._proc.stdin.flush()

            if not expect_response:
                return None

            header = self._proc.stdout.readline()
            if "Content-Length:" in header:
                length = int(header.split(":")[1].strip())
                self._proc.stdout.readline()
                body = self._proc.stdout.read(length)
                return json.loads(body)
        except Exception:
            pass
        return None


class LspManager:
    """
    LSP 管理器 — 多 Server 协调.
    
    移植自 grok-build LspManager:
    - 多语言 Server 管理
    - bootstrap 启动流程
    - 文件变更通知
    - 诊断收集
    - 重启监控
    """

    def __init__(self):
        self.clients: dict[str, LspServerInfo] = {}
        self._open_files: dict[str, str] = {}  # path → language

    def add_server(self, name: str, language: str, command: list):
        """注册 Server"""
        self.clients[name] = LspServerInfo(
            name=name, language=language, command=command)

    def ensure_initialized(self):
        """确保所有 Server 初始化"""
        for name, info in list(self.clients.items()):
            if info.status == LspServerStatus.READY:
                continue
            try:
                proc = subprocess.Popen(
                    info.command,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True,
                )
                info.process = proc
                rpc = LspJsonRpc(proc)

                # Initialize
                result = rpc.request("initialize", {
                    "processId": os.getpid(),
                    "rootUri": "file:///D:/qiankun",
                    "capabilities": {
                        "textDocument": {
                            "hover": {"contentFormat": ["markdown", "plaintext"]},
                            "definition": {"linkSupport": True},
                            "references": {},
                            "completion": {},
                            "diagnostic": {},
                        },
                    },
                })
                if result and "result" in result:
                    info.capabilities = result["result"].get("capabilities", {})
                    info.status = LspServerStatus.READY
                    rpc.notify("initialized", {})

                    # 打开已注册的文件
                    for path, lang in self._open_files.items():
                        if lang == info.language:
                            self._did_open(rpc, path, lang)

            except FileNotFoundError:
                info.status = LspServerStatus.ERROR
            except Exception as e:
                info.status = LspServerStatus.ERROR

    def _did_open(self, rpc: LspJsonRpc, path: str, language: str):
        """通知 Server 文件已打开"""
        try:
            text = Path(path).read_text(encoding="utf-8")
            uri = f"file:///{path.replace(chr(92), '/')}"
            rpc.notify("textDocument/didOpen", {
                "textDocument": {
                    "uri": uri, "languageId": language,
                    "version": 1, "text": text,
                },
            })
        except Exception:
            pass

    def notify_file_changed(self, path: str, content: str):
        """通知文件变更"""
        uri = f"file:///{path.replace(chr(92), '/')}"
        for info in self.clients.values():
            if info.status != LspServerStatus.READY or not info.process:
                continue
            rpc = LspJsonRpc(info.process)
            rpc.notify("textDocument/didChange", {
                "textDocument": {
                    "uri": uri, "version": int(time.time()),
                },
                "contentChanges": [{"text": content}],
            })

    def goto_definition(self, path: str, line: int, col: int,
                        language: str = "python") -> list[dict]:
        """跳转到定义"""
        uri = f"file:///{path.replace(chr(92), '/')}"
        for info in self.clients.values():
            if info.language == language and info.status == LspServerStatus.READY and info.process:
                rpc = LspJsonRpc(info.process)
                result = rpc.request("textDocument/definition", {
                    "textDocument": {"uri": uri},
                    "position": {"line": line, "character": col},
                })
                if result and "result" in result:
                    locations = result["result"]
                    if isinstance(locations, dict):
                        locations = [locations]
                    return [self._parse_location(loc) for loc in (locations or [])]
        return []

    def hover(self, path: str, line: int, col: int,
              language: str = "python") -> str:
        """悬停信息"""
        uri = f"file:///{path.replace(chr(92), '/')}"
        for info in self.clients.values():
            if info.language == language and info.status == LspServerStatus.READY and info.process:
                rpc = LspJsonRpc(info.process)
                result = rpc.request("textDocument/hover", {
                    "textDocument": {"uri": uri},
                    "position": {"line": line, "character": col},
                })
                if result and "result" in result:
                    contents = result["result"].get("contents", {})
                    if isinstance(contents, dict):
                        return contents.get("value", "")
                    if isinstance(contents, list):
                        return "\n".join(
                            c.get("value", str(c)) if isinstance(c, dict) else str(c)
                            for c in contents
                        )
                    return str(contents)
        return ""

    def references(self, path: str, line: int, col: int,
                   language: str = "python") -> list[dict]:
        """查找引用"""
        uri = f"file:///{path.replace(chr(92), '/')}"
        for info in self.clients.values():
            if info.language == language and info.status == LspServerStatus.READY and info.process:
                rpc = LspJsonRpc(info.process)
                result = rpc.request("textDocument/references", {
                    "textDocument": {"uri": uri},
                    "position": {"line": line, "character": col},
                    "context": {"includeDeclaration": True},
                })
                if result and "result" in result:
                    return [self._parse_location(loc) for loc in result["result"]]
        return []

    def collect_diagnostics(self, path: str,
                            language: str = "python") -> list[dict]:
        """收集诊断信息"""
        uri = f"file:///{path.replace(chr(92), '/')}"
        diagnostics = []
        for info in self.clients.values():
            if info.language == language and info.status == LspServerStatus.READY and info.process:
                rpc = LspJsonRpc(info.process)
                result = rpc.request("textDocument/diagnostic", {
                    "textDocument": {"uri": uri},
                })
                if result and "result" in result:
                    for item in result["result"].get("items", []):
                        diagnostics.append({
                            "message": item.get("message", ""),
                            "severity": item.get("severity", 3),
                            "line": item.get("range", {}).get("start", {}).get("line", 0),
                            "source": item.get("source", ""),
                        })
        return diagnostics

    def restartable_servers(self) -> list[str]:
        """可重启的 Server"""
        return [n for n, i in self.clients.items() if i.restartable()]

    def shutdown(self):
        """关闭所有 Server"""
        for info in self.clients.values():
            if info.process:
                try:
                    rpc = LspJsonRpc(info.process)
                    rpc.request("shutdown")
                    rpc.notify("exit")
                    info.process.terminate()
                except Exception:
                    pass

    @staticmethod
    def _parse_location(loc: dict) -> dict:
        rng = loc.get("range", {})
        start = rng.get("start", {})
        return {
            "uri": loc.get("uri", ""),
            "line": start.get("line", 0),
            "character": start.get("character", 0),
        }
