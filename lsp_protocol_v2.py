"""Full LSP Protocol v2 — 完整 LSP 客户端能力 + 所有方法 (移植自 grok-build LspClient)"""

import json, threading, time
from dataclasses import dataclass, field
from enum import Enum


class MarkupKind(Enum):
    PLAIN_TEXT = "plaintext"
    MARKDOWN = "markdown"


@dataclass
class TextDocumentSyncCapabilities:
    dynamic_registration: bool = False
    will_save: bool = False
    will_save_wait_until: bool = False
    did_save: bool = True

    def to_dict(self) -> dict:
        return {
            "dynamicRegistration": self.dynamic_registration,
            "willSave": self.will_save,
            "willSaveWaitUntil": self.will_save_wait_until,
            "didSave": self.did_save,
        }


@dataclass
class GotoCapability:
    dynamic_registration: bool = False
    link_support: bool = False

    def to_dict(self) -> dict:
        return {
            "dynamicRegistration": self.dynamic_registration,
            "linkSupport": self.link_support,
        }


@dataclass
class ReferenceCapability:
    dynamic_registration: bool = False

    def to_dict(self) -> dict:
        return {"dynamicRegistration": self.dynamic_registration}


@dataclass
class PublishDiagnosticsCapability:
    related_information: bool = True

    def to_dict(self) -> dict:
        return {"relatedInformation": self.related_information}


@dataclass
class HoverCapability:
    dynamic_registration: bool = False
    content_format: list[str] = field(default_factory=lambda: ["plaintext"])

    def to_dict(self) -> dict:
        return {
            "dynamicRegistration": self.dynamic_registration,
            "contentFormat": self.content_format,
        }


@dataclass
class CompletionCapability:
    dynamic_registration: bool = False
    snippet_support: bool = False

    def to_dict(self) -> dict:
        return {
            "dynamicRegistration": self.dynamic_registration,
            "completionItem": {"snippetSupport": self.snippet_support},
        }


@dataclass
class ClientCapabilities:
    """
    客户端能力 (移植自 grok-build client_capabilities).
    """
    text_document_sync: TextDocumentSyncCapabilities = field(default_factory=TextDocumentSyncCapabilities)
    definition: GotoCapability = field(default_factory=GotoCapability)
    references: ReferenceCapability = field(default_factory=ReferenceCapability)
    hover: HoverCapability = field(default_factory=HoverCapability)
    completion: CompletionCapability = field(default_factory=CompletionCapability)
    publish_diagnostics: PublishDiagnosticsCapability = field(default_factory=PublishDiagnosticsCapability)

    def to_initialize_params(self, root_uri: str = "file:///D:/qiankun") -> dict:
        return {
            "processId": None,
            "rootUri": root_uri,
            "capabilities": {
                "textDocument": {
                    "synchronization": self.text_document_sync.to_dict(),
                    "definition": self.definition.to_dict(),
                    "references": self.references.to_dict(),
                    "hover": self.hover.to_dict(),
                    "completion": self.completion.to_dict(),
                    "publishDiagnostics": self.publish_diagnostics.to_dict(),
                },
            },
        }


class LspOperations:
    """所有 LSP 操作的统一入口"""

    @staticmethod
    def definition(rpc, uri: str, line: int, col: int) -> list[dict]:
        result = rpc.request("textDocument/definition", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": col},
        })
        if result and "result" in result and result["result"]:
            locs = result["result"]
            if isinstance(locs, dict): locs = [locs]
            return [{
                "uri": l.get("uri", ""),
                "line": l.get("range", {}).get("start", {}).get("line", 0),
                "character": l.get("range", {}).get("start", {}).get("character", 0),
            } for l in locs]
        return []

    @staticmethod
    def hover(rpc, uri: str, line: int, col: int) -> str:
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

    @staticmethod
    def references(rpc, uri: str, line: int, col: int,
                   include_declaration: bool = True) -> list[dict]:
        result = rpc.request("textDocument/references", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": col},
            "context": {"includeDeclaration": include_declaration},
        })
        if result and "result" in result:
            return [{
                "uri": l.get("uri", ""),
                "line": l.get("range", {}).get("start", {}).get("line", 0),
            } for l in result["result"]]
        return []

    @staticmethod
    def completion(rpc, uri: str, line: int, col: int) -> list[dict]:
        result = rpc.request("textDocument/completion", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": col},
        })
        if result and "result" in result:
            items = result["result"].get("items", result["result"])
            if isinstance(items, list):
                return [{
                    "label": i.get("label", ""),
                    "kind": i.get("kind", 0),
                    "detail": i.get("detail", ""),
                } for i in items[:20]]
        return []

    @staticmethod
    def rename(rpc, uri: str, line: int, col: int,
               new_name: str) -> dict:
        result = rpc.request("textDocument/rename", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": col},
            "newName": new_name,
        })
        if result and "result" in result:
            changes = result["result"].get("changes", {})
            return {"ok": True, "changes": changes}
        return {"ok": False}

    @staticmethod
    def document_symbol(rpc, uri: str) -> list[dict]:
        result = rpc.request("textDocument/documentSymbol", {
            "textDocument": {"uri": uri},
        })
        if result and "result" in result:
            return [{
                "name": s.get("name", ""),
                "kind": s.get("kind", 0),
                "line": s.get("range", {}).get("start", {}).get("line", 0),
            } for s in result["result"]]
        return []

    @staticmethod
    def formatting(rpc, uri: str) -> str:
        result = rpc.request("textDocument/formatting", {
            "textDocument": {"uri": uri},
            "options": {"tabSize": 4, "insertSpaces": True},
        })
        if result and "result" in result:
            edits = result["result"]
            if isinstance(edits, list) and edits:
                return edits[0].get("newText", "")
        return ""

    @staticmethod
    def diagnostic(rpc, uri: str) -> list[dict]:
        result = rpc.request("textDocument/diagnostic", {
            "textDocument": {"uri": uri},
        })
        if result and "result" in result:
            return [{
                "message": i.get("message", ""),
                "severity": i.get("severity", 3),
                "line": i.get("range", {}).get("start", {}).get("line", 0),
                "source": i.get("source", ""),
                "code": i.get("code", ""),
            } for i in result["result"].get("items", [])]
        return []
