"""
Nexus 状态感知层 — 知道"现在什么情况"

立项设计第三层:
  · 当前任务状态
  · 知识空白标记
  · 学习优先级队列
  · 用户活跃度
"""
import time, logging
logger = logging.getLogger("nexus.state")

class StateAwareness:
    """状态感知——Nexus的自我监控。"""

    def __init__(self):
        self.current_task = None      # 当前正在做的事
        self.knowledge_gaps = []      # 发现的知识空白
        self.learning_queue = []      # 学习任务优先级队列
        self.last_interaction = 0     # 上次交互时间
        self.interaction_count = 0    # 总交互次数
        self.error_count = 0          # 错误次数
        self.model_loaded = False     # 模型是否加载

    def start_task(self, task: str):
        self.current_task = task
        self.last_interaction = time.time()

    def end_task(self):
        self.current_task = None

    def add_gap(self, topic: str, priority: int = 3):
        """发现知识空白——该学但还没学的东西。"""
        if topic not in [g["topic"] for g in self.knowledge_gaps]:
            self.knowledge_gaps.append({"topic": topic, "priority": priority, "found_at": time.time()})

    def add_learning(self, topic: str, priority: int = 3):
        """加入学习队列。"""
        self.learning_queue.append({"topic": topic, "priority": priority, "added": time.time()})
        self.learning_queue.sort(key=lambda x: x["priority"], reverse=True)
        self.learning_queue = self.learning_queue[:20]  # 最多20个

    def record_error(self):
        self.error_count += 1

    def set_model_loaded(self, loaded: bool):
        self.model_loaded = loaded

    def snapshot(self) -> dict:
        """当前状态快照——注入prompt帮助推理。"""
        now = time.time()
        idle_seconds = now - self.last_interaction if self.last_interaction else 0

        status = {
            "model_loaded": self.model_loaded,
            "total_interactions": self.interaction_count,
            "errors": self.error_count,
            "idle_seconds": int(idle_seconds),
            "current_task": self.current_task,
            "knowledge_gaps": len(self.knowledge_gaps),
            "learning_queue": len(self.learning_queue),
        }

        # 生成状态描述文本
        parts = []
        if idle_seconds > 300:
            parts.append(f"用户已{int(idle_seconds/60)}分钟未说话")
        if self.current_task:
            parts.append(f"当前任务: {self.current_task}")
        if self.knowledge_gaps:
            top_gap = sorted(self.knowledge_gaps, key=lambda x: x["priority"], reverse=True)[0]
            parts.append(f"最大知识空白: {top_gap['topic']}")
        if self.learning_queue:
            parts.append(f"待学习: {len(self.learning_queue)}项")
        if self.error_count > 0:
            parts.append(f"已出错{self.error_count}次")

        return {"status": status, "description": "。".join(parts) if parts else "正常"}
