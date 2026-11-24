"""
LoRA 微调 — 模型自己决定一切
不硬编码阈值，不硬编码时间。模型评估 → 决策 → 执行。
"""

import os, time, json, logging

logger = logging.getLogger("nexus_kb.trigger")


class TrainingTrigger:
    """模型自己决定是否训练、训什么、什么时候训。"""

    def __init__(self, knowledge_base):
        self.kb = knowledge_base
        self._state_path = os.path.join(self.kb.index_dir, "training_state.json")
        self._state = self._load()

    def _load(self):
        try:
            if os.path.exists(self._state_path):
                with open(self._state_path) as f:
                    return json.load(f)
        except:
            pass
        return {"last_time": 0, "last_count": 0, "history": []}

    def _save(self):
        try:
            tmp = self._state_path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self._state, f)
            os.replace(tmp, self._state_path)
        except:
            pass

    def ask_model(self) -> dict:
        """模型自省：要不要训练？"""
        from ..engine.lm_client import LMStudioClient
        lm = LMStudioClient()

        stats = self.kb.rag.stats()
        new = stats["docs"] - self._state.get("last_count", 0)
        days = (time.time() - self._state.get("last_time", 0)) / 86400

        top = [d for d in os.listdir(self.kb.data_dir)
               if os.path.isdir(os.path.join(self.kb.data_dir, d)) and not d.startswith(".")][:10]

        prompt = f"""判断是否需要微调。当前: {stats['docs']}篇文档(新增{new}篇), 距上次{days:.0f}天, 领域: {', '.join(top)}。
返回JSON: {{"should_train":bool,"focus":"重点","count":数字}}"""

        r = lm.ask(prompt, system="你是训练策略专家。只返回JSON。")
        try:
            r = r.strip()
            if r.startswith("```"): r = r.split("```")[1]
            if r.lower().startswith("json"): r = r[4:]
            return json.loads(r)
        except:
            return {"should_train": new > 100, "focus": "全领域", "count": min(new, 200)}

    def should_train(self) -> bool:
        return self.ask_model().get("should_train", False)

    def train(self) -> dict:
        d = self.ask_model()
        if not d.get("should_train"):
            return {"status": "skipped", "reason": "模型判断不需要"}

        from .lora import LoRATrainer
        n = min(d.get("count", 200), len(self.kb.rag._docs))
        texts = [doc["text"][:800] for doc in self.kb.rag._docs[:n] if doc.get("text")]

        if len(texts) < 10:
            return {"status": "skipped", "reason": "数据不足"}

        trainer = LoRATrainer()
        trainer.train(texts, epochs=2)

        self._state["last_time"] = time.time()
        self._state["last_count"] = self.kb.rag.stats()["docs"]
        self._state["history"].append({"time": time.time(), "focus": d.get("focus",""), "samples": len(texts)})
        self._save()
        return {"status": "trained", "focus": d.get("focus"), "samples": len(texts)}

    def status(self) -> dict:
        return {
            "current_docs": self.kb.rag.stats()["docs"],
            "days_since_train": (time.time() - self._state.get("last_time", 0)) / 86400,
            "history": len(self._state.get("history", [])),
        }
