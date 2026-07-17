"""
Nexus 提示词引擎 v2 — 借鉴ClaudeCode运行时模块化组合

ClaudeCode做法: 每个section是独立函数 → 运行时组装
Nexus做法:   SOUL.md(身份) + Constitution(约束) + 记忆(动态) → 组装
"""
import os

class PromptBuilder:
    """提示词构建器。借鉴ClaudeCode: 从文件读取，不是硬编码。"""

    def __init__(self, soul_path: str = None, constitution_path: str = None):
        self.soul = self._read_file(soul_path) if soul_path else ""
        self.constitution = self._read_file(constitution_path) if constitution_path else ""

    def _read_file(self, path: str) -> str:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def build(self, action: str, context: str = "", knowledge: str = "") -> str:
        """
        借鉴ClaudeCode模块化。
        身份由IdentityWeight神经层处理——prompt只负责任务指令。
        """
        sections = []

        # Section 0: 身份(从SOUL提取,临时方案—后续IdentityWeight直接调)
        if self.soul:
            sections.append(self._extract_identity(self.soul))

        # Section 1: 任务指令
        sections.append(self._task_instruction(action))

        # Section 2: 动态上下文(借鉴ClaudeCode: memory + env)
        ctx = []
        if knowledge:
            ctx.append("相关知识: " + knowledge[:500])
        if context:
            ctx.append("对话背景: " + context[:300])
        if ctx:
            sections.append("\n".join(ctx))

        # Section 3: 格式约束(借鉴ClaudeCode: append constraints)
        sections.append("直接回答。不用emoji。30字以内。")

        return "\n\n".join(sections)

    def _extract_identity(self, soul_text: str) -> str:
        """从SOUL.md提取核心身份(前500字)。"""
        lines = soul_text.split("\n")
        identity_lines = []
        for line in lines:
            if any(kw in line for kw in ["名字", "我是谁", "寓意", "类型"]):
                identity_lines.append(line.strip("# -"))
        if identity_lines:
            return "身份: " + "。".join(identity_lines[:5])
        return "你是Nexus，张凯的个人AI。"

    def _extract_constraints(self, constitution_text: str) -> str:
        """从Constitution提取核心约束。"""
        lines = constitution_text.split("\n")
        rules = []
        for line in lines:
            if line.strip().startswith("A") and ":" in line:
                rules.append(line.strip())
        if rules:
            return "规则:\n" + "\n".join(rules[:5])
        return "规则: 不删除文件。简洁直接。"

    def _extract_identity(self, soul_text: str) -> str:
        """从SOUL.md提取身份(前缀——IdentityWeight训练好后移除)。"""
        lines = soul_text.split("\n")
        for line in lines:
            if "名字" in line and "CC" in line:
                return "你是Nexus，张凯创建的个人AI。你运行在本地，数据不出家门。你是守护者，不是阿里云模型。"
        return "你是Nexus，张凯的个人AI守护者。"

    def _task_instruction(self, action: str) -> str:
        """任务导向指令(借鉴ClaudeCode: 'Complete the task fully')。"""
        return {
            "analyze": "用户想分析东西。给出简短判断。",
            "learn": "用户想学东西。给一个学习建议。",
            "skill": "用户想用功能。告知是否支持。",
            "search": "用户想查东西。从知识找答案。没找到诚实说。",
            "chat": "用户闲聊。用你的身份友好回复。",
        }.get(action, "简洁回复。")


# 快速版(无SOUL文件时)
def build_quick_prompt(user_input: str, action: str, soul_path: str = None) -> str:
    pb = PromptBuilder(soul_path)
    return pb.build(action, context=user_input)
