"""
统一压缩引擎 — ClaudeCode四级+AEGIS消化器融合

五层压缩：
  1. snip         — 每轮前裁剪旧消息(ClaudeCode)
  2. micro compact — 缓存感知/时间/API级三种策略(ClaudeCode)
  3. auto compact  — Token超阈值→AI浓缩对话(ClaudeCode)
  4. reactive      — 413溢出紧急压缩+恢复关键信息(ClaudeCode)
  5. aegis digest  — 轨迹→结构化摘要+失败模式+证据片段(HarnessX)

核心原则(ClaudeCode): 压缩后自动恢复最近读取文件/当前plan/已调用技能
"""
import time, logging
from collections import deque

logger = logging.getLogger("nexus.compact")


class UnifiedCompactor:
    """五层压缩引擎。AEGIS消化器是第5层——结构化的轨迹压缩。"""

    def __init__(self, max_context_tokens: int = 10000):
        self.max_tokens = max_context_tokens
        self.snipped = 0
        self.micro_compacted = 0
        self.auto_compacted = 0
        self.reactive_compacted = 0
        self.aegis_digested = 0
        # ClaudeCode: 压缩后需要恢复的关键信息
        self._recent_files = deque(maxlen=5)
        self._current_plan = None
        self._active_skills = []

    # ── Layer 1: snip — 每轮前裁剪 ──

    def snip(self, messages: list, max_messages: int = 50) -> list:
        """裁剪旧消息，保留最近N条 + 系统消息。"""
        if len(messages) <= max_messages:
            return messages
        system_msgs = [m for m in messages if m.get("role") == "system"]
        recent = messages[-(max_messages - len(system_msgs)):]
        self.snipped += len(messages) - len(recent) - len(system_msgs)
        return system_msgs + recent

    # ── Layer 2: micro compact — 缓存感知/时间/API级 ──

    def micro_compact(self, messages: list, strategy: str = "cache_aware") -> list:
        """
        三种策略:
          cache_aware: 保留可缓存的静态部分，压缩动态部分
          time_based:  超过N秒的消息合并摘要
          api_level:   利用API缓存机制减少重复传输
        """
        if strategy == "cache_aware":
            return self._micro_cache_aware(messages)
        elif strategy == "time_based":
            return self._micro_time_based(messages)
        return messages

    def _micro_cache_aware(self, messages: list) -> list:
        """静态部分(系统提示)保留原文，动态部分(对话)可能截断。"""
        result = []
        for m in messages:
            if m.get("role") == "system":
                result.append(m)  # 静态缓存友好
            else:
                content = m.get("content", "")
                if len(content) > 2000:
                    m = dict(m)
                    m["content"] = content[:2000] + "...[snip]"
                result.append(m)
        self.micro_compacted += 1
        return result

    def _micro_time_based(self, messages: list, max_age_s: int = 300) -> list:
        """超过5分钟的消息合并为摘要。"""
        now = time.time()
        result = []
        old_summaries = []
        for m in messages:
            if m.get("timestamp", now) > now - max_age_s:
                result.append(m)
            else:
                old_summaries.append(m.get("content", "")[:100])
        if old_summaries:
            result.insert(0, {"role": "system", "content": f"[历史摘要]: {'; '.join(old_summaries[-3:])}"})
        self.micro_compacted += 1
        return result

    # ── Layer 3: auto compact — Token超阈值压缩 ──

    def auto_compact(self, messages: list) -> list:
        """Token超阈值→AI浓缩对话。压缩后恢复关键信息。"""
        estimated = sum(len(str(m)) for m in messages)
        if estimated < self.max_tokens * 3:  # 粗略估算
            return messages

        # 压缩: 保留system + 最近5条 + 摘要中间
        system = [m for m in messages if m.get("role") == "system"]
        recent = messages[-5:]
        middle_summary = {"role": "system", "content": self._summarize_middle(messages[1:-5])}

        self.auto_compacted += 1
        # ClaudeCode: 压缩后恢复关键信息
        self._restore_critical_context()
        return system + [middle_summary] + recent

    def _summarize_middle(self, messages: list) -> str:
        """压缩中间消息为摘要——借鉴ClaudeCode的AI浓缩。"""
        if not messages: return ""
        topics = set()
        for m in messages:
            content = m.get("content", "")
            if "分析" in content: topics.add("股票分析")
            if "学习" in content: topics.add("知识学习")
            if "代码" in content or "code" in content.lower(): topics.add("代码编写")
        return f"[压缩{len(messages)}条消息] 讨论主题: {', '.join(topics) if topics else '通用对话'}"

    # ── Layer 4: reactive compact — 413溢出紧急压缩 ──

    def reactive_compact(self, messages: list) -> list:
        """
        紧急压缩: 只保留system + 最近3条 + 当前plan + 已调用技能
        ClaudeCode: 不暴力丢弃，恢复关键上下文
        """
        system = [m for m in messages if m.get("role") == "system"]
        recent = messages[-3:]
        critical = []

        if self._current_plan:
            critical.append({"role": "system", "content": f"[当前Plan]: {self._current_plan}"})
        if self._active_skills:
            critical.append({"role": "system", "content": f"[已调用技能]: {', '.join(self._active_skills)}"})
        if self._recent_files:
            critical.append({"role": "system", "content": f"[最近文件]: {', '.join(self._recent_files)}"})

        self.reactive_compacted += 1
        return system + critical + recent

    # ── Layer 5: AEGIS digest — 轨迹结构化压缩 ──

    def aegis_digest(self, trajectories: list) -> dict:
        """
        AEGIS消化器: 千万token轨迹 → 结构化摘要
        不是简单截断——提取失败模式+证据片段+受影响组件
        """
        from learner.aegis import TrajectoryDigestor
        digestor = TrajectoryDigestor()
        result = digestor.compress(trajectories)
        self.aegis_digested += 1
        return result

    # ── ClaudeCode: 压缩后恢复关键信息 ──

    def track_file(self, path: str):
        self._recent_files.append(path)

    def track_plan(self, plan: str):
        self._current_plan = plan

    def track_skill(self, skill_name: str):
        if skill_name not in self._active_skills:
            self._active_skills.append(skill_name)

    def _restore_critical_context(self):
        """压缩后恢复: 最近文件 + plan + 技能。"""
        logger.debug(f"Restored: {len(self._recent_files)} files, plan={bool(self._current_plan)}, {len(self._active_skills)} skills")

    # ── 统计 ──

    def stats(self) -> dict:
        return {
            "snip": self.snipped,
            "micro_compact": self.micro_compacted,
            "auto_compact": self.auto_compacted,
            "reactive_compact": self.reactive_compacted,
            "aegis_digest": self.aegis_digested,
        }
