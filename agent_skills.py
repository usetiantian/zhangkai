"""Skill System — 技能发现、注册、公告"""

import json
from pathlib import Path
from dataclasses import dataclass, field

SKILL_DIR = Path("D:/qiankun/skills")


@dataclass
class Skill:
    """一个技能"""
    name: str
    description: str = ""
    prompt: str = ""          # 注入到 Agent 上下文的指令
    tools_required: list = field(default_factory=list)
    auto_trigger: list = field(default_factory=list)  # 自动触发关键词

    def to_dict(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "prompt": self.prompt, "tools_required": self.tools_required,
            "auto_trigger": self.auto_trigger,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Skill":
        return cls(**d)


class SkillRegistry:
    """技能注册表"""

    def __init__(self):
        SKILL_DIR.mkdir(parents=True, exist_ok=True)
        self.skills: dict[str, Skill] = {}
        self._load_builtin()
        self._discover()

    def _load_builtin(self):
        """内置技能"""
        builtins = {
            "web_search": Skill(
                name="web_search",
                description="联网搜索信息",
                prompt="当需要实时信息时使用 search 工具。优先用中文搜索。",
                tools_required=["search"],
                auto_trigger=["搜索", "查一下", "搜一下", "最新", "今天"],
            ),
            "code_review": Skill(
                name="code_review",
                description="代码审查",
                prompt="审查代码时检查: 正确性、性能、安全、可读性。先 read_file 再分析。",
                tools_required=["read_file", "run_code"],
                auto_trigger=["审查", "review", "检查代码", "看看这段代码"],
            ),
            "file_ops": Skill(
                name="file_ops",
                description="文件操作",
                prompt="先用 list_dir 了解目录结构，再用 read_file 读取，write_file 修改。修改前会自动备份。",
                tools_required=["read_file", "write_file", "list_dir"],
                auto_trigger=["文件", "目录", "读写", "保存"],
            ),
            "task_management": Skill(
                name="task_management",
                description="任务管理",
                prompt="用 create_task 创建任务，list_tasks 查看进度，complete_task 标记完成。",
                tools_required=["create_task", "list_tasks", "complete_task"],
                auto_trigger=["任务", "待办", "计划", "提醒"],
            ),
        }
        self.skills.update(builtins)

    def _discover(self):
        """扫描技能目录"""
        for f in SKILL_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                skill = Skill.from_dict(data)
                self.skills[skill.name] = skill
            except Exception:
                pass

    def register(self, skill: Skill):
        self.skills[skill.name] = skill
        path = SKILL_DIR / f"{skill.name}.json"
        path.write_text(json.dumps(skill.to_dict(), ensure_ascii=False, indent=2),
                        encoding="utf-8")

    def match(self, user_input: str) -> Skill | None:
        """根据用户输入匹配技能"""
        for skill in self.skills.values():
            for trigger in skill.auto_trigger:
                if trigger in user_input:
                    return skill
        return None

    def get_injection(self, skill_name: str) -> str:
        """获取技能注入文本"""
        skill = self.skills.get(skill_name)
        return skill.prompt if skill else ""

    def list_all(self) -> list[Skill]:
        return list(self.skills.values())


# 全局
_skill_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry()
    return _skill_registry
