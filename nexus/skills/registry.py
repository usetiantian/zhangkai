"""技能注册中心——借鉴ClaudeCode Tool抽象+MCP协议"""
import os, json, logging
logger = logging.getLogger("nexus.skills")

class SkillRegistry:
    def __init__(self):
        self.skills = {}

    def register(self, name: str, description: str, handler, schema: dict = None):
        self.skills[name] = {"name": name, "description": description, "handler": handler, "schema": schema or {}, "enabled": True}

    def discover(self, skill_dir: str):
        if not os.path.exists(skill_dir): return
        for f in os.listdir(skill_dir):
            if f.endswith(".json"):
                with open(os.path.join(skill_dir, f)) as fp:
                    meta = json.load(fp)
                    self.register(meta["name"], meta.get("desc", ""), None, meta)

    def match(self, intent: str) -> list:
        matched = []
        for name, skill in self.skills.items():
            if skill["enabled"]:
                # 双向匹配——intent里有没有skill关键词，skill里有没有intent关键词
                score = 0
                for kw in [skill["name"], skill["description"]]:
                    if kw in intent:
                        score += 2
                    elif any(c in intent for c in kw if len(c) >= 1):
                        score += 0.5  # 部分字符匹配
                if score > 0:
                    matched.append({"name": name, "score": score, **skill})
        return sorted(matched, key=lambda x: x["score"], reverse=True)

    def execute(self, name: str, **params):
        skill = self.skills.get(name)
        if not skill or not skill["handler"]:
            raise ValueError(f"Skill not available: {name}")
        return skill["handler"](**params)

    def list_all(self) -> list:
        return [{"name": n, "desc": s["description"], "enabled": s["enabled"]} for n, s in self.skills.items()]
