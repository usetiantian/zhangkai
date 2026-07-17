# -*- coding: utf-8 -*-
"""
CC Teacher Mode — 用我的思维模式训练Nexus
每30tick自动生成一道"CC风格"的训练题，Nexus自己回答，自己验证

训练模式:
  plan_first    — 先规划再执行 (CC核心习惯)
  verify_always — 每次输出前自检
  ask_why       — 追问根因
  think_loud    — 出声思考
  fix_loop      — 修复→验证→再修复
  modularize    — 拆解复杂问题
"""
import logging, random, time, json, hashlib
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# CC训练题库 — 按能力维度分类
CC_TRAINING_TASKS = {
    "system_audit": [
        "全面审计Nexus所有模块的运行状态，列出每个模块的上次活跃时间、错误计数、依赖关系。给出3个最需要修复的模块。",
        "扫描C:\\Users\\87999\\.nexus\\logs目录，找出最近1小时内所有ERROR和WARNING。按模块分组，给出修复优先级。",
        "检查Nexus的GPU显存使用情况。如果超过80%，找出占用最多的模块并建议释放方案。",
    ],
    "code_review": [
        "阅读heartbeat_loop.py的_launch_async方法。分析它如何处理协程对象和callable。如果有bug，写出修复代码。",
        "审查research_institute.py的_proactive_search方法。它是否正确处理了外部搜索的超时和错误？给出改进建议。",
        "检查scenario_generator.py的场景去重逻辑。是否存在重复场景污染训练数据的风险？",
    ],
    "multi_step_plan": [
        "用户报告系统响应变慢。请分5步诊断：1)检查GPU/CPU占用 2)检查任务队列长度 3)检查最近ERROR日志 4)分析瓶颈模块 5)给出优化方案",
        "需要给Nexus添加一个新能力：自动备份关键文件到D:\\backup。请分步规划：1)确定备份范围 2)设计备份策略 3)编写实现 4)测试验证 5)加入心跳调度",
        "EvoKG数据库WAL文件超过500MB。请分步处理：1)检查WAL大小 2)执行checkpoint 3)验证数据完整性 4)设置自动checkpoint策略",
    ],
    "root_cause": [
        "SelfPlay反复出现UNLEARNABLE。不要只看日志里的UNLEARNABLE字样。追问：为什么这个seed解不了？是代码太长？领域太偏？还是求解器能力不够？给出根因和永久修复方案。",
        "MetaCognition报告已知领域为0。追问：是数据库连接失败？数据被误删？还是查询逻辑有问题？不要只看表面，找到真正的root cause。",
        "心跳偶尔出现idle_tick failed。追问5个为什么，找到最底层的原因，而不是修复表面错误。",
    ],
    "self_improve": [
        "阅读你自己(reasoner.py)的代码。找出一个可以优化的地方——更快的算法、更少的重复计算、更好的错误处理。自己写修复代码。",
        "分析过去24小时的所有ERROR日志。找出重复率最高的3个错误。为每个错误设计永久修复方案，而不是workaround。",
        "你的 WorldModel v19 和旧的 world_model 模块之间有没有功能重叠？如果有，设计合并方案。如果没有，设计桥接方案。",
    ],
}

