"""
长期记忆 — 基于知识图谱 + 日记文件的持久化存储

存储：
- 知识图谱节点：用户偏好、项目信息、技能知识
- 日记文件：每日对话摘要（Markdown追加）
- 关系：用户→偏好、项目→决策、技能→能力
"""
import os, time, logging
from pathlib import Path
logger = logging.getLogger("nexus.memory.long")

class LongTermMemory:
    def __init__(self, graph, diary_dir: str = None):
        self.graph = graph            # KnowledgeGraph 实例
        self.diary_dir = diary_dir or os.path.join(os.path.dirname(__file__), "..", "data", "diary")
        os.makedirs(self.diary_dir, exist_ok=True)

    def remember_user(self, user_id: str, key: str, value: str):
        """记住用户偏好。"""
        self.graph.add_node(user_id, user_id, "user")
        pref_id = f"{user_id}_pref_{key}"
        self.graph.add_node(pref_id, f"{key}:{value}", "preference", key=key, value=value)
        self.graph.add_edge(user_id, pref_id, "prefers")
        logger.info(f"Remember: {key} = {value}")

    def remember_project(self, proj_id: str, key: str, value: str):
        """记住项目决策。"""
        self.graph.add_node(proj_id, proj_id, "project")
        dec_id = f"{proj_id}_dec_{key}"
        self.graph.add_node(dec_id, f"{key}:{value}", "decision", key=key, value=value)
        self.graph.add_edge(proj_id, dec_id, "decided")

    def remember_skill(self, skill_id: str, capability: str):
        """记住技能能力。"""
        self.graph.add_node(skill_id, skill_id, "skill")
        cap_id = f"{skill_id}_cap_{capability}"
        self.graph.add_node(cap_id, capability, "capability")
        self.graph.add_edge(skill_id, cap_id, "can_do")

    def get_user_preferences(self, user_id: str) -> dict:
        """获取用户所有偏好。"""
        prefs = {}
        for edge in self.graph.get_neighbors(user_id, "prefers"):
            node = edge["node"]
            if node.get("type") == "preference":
                prefs[node.get("key", "?")] = node.get("value", "?")
        return prefs

    def write_diary(self, date: str, content: str):
        """写入日报。追加模式。"""
        path = os.path.join(self.diary_dir, f"diary_{date}.md")
        with open(path, "a", encoding="utf-8") as f:
            ts = time.strftime("%H:%M")
            f.write(f"\n## {ts}\n\n{content}\n")

    def read_diary(self, date: str = None) -> str:
        """读取日报。不指定日期读最新。"""
        if date:
            path = os.path.join(self.diary_dir, f"diary_{date}.md")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
        else:
            files = sorted([f for f in os.listdir(self.diary_dir) if f.endswith(".md")])
            if files:
                with open(os.path.join(self.diary_dir, files[-1]), "r", encoding="utf-8") as f:
                    return f.read()
        return ""

    def save(self, path: str = None):
        """保存知识图谱到文件。"""
        path = path or os.path.join(self.diary_dir, "long_term_graph.json")
        self.graph.save(path)

    @classmethod
    def load(cls, data_dir: str = None, graph_path: str = None):
        """从文件恢复。"""
        from knowledge.graph import KnowledgeGraph
        data_dir = data_dir or os.path.join(os.path.dirname(__file__), "..", "data")
        path = graph_path or os.path.join(data_dir, "long_term_graph.json")
        graph = KnowledgeGraph.load(path)
        return cls(graph, os.path.join(data_dir, "diary"))
