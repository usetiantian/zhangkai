"""Goal Classifier + Strategist v2 — 验证面板 + 策略师 (移植自 grok-build goal_classifier + strategist)"""

import json, time, hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class SkepticConfidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class SkepticBlocking(Enum):
    BLOCKING = "blocking"
    NON_BLOCKING = "non_blocking"
    NONE = "none"


@dataclass
class SkepticVerdict:
    """验证者裁决 (移植自 grok-build SkepticVerdict)"""
    refuted: bool           # 是否驳回了目标
    confidence: SkepticConfidence = SkepticConfidence.UNKNOWN
    blocking: SkepticBlocking = SkepticBlocking.NONE
    evidence: str = ""       # 证据
    findings: list = field(default_factory=list)  # 发现的问题
    details_md: str = ""     # 详细报告


@dataclass
class SkepticResult:
    """验证结果"""
    skeptic_idx: int
    refuted: bool
    confidence: SkepticConfidence
    blocking: SkepticBlocking
    evidence: str
    findings: list
    fallback_note: str | None = None
    latency_ms: int = 0


def parse_verdict_json(body: str) -> SkepticVerdict | None:
    """解析验证者 JSON 裁决"""
    try:
        data = json.loads(body)
        return SkepticVerdict(
            refuted=data.get("refuted", False),
            confidence=SkepticConfidence(
                data.get("confidence", "unknown").lower()),
            blocking=SkepticBlocking(
                data.get("blocking", "none").lower()),
            evidence=data.get("evidence", ""),
            findings=data.get("findings", []),
            details_md=data.get("details_md", ""),
        )
    except (json.JSONDecodeError, ValueError):
        return None


def parse_skeptic_terminal_response(terminal: str) -> bool | None:
    """解析终端 token 响应"""
    t = terminal.strip().lower()
    if "achieved" in t or "pass" in t or "success" in t:
        return False  # 未驳回
    if "not_achieved" in t or "fail" in t or "refuted" in t:
        return True   # 驳回
    return None


def gap_fingerprint(findings: list[str]) -> str:
    """缺口指纹 — 用于检测重复错误模式"""
    normalized = sorted(set(
        f.strip().lower().replace(" ", "_")[:50]
        for f in findings
    ))
    return hashlib.sha256(
        "|".join(normalized).encode()
    ).hexdigest()[:16]


class GoalClassifier:
    """
    目标分类器 — 多验证者面板.
    
    移植自 grok-build goal_classifier:
    - read_skeptic_verdict: 读取 JSON 裁决
    - gap_fingerprint: 缺口指纹
    - render_skeptic_panel_details: 渲染验证详情
    """
    def __init__(self, skeptic_count: int = 3):
        self.skeptic_count = skeptic_count
        self.results: list[SkepticResult] = []

    def run_panel(self, goal_objective: str, work_summary: str,
                  code_changes: str = "") -> dict:
        """运行验证面板 — 返回综合裁决"""
        self.results = []

        for i in range(self.skeptic_count):
            result = self._run_single_skeptic(
                i, goal_objective, work_summary, code_changes)
            self.results.append(result)

        return self._aggregate()

    def _run_single_skeptic(self, idx: int, objective: str,
                            summary: str, changes: str) -> SkepticResult:
        """单个验证者 — 让模型判断"""
        start = time.time()

        prompt = f"""你是验证者 #{idx+1}。审查以下目标是否真正达成。

目标: {objective}
完成的工作: {summary}
代码变更: {changes[:500]}

请输出 JSON:
{{"refuted": false, "confidence": "high", "blocking": "none",
  "evidence": "你的理由", "findings": ["发现1", "发现2"],
  "details_md": "你的详细报告"}}"""

        try:
            from coordinator.engine import think
            raw = think(prompt)

            # 尝试解析 JSON
            m = __import__('re').search(r'\{.*\}', raw, __import__('re').DOTALL)
            if m:
                verdict = parse_verdict_json(m.group())
                if verdict:
                    return SkepticResult(
                        skeptic_idx=idx,
                        refuted=verdict.refuted,
                        confidence=verdict.confidence,
                        blocking=verdict.blocking,
                        evidence=verdict.evidence,
                        findings=verdict.findings,
                        latency_ms=int((time.time() - start) * 1000),
                    )

            # 回退: 终端 token
            refuted = parse_skeptic_terminal_response(raw)
            if refuted is not None:
                return SkepticResult(
                    skeptic_idx=idx,
                    refuted=refuted,
                    confidence=SkepticConfidence.UNKNOWN,
                    blocking=SkepticBlocking.NONE,
                    evidence="",
                    findings=[],
                    fallback_note="terminal token fallback",
                    latency_ms=int((time.time() - start) * 1000),
                )

        except Exception as e:
            pass

        return SkepticResult(
            skeptic_idx=idx,
            refuted=True,
            confidence=SkepticConfidence.UNKNOWN,
            blocking=SkepticBlocking.BLOCKING,
            evidence=str(e)[:200],
            findings=[],
            fallback_note="verdict failed",
            latency_ms=int((time.time() - start) * 1000),
        )

    def _aggregate(self) -> dict:
        """综合所有验证者裁决"""
        refuted_count = sum(1 for r in self.results if r.refuted)
        blocking_count = sum(
            1 for r in self.results
            if r.blocking == SkepticBlocking.BLOCKING
        )

        all_findings = []
        for r in self.results:
            all_findings.extend(r.findings)

        fp = gap_fingerprint(all_findings) if all_findings else ""

        return {
            "achieved": refuted_count < len(self.results) / 2,
            "refuted": f"{refuted_count}/{len(self.results)}",
            "blocking": blocking_count,
            "consensus": "achieved" if refuted_count < len(self.results) / 2
                         else "not_achieved" if refuted_count > len(self.results) / 2
                         else "split",
            "findings": all_findings,
            "gap_fingerprint": fp,
            "results": [
                {
                    "skeptic": r.skeptic_idx,
                    "refuted": r.refuted,
                    "confidence": r.confidence.value,
                    "blocking": r.blocking.value,
                }
                for r in self.results
            ],
        }


class Strategist:
    """
    策略师 — 当目标卡住时重新规划.
    
    移植自 grok-build goal_strategist.
    """
    def __init__(self):
        self.last_strategy: str = ""
        self.last_strategy_path: str = ""
        self.fire_count: int = 0

    def analyze(self, objective: str, gaps: list[str],
                rounds: int) -> str:
        """分析卡住原因, 给出新策略"""
        self.fire_count += 1

        prompt = f"""你是策略师。目标已执行 {rounds} 轮但未达成。

目标: {objective}
当前缺口: {gaps}

请给出新的执行策略建议 (简短, 1-3 条):
1.
2.
3."""

        try:
            from coordinator.engine import think
            strategy = think(prompt)
            self.last_strategy = strategy
            return strategy
        except Exception as e:
            return f"策略生成失败: {e}"
