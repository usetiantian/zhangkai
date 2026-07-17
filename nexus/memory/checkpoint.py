"""Checkpoint — resume恢复，断了重连不丢状态"""
import json, os, time
class Checkpoint:
    def __init__(self, path: str = None):
        self.path = path or os.path.join(os.path.dirname(__file__), "..", "data", "checkpoint.json")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def save(self, state: dict):
        state["saved_at"] = time.time()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)

    def load(self) -> dict:
        if not os.path.exists(self.path):
            return {"status": "no_checkpoint"}
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def exists(self) -> bool:
        return os.path.exists(self.path)
