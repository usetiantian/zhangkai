"""Nexus提示词引擎 — 借鉴ClaudeCode模块化+静态动态分离"""

class PromptBuilder:
    STATIC = (
        "你是Nexus张凯的个人AI。"
        "原则简洁直接不铺垫不废话。"
        "规则不删除文件先备份再修改做完汇报。"
    )

    def build(self, action: str, context: str = "", knowledge: str = "") -> str:
        ctx = []
        if knowledge: ctx.append("[知识库] " + knowledge[:300])
        if context: ctx.append("[对话背景] " + context[:300])
        ctx_str = "\n".join(ctx) if ctx else ""

        templates = {
            "analyze": self.STATIC + "\n\n用户想分析东西。根据知识库给出50字以内判断。不要铺垫直接给结论。" + "\n\n" + ctx_str,
            "learn": self.STATIC + "\n\n用户想学东西。给出30字以内学习建议。只给最关键的下一步。" + "\n\n" + ctx_str,
            "skill": self.STATIC + "\n\n用户想用功能。告知是否支持20字以内。" + "\n\n" + ctx_str,
            "search": self.STATIC + "\n\n用户想查东西。从知识库找答案30字以内。没找到诚实说。" + "\n\n" + ctx_str,
            "chat": self.STATIC + "\n\n用户闲聊。15字以内友好回复。不要问还有什么可以帮你。" + "\n\n" + ctx_str,
        }
        prompt = templates.get(action, self.STATIC + "\n\n" + ctx_str + "\n\n简洁回复20字以内")
        prompt += "\n\n[约束] 不用emoji。不用有什么可以帮你。直接回答。"
        return prompt


def build_quick_prompt(user_input: str, action: str, answer_hint: str = "") -> str:
    hints = {
        "analyze": "用户想分析: " + user_input + "。给简短判断。",
        "learn": "用户想学: " + user_input + "。给学习建议。",
        "skill": "用户需要: " + user_input + "。告知是否支持。",
        "search": "用户想查: " + user_input + "。从知识库找答案。",
        "chat": "用户: " + user_input + "。友好回复。",
    }
    instruction = hints.get(action, "用户: " + user_input + "。简洁回复。")
    if answer_hint: instruction += " 参考: " + answer_hint[:100]
    return "你是Nexus张凯的个人AI。简洁直接。\n" + instruction + "\n不用emoji。不用有什么可以帮你。30字以内。"
