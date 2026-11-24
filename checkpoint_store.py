"""Checkpoint Store — 检查点持久化 (移植自 grok-build CheckpointStore.persist)"""

import os, json, threading
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class RewindCheckpoint:
    """回滚检查点"""
    prompt_index: int
    session_id: str = ""
    file_states: dict = field(default_factory=dict)  # path → hash
    timestamp: str = ""


class CheckpointStore:
    """
    检查点存储 — 带容量上限的环形持久化.
    
    移植自 grok-build CheckpointStore:
    - push: 带保留窗口, 自动淘汰最旧
    - persist: I/O 锁, 容量管理
    - evict: 删除超出容量的最旧检查点
    """
    def __init__(self, directory: Path = None, capacity: int = 10):
        self.dir = directory or Path("D:/qiankun/data/checkpoints")
        self.cap = capacity
        self.cache: dict[int, RewindCheckpoint] = {}
        self._io_lock = threading.Lock()

    def persist(self, checkpoint: RewindCheckpoint):
        """持久化检查点 (移植自 grok-build persist)"""
        with self._io_lock:
            prompt_index = checkpoint.prompt_index

            # 保留窗口检查: 如果已满且新索引比最旧还小, 跳过
            if len(self.cache) >= self.cap:
                if prompt_index not in self.cache:
                    oldest = min(self.cache.keys()) if self.cache else None
                    if oldest is not None and prompt_index < oldest:
                        return

            # 写入文件
            try:
                self.dir.mkdir(parents=True, exist_ok=True)
                path = self.dir / f"checkpoint_{prompt_index}.json"
                path.write_text(json.dumps({
                    "prompt_index": checkpoint.prompt_index,
                    "session_id": checkpoint.session_id,
                    "file_states": checkpoint.file_states,
                    "timestamp": checkpoint.timestamp,
                }, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                print(f"[Checkpoint] 写入失败: {e}")
                return

            # 插入缓存并淘汰
            self.cache[prompt_index] = checkpoint
            evicted = []

            while len(self.cache) > self.cap:
                oldest = min(self.cache.keys())
                evicted.append(oldest)
                del self.cache[oldest]

            # 删除淘汰的检查点文件
            for idx in evicted:
                try:
                    (self.dir / f"checkpoint_{idx}.json").unlink()
                except Exception:
                    pass

    def restore(self, prompt_index: int = None) -> RewindCheckpoint | None:
        """恢复检查点"""
        if prompt_index and prompt_index in self.cache:
            return self.cache[prompt_index]
        # 从最新恢复
        if self.cache:
            latest = max(self.cache.keys())
            return self.cache[latest]
        return None

    def stats(self) -> dict:
        return {
            "stored": len(self.cache),
            "capacity": self.cap,
            "oldest": min(self.cache.keys()) if self.cache else None,
            "newest": max(self.cache.keys()) if self.cache else None,
        }
