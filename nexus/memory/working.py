"""工作记忆 — 任务状态+技能栈+投机预览（实时）"""
import time
class WorkingMemory:
    def __init__(self):
        self.current_task = None       # {"action":..., "target":..., "started":...}
        self.skill_stack = []          # 当前激活的技能列表
        self.speculative = {}          # 投机执行预览 {"path": "overlay内容"}
        self.last_decision = None

    def set_task(self, action: str, target: str):
        self.current_task = {"action": action, "target": target, "started": time.time()}

    def push_skill(self, skill_name: str):
        if skill_name not in self.skill_stack:
            self.skill_stack.append(skill_name)

    def pop_skill(self, skill_name: str):
        if skill_name in self.skill_stack:
            self.skill_stack.remove(skill_name)

    def set_speculative(self, path: str, preview: str):
        """记录投机执行预览。"""
        self.speculative[path] = preview

    def clear_speculative(self, path: str, confirmed: bool):
        """确认或放弃投机执行。confirmed=True则保留，False则清除。"""
        if not confirmed:
            self.speculative.pop(path, None)
        # confirmed: 保留记录供后续 audit

    def snapshot(self) -> dict:
        return {
            "current_task": self.current_task,
            "active_skills": self.skill_stack[:],
            "speculative_count": len(self.speculative),
        }
