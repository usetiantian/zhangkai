"""
投机执行引擎 — 借鉴Claude Code copyahead overlay模式
AI想做的事先在覆盖层预执行 → 用户确认 → 生效；拒绝 → 零副作用
"""
import os, shutil, logging, json
logger = logging.getLogger("nexus.speculative")

class SpeculativeExecutor:
    """投机执行——预演AI的操作，确认后才生效。"""

    def __init__(self, overlay_dir: str = None):
        self.overlay_dir = overlay_dir or os.path.join(
            os.path.dirname(__file__), "..", "data", "speculative"
        )
        os.makedirs(self.overlay_dir, exist_ok=True)
        self.pending = {}  # {id: {type, preview, real_path, overlay_path}}

    def preview_file_write(self, path: str, content: str) -> str:
        """
        预演文件写入。
        返回预览ID——展示给用户确认。
        """
        op_id = str(len(self.pending) + 1)
        overlay_path = os.path.join(self.overlay_dir, f"preview_{op_id}.txt")
        with open(overlay_path, "w", encoding="utf-8") as f:
            f.write(f"## 投机预览 #{op_id}\n")
            f.write(f"## 目标文件: {path}\n")
            f.write(f"## 预览内容:\n\n{content}\n")
            f.write(f"\n## 确认后将写入真实文件: {path}")

        self.pending[op_id] = {
            "type": "file_write",
            "path": path,
            "overlay_path": overlay_path,
            "content": content,
        }
        logger.info(f"Speculative preview #{op_id}: {path}")
        return op_id

    def preview_config_change(self, key: str, old_value: str, new_value: str) -> str:
        """预演配置修改。"""
        op_id = str(len(self.pending) + 1)
        self.pending[op_id] = {
            "type": "config_change",
            "key": key,
            "old": old_value,
            "new": new_value,
        }
        return op_id

    def confirm(self, op_id: str) -> bool:
        """用户确认——真正执行。"""
        if op_id not in self.pending:
            logger.warning(f"Speculative op {op_id} not found")
            return False

        op = self.pending[op_id]
        if op["type"] == "file_write":
            os.makedirs(os.path.dirname(op["path"]) or ".", exist_ok=True)
            with open(op["path"], "w", encoding="utf-8") as f:
                f.write(op["content"])
            logger.info(f"Speculative #{op_id} COMMITTED: {op['path']}")

        elif op["type"] == "config_change":
            logger.info(f"Speculative #{op_id} COMMITTED: {op['key']}={op['new']}")

        # 清理覆盖层
        if "overlay_path" in op and os.path.exists(op["overlay_path"]):
            os.remove(op["overlay_path"])

        del self.pending[op_id]
        return True

    def reject(self, op_id: str):
        """用户拒绝——清理覆盖层，零副作用。"""
        if op_id in self.pending:
            op = self.pending[op_id]
            if "overlay_path" in op and os.path.exists(op["overlay_path"]):
                os.remove(op["overlay_path"])
            del self.pending[op_id]
            logger.info(f"Speculative #{op_id} REJECTED — zero side effects")

    def list_pending(self) -> list:
        return [{"id": k, "type": v["type"], "path": v.get("path", v.get("key", ""))}
                for k, v in self.pending.items()]

    def count(self) -> int:
        return len(self.pending)