class CCTeacherMode:
    """CC老师模式 — 自动出题训练Nexus"""

    def __init__(self):
        self._tasks_done = 0
        self._current_task = None

    async def assign_task(self) -> Dict:
        """分配一道训练题"""
        category = random.choice(list(CC_TRAINING_TASKS.keys()))
        task = random.choice(CC_TRAINING_TASKS[category])
        self._current_task = {"category": category, "task": task, "assigned_at": time.time()}
        logger.info("[CC-Teach] New task [%s]: %s", category, task[:80])
        return self._current_task

    async def evaluate_answer(self, task: Dict, answer: str) -> Dict:
        """评估Nexus的回答 — CC风格的评分标准"""
        scores = {}

        # 1. 是否有明确的执行计划？
        plan_keywords = ["step", "步骤", "1.", "2.", "3.", "先", "再", "最后", "首先", "其次"]
        has_plan = any(kw in answer.lower() for kw in plan_keywords)
        scores["has_plan"] = 1.0 if has_plan else 0.3

        # 2. 是否深入到了根因？
        depth_keywords = ["根因", "root cause", "因为", "导致", "底层", "本质", "why"]
        has_depth = any(kw in answer.lower() for kw in depth_keywords)
        scores["depth"] = 1.0 if has_depth else 0.3

        # 3. 是否给出了可执行的修复？
        action_keywords = ["修复", "fix", "修改", "改为", "替换", "添加", "删除", "更新"]
        has_action = any(kw in answer.lower() for kw in action_keywords)
        scores["actionable"] = 1.0 if has_action else 0.2

        # 4. 是否包含验证步骤？
        verify_keywords = ["验证", "测试", "verify", "test", "确认", "检查"]
        has_verify = any(kw in answer.lower() for kw in verify_keywords)
        scores["verification"] = 1.0 if has_verify else 0.2

        # 5. 长度是否足够（不是敷衍了事）？
        scores["thorough"] = min(1.0, len(answer) / 500)

        # 综合评分
        weights = {"has_plan": 0.3, "depth": 0.25, "actionable": 0.25, "verification": 0.1, "thorough": 0.1}
        overall = sum(scores[k] * weights.get(k, 0.2) for k in scores)

        result = {
            "task": task["task"][:100],
            "category": task["category"],
            "scores": scores,
            "overall": round(overall, 2),
            "grade": "A" if overall > 0.8 else "B" if overall > 0.6 else "C" if overall > 0.4 else "D",
            "feedback": self._generate_feedback(scores, overall),
        }

        self._tasks_done += 1
        logger.info("[CC-Teach] Score: %.2f (%s) — %s", overall, result["grade"], result["feedback"][:80])
        return result

    def _generate_feedback(self, scores: Dict, overall: float) -> str:
        """生成CC风格的反馈"""
        feedback = []
        if scores.get("has_plan", 0) < 0.8:
            feedback.append("要先规划再动手——列出步骤1/2/3")
        if scores.get("depth", 0) < 0.8:
            feedback.append("追问根因——不要只看表面，问5个为什么")
        if scores.get("actionable", 0) < 0.8:
            feedback.append("给出可执行的修复——不是描述问题，是解决问题")
        if scores.get("verification", 0) < 0.8:
            feedback.append("修完要验证——跑一遍确认真的修好了")
        if overall > 0.8:
            feedback.append("做得不错，继续保持这种深度思考")
        return "; ".join(feedback) if feedback else "完美"

    @property
    def stats(self) -> dict:
        return {"tasks_completed": self._tasks_done}


_teacher = None

def get_cc_teacher() -> CCTeacherMode:
    global _teacher
    if _teacher is None:
        _teacher = CCTeacherMode()
    return _teacher


async def run_cc_training_cycle() -> Dict:
    """训练周期 — 每30tick自动触发, 用CC风格训练Nexus"""
    try:
        teacher = get_cc_teacher()
        task = await teacher.assign_task()

        # 让Nexus自己回答
        try:
            from nexus_agent.world_model_v19 import get_world_model_v19
            wm = get_world_model_v19()
            ctx = await wm.talk(task["task"], user_id="cc_teacher")
            answer = wm.generate_response(ctx) if not ctx.needs_tier2 else "[Tier2 delegated]"
        except:
            answer = "[WorldModel unavailable]"

        # CC评分
        result = await teacher.evaluate_answer(task, answer)
        result["answer"] = answer[:500]
        return result

    except Exception as e:
        logger.debug("[CC-Teach] cycle: %s", e)
        return {"error": str(e)[:100]}
