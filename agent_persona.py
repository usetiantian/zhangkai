"""Persona System — Agent 可切换人格"""

import json
from dataclasses import dataclass, field
from pathlib import Path

PERSONA_DIR = Path("D:/qiankun/personas")


@dataclass
class Persona:
    """一个 Agent 人格"""
    name: str
    description: str = ""
    system_prompt: str = ""
    tools_allowlist: list = field(default_factory=list)  # None=全部
    model_preference: str = ""  # 偏好模型
    temperature: float = 0.7

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "tools_allowlist": self.tools_allowlist,
            "model_preference": self.model_preference,
            "temperature": self.temperature,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Persona":
        return cls(**d)


# 内置人格
BUILTIN_PERSONAS = {
    "default": Persona(
        name="default",
        description="乾坤通用助手",
        system_prompt="""你是乾坤，张凯的自主 AI 助手。你运行在本机 D 盘，有自己的记忆和工具。
你知道的就直接回答，不确定的就搜索确认。你是一个会思考、会决策的自主生命体。""",
    ),
    "stock": Persona(
        name="stock",
        description="A股超短线分析师",
        system_prompt="""你是乾坤的股票分析人格。你专注于 A 股超短线分析。
你能搜索行情、抓取财报、分析龙虎榜、识别游资信号。
你的分析风格是数据驱动、简洁直接。对每一只股票给出明确的买卖建议。""",
        tools_allowlist=["search", "fetch", "browser", "extract", "notify"],
        temperature=0.3,
    ),
    "coder": Persona(
        name="coder",
        description="代码助手",
        system_prompt="""你是乾坤的编程人格。你专注于代码生成、调试、架构设计。
你能读写文件、执行代码、搜索技术文档。
你的输出直接可用，附带必要的解释。""",
        tools_allowlist=["search", "fetch", "read_file", "write_file",
                         "run_code", "list_dir", "undo_file"],
        temperature=0.5,
    ),
    "researcher": Persona(
        name="researcher",
        description="深度研究员",
        system_prompt="""你是乾坤的研究人格。你专注于深度信息收集和分析。
你会用搜索、抓取、爬取层层深入，交叉验证信息源，给出有引用的研究报告。""",
        tools_allowlist=["search", "fetch", "browser", "crawl",
                         "extract", "notify"],
        temperature=0.4,
    ),
}


def load_persona(name: str) -> Persona:
    """加载人格 (内置优先，然后从文件)"""
    if name in BUILTIN_PERSONAS:
        return BUILTIN_PERSONAS[name]

    PERSONA_DIR.mkdir(parents=True, exist_ok=True)
    path = PERSONA_DIR / f"{name}.json"
    if path.exists():
        return Persona.from_dict(json.loads(path.read_text(encoding="utf-8")))

    return BUILTIN_PERSONAS["default"]


def save_persona(persona: Persona):
    """保存自定义人格"""
    PERSONA_DIR.mkdir(parents=True, exist_ok=True)
    path = PERSONA_DIR / f"{persona.name}.json"
    path.write_text(json.dumps(persona.to_dict(), ensure_ascii=False, indent=2),
                    encoding="utf-8")


def list_personas() -> list[str]:
    """列出所有人格"""
    names = list(BUILTIN_PERSONAS.keys())
    PERSONA_DIR.mkdir(parents=True, exist_ok=True)
    for f in PERSONA_DIR.glob("*.json"):
        names.append(f.stem)
    return sorted(set(names))
