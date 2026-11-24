"""Hunk Tracker — 文件变更追踪 (移植自 grok-build xai-hunk-tracker)"""

import difflib, hashlib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Hunk:
    """一个 diff 块"""
    old_start: int = 0
    old_count: int = 0
    new_start: int = 0
    new_count: int = 0
    old_lines: list = field(default_factory=list)
    new_lines: list = field(default_factory=list)

    def to_unified(self) -> str:
        lines = [f"@@ -{self.old_start},{self.old_count} +{self.new_start},{self.new_count} @@"]
        for l in self.old_lines:
            lines.append(f"-{l}")
        for l in self.new_lines:
            lines.append(f"+{l}")
        return "\n".join(lines)


@dataclass
class HunkRecord:
    """一次文件变更记录"""
    file_path: str
    hunks: list = field(default_factory=list)
    before_hash: str = ""
    after_hash: str = ""
    tool_name: str = ""       # 哪个工具造成的变更
    turn_id: str = ""         # 哪一轮对话

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "before_hash": self.before_hash,
            "after_hash": self.after_hash,
            "tool_name": self.tool_name,
            "turn_id": self.turn_id,
            "hunks": [h.to_unified() for h in self.hunks],
        }


class HunkTracker:
    """
    文件变更追踪器.
    
    移植自 grok-build HunkTrackerActor:
    - handle_file_change: 检测文件变更
    - process_file_change: 计算 diff, 生成 hunks
    - apply_file_action: 记录到历史
    """
    def __init__(self):
        self.records: list[HunkRecord] = []
        self._file_snapshots: dict[str, str] = {}  # path → hash

    def snapshot(self, file_path: str) -> str:
        """保存文件快照"""
        try:
            content = Path(file_path).read_text(encoding="utf-8")
            h = hashlib.sha256(content.encode()).hexdigest()[:16]
            self._file_snapshots[file_path] = h
            return h
        except Exception:
            return ""

    def handle_file_change(self, file_path: str, new_content: str,
                           tool_name: str = "", turn_id: str = "") -> HunkRecord | None:
        """
        处理文件变更 — 对比快照, 生成 hunks.
        移植自 grok-build handle_file_change + process_file_change.
        """
        old_hash = self._file_snapshots.get(file_path, "")
        new_hash = hashlib.sha256(new_content.encode()).hexdigest()[:16]

        if old_hash == new_hash:
            return None  # 无变更

        # 获取旧内容
        old_content = ""
        try:
            old_content = Path(file_path).read_text(encoding="utf-8")
        except Exception:
            pass

        # 计算 hunks
        hunks = self._compute_hunks(old_content, new_content)

        record = HunkRecord(
            file_path=file_path,
            hunks=hunks,
            before_hash=old_hash,
            after_hash=new_hash,
            tool_name=tool_name,
            turn_id=turn_id,
        )
        self.records.append(record)

        # 更新快照
        self._file_snapshots[file_path] = new_hash

        return record

    def _compute_hunks(self, old_text: str, new_text: str) -> list[Hunk]:
        """计算 unified diff hunks"""
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            old_lines, new_lines, lineterm="", n=3))
        
        hunks = []
        current = Hunk()
        old_pos = new_pos = 0

        for line in diff:
            if line.startswith("@@"):
                if current.old_lines or current.new_lines:
                    hunks.append(current)
                current = Hunk()
            elif line.startswith("-") and not line.startswith("---"):
                current.old_lines.append(line[1:])
                current.old_count += 1
            elif line.startswith("+") and not line.startswith("+++"):
                current.new_lines.append(line[1:])
                current.new_count += 1

        if current.old_lines or current.new_lines:
            hunks.append(current)

        return hunks

    def format_unified_diff(self, record: HunkRecord) -> str:
        """生成 unified diff 文本"""
        lines = [f"--- {record.file_path}", f"+++ {record.file_path}"]
        for h in record.hunks:
            lines.append(h.to_unified())
        return "\n".join(lines)

    def get_changes_for_file(self, file_path: str) -> list[HunkRecord]:
        return [r for r in self.records if r.file_path == file_path]

    def recent_changes(self, limit: int = 20) -> list[dict]:
        return [r.to_dict() for r in self.records[-limit:]]
