"""
用户认知层 — 知道"用户是谁、喜欢什么"

立项设计第二层(出厂空白，每用户自训练):
  · 用户叫什么
  · 什么职业
  · 喜欢什么风格
  · 讨厌什么方式
  · 历史决策偏好
"""
import json, os, logging
logger = logging.getLogger("nexus.user_cognition")

class UserCognition:
    """用户认知——记录用户偏好，越用越懂。"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.profiles = {}  # {user_id: profile}
        self._load_all()

    def _load_all(self):
        for f in os.listdir(self.data_dir):
            if f.endswith(".json"):
                uid = f.replace(".json", "")
                with open(os.path.join(self.data_dir, f), "r", encoding="utf-8") as fp:
                    self.profiles[uid] = json.load(fp)

    def _save(self, user_id: str):
        with open(os.path.join(self.data_dir, f"{user_id}.json"), "w", encoding="utf-8") as f:
            json.dump(self.profiles[user_id], f, ensure_ascii=False, indent=2)

    def get_or_create(self, user_id: str, name: str = "") -> dict:
        if user_id not in self.profiles:
            self.profiles[user_id] = {
                "name": name or user_id,
                "profession": "",
                "preferences": {},     # {"style": "简洁", "tone": "直接"}
                "dislikes": [],        # ["铺垫", "啰嗦"]
                "decision_history": [], # [{"date":"...","choice":"A","reason":"..."}]
                "conversation_count": 0,
                "last_seen": "",
            }
            self._save(user_id)
        return self.profiles[user_id]

    def observe(self, user_id: str, action: str, detail: str = ""):
        """观察一次用户行为。"""
        p = self.get_or_create(user_id)
        p["conversation_count"] += 1

        # 学习偏好: analyze → 股票相关, learn → 学习偏好
        if action == "analyze":
            p["preferences"].setdefault("interests", [])
            if "股票" not in p["preferences"]["interests"]:
                p["preferences"]["interests"].append("股票")
        elif action == "learn":
            if detail and detail not in p.get("learning_topics", []):
                p.setdefault("learning_topics", []).append(detail)

        p["last_seen"] = __import__('time').strftime("%Y-%m-%d %H:%M")
        if p["conversation_count"] % 50 == 0:
            self._save(user_id)

    def get_context(self, user_id: str) -> str:
        """获取用户认知摘要——注入prompt。"""
        p = self.get_or_create(user_id)
        if not p.get("profession"):
            return f"用户: {p['name']} (新用户)"

        parts = [f"用户: {p['name']}"]
        if p.get("profession"): parts.append(f"职业: {p['profession']}")
        if p.get("preferences", {}).get("style"): parts.append(f"偏好: {p['preferences']['style']}")
        if p.get("preferences", {}).get("interests"): parts.append(f"兴趣: {', '.join(p['preferences']['interests'][:3])}")
        parts.append(f"交互: {p['conversation_count']}次")
        return "。".join(parts) + "。"

    def learn_preference(self, user_id: str, key: str, value: str):
        """学习一个偏好。"""
        p = self.get_or_create(user_id)
        p["preferences"][key] = value
        self._save(user_id)
