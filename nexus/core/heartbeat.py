"""
Nexus 心跳循环 — 让AI自己运转一整天

借鉴ClaudeCode的cron+autoDream和GrokBuild的dream蒸馏
"""
import time, os, json, logging
from datetime import datetime

logger = logging.getLogger("nexus.heartbeat")

class HeartbeatLoop:
    """每日心跳——Nexus的生命节律。"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.state_path = os.path.join(data_dir, "heartbeat_state.json")
        self.state = self._load_state()
        self.last_tick = 0

    def _load_state(self) -> dict:
        if os.path.exists(self.state_path):
            with open(self.state_path) as f:
                return json.load(f)
        return {"boot_count": 0, "total_ticks": 0, "tasks_completed": 0, "last_boot": ""}

    def _save_state(self):
        with open(self.state_path, "w") as f:
            json.dump(self.state, f, ensure_ascii=False)

    def boot(self):
        """启动——记录启动次数，检查上次状态。"""
        self.state["boot_count"] += 1
        self.state["last_boot"] = datetime.now().isoformat()
        self._save_state()
        logger.info(f"Nexus heartbeat: boot #{self.state['boot_count']}")

    def tick(self, nexus) -> dict:
        """
        一次心跳。调用自主引擎+学习者。
        借鉴GrokBuild的dream门控: 时间+次数双重阈值。
        """
        now = time.time()
        actions = []

        # 每5分钟 → 自主扫描
        if now - self.last_tick > 300:
            result = nexus.autonomous.tick(nexus)
            actions.append(f"auto_scan: {result['tasks_completed']}/{result['tasks_found']}")
            self.last_tick = now

        # 每60分钟 → AEGIS消化(如果accumulated了轨迹)
        if self.state["total_ticks"] % 12 == 0 and self.state["total_ticks"] > 0:
            actions.append("aegis_digest: pending")

        # 每天凌晨3点 → dream蒸馏（借鉴GrokBuild）
        h = datetime.now().hour
        if h == 3 and not self.state.get("dream_today"):
            actions.append("dream_distill: triggered")
            self.state["dream_today"] = True

        # 新的一天重置dream标记
        if h != 3:
            self.state["dream_today"] = False

        self.state["total_ticks"] += 1
        self._save_state()
        return {"tick": self.state["total_ticks"], "actions": actions}

    def report(self) -> dict:
        """心跳报告——今天做了什么。"""
        return {
            "boot_count": self.state["boot_count"],
            "total_ticks": self.state["total_ticks"],
            "last_boot": self.state["last_boot"],
            "dream_today": self.state.get("dream_today", False),
        }
