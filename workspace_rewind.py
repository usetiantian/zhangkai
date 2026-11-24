"""File State Rewind — 回滚工作区到历史状态"""

import json, shutil, time
from pathlib import Path
from datetime import datetime


class FileRewind:
    """文件历史回滚"""

    def __init__(self, workspace_root: Path = Path("D:/qiankun/workspace_root")):
        self.root = workspace_root
        self.history_dir = workspace_root / ".qiankun_history"
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def snapshot(self, file_path: str) -> str:
        """保存文件快照"""
        src = self.root / file_path
        if not src.exists():
            return ""

        snap_id = f"{file_path.replace('/', '_')}_{int(time.time())}"
        dest = self.history_dir / snap_id
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

        # 记录
        index_file = self.history_dir / "index.json"
        index = []
        if index_file.exists():
            index = json.loads(index_file.read_text(encoding="utf-8"))
        index.append({
            "id": snap_id, "file": file_path,
            "timestamp": datetime.now().isoformat(),
            "size": src.stat().st_size,
        })
        index_file.write_text(json.dumps(index[-100:], ensure_ascii=False, indent=2),
                              encoding="utf-8")
        return snap_id

    def list_snapshots(self, file_path: str = None) -> list[dict]:
        """列出快照"""
        index_file = self.history_dir / "index.json"
        if not index_file.exists():
            return []
        index = json.loads(index_file.read_text(encoding="utf-8"))
        if file_path:
            index = [s for s in index if s["file"] == file_path]
        return index[-50:]

    def rewind_to(self, snap_id: str) -> dict:
        """回滚到指定快照"""
        index_file = self.history_dir / "index.json"
        if not index_file.exists():
            return {"ok": False, "error": "无历史记录"}

        index = json.loads(index_file.read_text(encoding="utf-8"))
        snap = next((s for s in index if s["id"] == snap_id), None)
        if not snap:
            return {"ok": False, "error": f"快照不存在: {snap_id}"}

        # 先备份当前版本
        current = self.root / snap["file"]
        if current.exists():
            self.snapshot(snap["file"])  # auto-snapshot before rewind

        # 恢复
        src = self.history_dir / snap_id
        current.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, current)

        return {"ok": True, "rewound_to": snap_id, "file": snap["file"],
                "timestamp": snap["timestamp"]}

    def rewind_last(self, file_path: str) -> dict:
        """回滚到上一个快照"""
        snaps = self.list_snapshots(file_path)
        if len(snaps) < 2:
            return {"ok": False, "error": "至少需要 2 个快照才能回滚"}
        # 倒数第二个 = 上一个版本
        return self.rewind_to(snaps[-2]["id"])
