# -*- coding: utf-8 -*-
"""
Nexus SelfAuditor v2 — 编排层（融合已有组件，不重复造轮子）

职责：把 event_auditor + health_monitor + self_heal 的审计能力，
      与新增的 8步闭环静态代码分析 融合成一个统一入口。

已有组件复用：
  - EventAuditor: 死信检测 + 自愈 (不重复)
  - HealthMonitor: 9维运行时健康 (不重复)
  - SelfHealEngine: Sentinel→修复 (不重复)

新增能力（这些是已有组件做不了的）：
  - 8步闭环静态代码分析 (WHY→SCAN→GENERALIZE→ANALYZE→IMPLEMENT→VERIFY→DOCUMENT→CLOSE)
  - 跨模块依赖图分析 (import graph + fan-in/fan-out)
  - 历史趋势追踪 (score随时间的变化)
  - 统一报告聚合 (三步结果汇总)

用法：
    auditor = get_self_auditor()
    report = await auditor.orchestrate_audit("knowledge_generator")
"""

import ast
import asyncio
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

AGENT_DIR = Path(__file__).parent
AUDIT_HISTORY = AGENT_DIR.parent / "data" / "audit_history.json"

# ── 8步闭环步骤定义 ──────────────────────────────────────

EIGHT_STEPS = [
    ("0_WHY",       "追问为什么",  "根因分析：表象→直接原因→根因→系统性原因→预防"),
    ("1_SCAN",      "先扫描",      "代码定位+调用链+加载机制+类比+风险分离"),
    ("2_GENERALIZE","举一反三",    "根因扩散+同类检测+同步更新+系统性反思"),
    ("3_ANALYZE",   "分析设计",    "功能映射+状态模型+技术选型+风险预案"),
    ("4_IMPLEMENT", "分批实现",    "粒度检测+验证能力+备份机制"),
    ("5_VERIFY",    "测试验证",    "单元+E2E+边界+回归+安全检查"),
    ("6_DOCUMENT",  "文档归档",    "MEMORY+Obsidian+LEARNINGS+清理"),
    ("7_CLOSE",     "形成闭环",    "需求清单+数据新鲜度+执行链路+PREVENT"),
]


@dataclass
class StepResult:
    step_key: str
    label: str
    score: float
    status: str  # ok / warn / error
    findings: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)


@dataclass
class UnifiedReport:
    module: str
    timestamp: float

    # 8步静态分析（新增，独有）
    eight_step: List[StepResult] = field(default_factory=list)

    # 运行时审计（委托给已有组件）
    runtime_audit: Dict[str, Any] = field(default_factory=dict)

    # 跨模块依赖（新增，独有）
    deps: Dict[str, Any] = field(default_factory=dict)

    # 历史趋势（新增，独有）
    trend: Dict[str, Any] = field(default_factory=dict)

    # 汇总
    overall_score: float = 0.0
    status: str = "unknown"


class SelfAuditor:
    """编排层：融合已有审计组件 + 新增 8步静态分析。"""

    def __init__(self):
        self._event_auditor = None
        self._health_monitor = None
        self._module_index: Dict[str, Path] = {}
        self._import_graph: Dict[str, set] = defaultdict(set)
        self._history: Dict[str, list] = {}
        self._loaded = False

    def load(self) -> bool:
        """加载依赖 + 构建模块索引 + 导入图。"""
        # ── 加载已有审计组件 ──
        try:
            from nexus_agent.event_auditor import get_event_auditor
            self._event_auditor = get_event_auditor()
        except Exception:
            logger.debug("[SelfAuditor] event_auditor unavailable")

        try:
            from nexus_agent.health_monitor import get_health_monitor
            self._health_monitor = get_health_monitor()
        except Exception:
            logger.debug("[SelfAuditor] health_monitor unavailable")

        # ── 构建模块索引 + 导入图 ──
        for f in AGENT_DIR.rglob("*.py"):
            if f.name.startswith("__"):
                continue
            mod = f.stem if f.parent == AGENT_DIR else f"{f.parent.name}.{f.stem}"
            self._module_index[mod] = f
            try:
                code = f.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        targets = []
                        if isinstance(node, ast.ImportFrom) and node.module:
                            targets.append(node.module)
                        for a in node.names:
                            targets.append(a.name)
                        for t in targets:
                            self._import_graph[mod].add(t)
            except Exception:
                pass

        # ── 加载历史 ──
        try:
            if AUDIT_HISTORY.exists():
                self._history = json.loads(AUDIT_HISTORY.read_text("utf-8"))
        except Exception:
            pass

        self._loaded = True
        logger.info("[SelfAuditor] v2 编排引擎就绪 (modules=%d, event_auditor=%s, health_monitor=%s)",
                   len(self._module_index),
                   self._event_auditor is not None,
                   self._health_monitor is not None)
        return True

    # ══════════════════════════════════════════════════════════
    # 主入口：编排审计
    # ══════════════════════════════════════════════════════════

    async def orchestrate_audit(self, module_name: str) -> UnifiedReport:
        """编排一次完整审计：运行时 + 静态 + 依赖 + 趋势。"""
        t0 = time.time()
        report = UnifiedReport(module=module_name, timestamp=t0)

        file_path = self._find_file(module_name)
        if not file_path:
            report.status = "error"
            return report

        try:
            code = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(code)
        except Exception:
            report.status = "error"
            return report

        # 1) 8步静态分析（独有）
        report.eight_step = self._run_eight_step(module_name, code, tree, file_path)

        # 2) 运行时审计（委托给已有组件）
        report.runtime_audit = await self._run_runtime_audit(module_name)

        # 3) 跨模块依赖（独有）
        report.deps = self._analyze_dependencies(module_name, code, tree)

        # 4) 历史趋势（独有）
        report.trend = self._analyze_trend(module_name)

        # 汇总
        scores = [s.score for s in report.eight_step]
        if report.runtime_audit.get("health_score"):
            scores.append(report.runtime_audit["health_score"])

        report.overall_score = sum(scores) / len(scores) if scores else 0.0

        if report.overall_score >= 0.8:
            report.status = "healthy"
        elif report.overall_score >= 0.5:
            report.status = "degraded"
        else:
            report.status = "critical"

        # 持久化
        self._save_score(module_name, report.overall_score)

        # 如果有危险发现，发 sentinel 告警
        if report.status == "critical":
            await self._emit_alert(report)

        return report

    async def orchestrate_all(self) -> Dict[str, Any]:
        """全模块编排审计。"""
        reports = []
        for mod in sorted(self._module_index.keys()):
            try:
                r = await self.orchestrate_audit(mod)
                reports.append(r)
            except Exception:
                pass

        critical = [r for r in reports if r.status == "critical"]
        degraded = [r for r in reports if r.status == "degraded"]
        healthy = [r for r in reports if r.status == "healthy"]

        self._save_history()
        return {
            "total": len(reports),
            "healthy": len(healthy), "degraded": len(degraded), "critical": len(critical),
            "critical_modules": [
                {"name": r.module, "score": r.overall_score,
                 "findings": [f.description for f in (r.eight_step or [])
                            if hasattr(f, 'findings') and r.status != "healthy"][:3]}
                for r in critical[:10]
            ],
        }

    # ══════════════════════════════════════════════════════════
    # 1) 8步静态代码分析（独有——已有组件做不了）
    # ══════════════════════════════════════════════════════════

    def _run_eight_step(self, mod: str, code: str, tree, path: Path) -> List[StepResult]:
        step_map = {
            "0_WHY": self._s0_why,
            "1_SCAN": self._s1_scan,
            "2_GENERALIZE": self._s2_generalize,
            "3_ANALYZE": self._s3_analyze,
            "4_IMPLEMENT": self._s4_implement,
            "5_VERIFY": self._s5_verify,
            "6_DOCUMENT": self._s6_document,
            "7_CLOSE": self._s7_close,
        }
        results = []
        for key, label, _desc in EIGHT_STEPS:
            fn = step_map.get(key)
            if fn:
                sr = fn(mod, code, tree, path)
                sr.step_key = key
                sr.label = label
                results.append(sr)
        return results

    # ── S0: 追问为什么 ──
    def _s0_why(self, mod, code, tree, path) -> StepResult:
        sr = StepResult("0_WHY", "", 1.0, "ok")
        doc = ast.get_docstring(tree)
        if not doc:
            sr.score -= 0.15
            sr.findings.append("无模块文档字符串——无法理解WHY")
        else:
            sr.evidence.append(f"目的: {doc[:200]}")
        if 'raise NotImplementedError' in code:
            sr.score -= 0.3
            sr.findings.append("包含 NotImplementedError——功能存根")
        todos = [l.strip()[:80] for l in code.split('\n') if 'TODO' in l or 'FIXME' in l]
        if todos:
            sr.score -= 0.1
            sr.findings.append(f"{len(todos)}个TODO/FIXME——技术债务")
        if sr.score < 0.5: sr.status = "error"
        elif sr.score < 0.8: sr.status = "warn"
        return sr

    # ── S1: 先扫描 ──
    def _s1_scan(self, mod, code, tree, path) -> StepResult:
        sr = StepResult("1_SCAN", "", 1.0, "ok")
        lines = len(code.split('\n'))
        funcs = len([n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))])
        sr.evidence = [f"{lines}行, {funcs}函数"]

        if lines > 3000:
            sr.score -= 0.3; sr.findings.append(f"过大({lines}行)——高风险")
        elif lines > 1500:
            sr.score -= 0.1; sr.findings.append(f"较大({lines}行)")
        if lines < 10:
            sr.score = 0.0; sr.status = "error"; sr.findings.append("空文件")

        risks = []
        if 'eval(' in code or 'exec(' in code: risks.append("eval/exec")
        if 'subprocess' in code: risks.append("系统调用")
        if risks: sr.score -= len(risks) * 0.05; sr.findings.append(f"风险: {','.join(risks)}")

        if sr.score < 0.5: sr.status = "error"
        elif sr.score < 0.8: sr.status = "warn"
        return sr

    # ── S2: 举一反三 ──
    def _s2_generalize(self, mod, code, tree, path) -> StepResult:
        sr = StepResult("2_GENERALIZE", "", 1.0, "ok")
        # 检查此模块的公开函数被多少其他模块使用
        func_names = [n.name for n in ast.walk(tree)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and not n.name.startswith('_')]
        used_by = []
        for other_mod, other_path in self._module_index.items():
            if other_mod == mod: continue
            try:
                oc = other_path.read_text(encoding="utf-8", errors="replace")
                for fn in func_names:
                    if fn in oc:
                        used_by.append(f"{other_mod}→{fn}")
                        if len(used_by) >= 10: break
            except Exception: pass
            if len(used_by) >= 10: break

        if len(used_by) > 5:
            sr.score -= 0.1
            sr.findings.append(f"高扇出: {len(used_by)}个外部调用点——修改影响面广")
        if used_by:
            sr.evidence = used_by[:5]
        if sr.score < 0.5: sr.status = "error"
        elif sr.score < 0.8: sr.status = "warn"
        return sr

    # ── S3: 分析设计 ──
    def _s3_analyze(self, mod, code, tree, path) -> StepResult:
        sr = StepResult("3_ANALYZE", "", 1.0, "ok")
        # except:pass 计数
        ep = 0
        lines = code.split('\n')
        in_ep = False
        for l in lines:
            s = l.strip()
            if s.startswith('except') and ('Exception' in s or s.rstrip(':') == 'except'):
                in_ep = True
            elif in_ep and s == 'pass': ep += 1; in_ep = False
            elif in_ep and s: in_ep = False
        if ep > 5:
            sr.score -= 0.2; sr.findings.append(f"{ep}处except:pass——静默吞异常")
        elif ep > 0:
            sr.score -= ep * 0.03; sr.findings.append(f"{ep}处except:pass")
        if sr.score < 0.5: sr.status = "error"
        elif sr.score < 0.8: sr.status = "warn"
        return sr

    # ── S4: 分批实现 ──
    def _s4_implement(self, mod, code, tree, path) -> StepResult:
        sr = StepResult("4_IMPLEMENT", "", 1.0, "ok")
        funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        large = [(f.name, (f.end_lineno or 0) - f.lineno + 1)
                for f in funcs if hasattr(f, 'end_lineno') and (f.end_lineno or 0) - f.lineno > 100]
        if large:
            sr.score -= 0.1
            sr.findings.append(f"{len(large)}个大函数(>100行): {[n for n,_ in large[:3]]}——无法分批修改")
        if sr.score < 0.5: sr.status = "error"
        elif sr.score < 0.8: sr.status = "warn"
        return sr

    # ── S5: 测试验证 ──
    def _s5_verify(self, mod, code, tree, path) -> StepResult:
        sr = StepResult("5_VERIFY", "", 1.0, "ok")
        checks = {
            "test": any(k in code for k in ['test_', 'pytest', 'assertEqual']),
            "assert": 'assert ' in code,
            "boundary": any(k in code for k in ['None', 'default', 'max(', 'min(']),
            "timeout": any(k in code for k in ['timeout', 'wait_for']),
        }
        passed = sum(1 for v in checks.values() if v)
        sr.evidence.append(f"验证覆盖: {passed}/{len(checks)}")
        if passed == 0: sr.score -= 0.4; sr.findings.append("无验证机制")
        elif passed <= 2: sr.score -= 0.15
        if sr.score < 0.5: sr.status = "error"
        elif sr.score < 0.8: sr.status = "warn"
        return sr

    # ── S6: 文档归档 ──
    def _s6_document(self, mod, code, tree, path) -> StepResult:
        sr = StepResult("6_DOCUMENT", "", 1.0, "ok")
        has_mod_doc = bool(ast.get_docstring(tree))
        funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        pub = [f for f in funcs if not f.name.startswith('_')]
        docd = [f for f in pub if ast.get_docstring(f)]
        cov = len(docd) / max(len(pub), 1)
        sr.evidence = [f"模块文档:{has_mod_doc}, 函数覆盖率:{cov:.0%}"]
        if not has_mod_doc: sr.score -= 0.1; sr.findings.append("无模块文档")
        if cov < 0.5 and len(pub) > 3: sr.score -= 0.1; sr.findings.append(f"函数文档覆盖率低({cov:.0%})")
        # 残留文件
        if path:
            bak = list(path.parent.glob("*.bak*")) + list(path.parent.glob("*_debug.py"))
            if bak: sr.score -= 0.05; sr.findings.append(f"{len(bak)}个残留文件需清理")
        if sr.score < 0.5: sr.status = "error"
        elif sr.score < 0.8: sr.status = "warn"
        return sr

    # ── S7: 形成闭环 ──
    def _s7_close(self, mod, code, tree, path) -> StepResult:
        sr = StepResult("7_CLOSE", "", 1.0, "ok")
        chain = {
            "trigger": any(k in code for k in ['subscribe', 'on(', 'handler', 'trigger']),
            "execute": any(k in code for k in ['def ', 'async def', 'run(', 'process']),
            "store": any(k in code for k in ['save', 'write', 'store', 'persist']),
            "cleanup": any(k in code for k in ['finally', 'cleanup', 'close(', 'unlink']),
        }
        missing = [k for k, v in chain.items() if not v]
        if len(missing) >= 3:
            sr.score -= 0.3; sr.findings.append(f"执行链路不完整——缺{missing}")
        elif missing:
            sr.score -= 0.1 * len(missing)

        prevent = {
            "TTL": any(k in code for k in ['timeout', 'TTL', 'expire']),
            "monitor": 'logger.' in code or 'logging.' in code,
            "self_heal": any(k in code for k in ['sentinel.alert', 'self_heal']),
        }
        missing_p = [k for k, v in prevent.items() if not v]
        if missing_p:
            sr.score -= 0.1 * len(missing_p)
            sr.findings.append(f"预防机制不全——缺{missing_p}")

        if sr.score < 0.5: sr.status = "error"
        elif sr.score < 0.8: sr.status = "warn"
        return sr

    # ══════════════════════════════════════════════════════════
    # 2) 运行时审计（委托给已有组件）
    # ══════════════════════════════════════════════════════════

    async def _run_runtime_audit(self, module_name: str) -> Dict:
        result = {}
        # 委托 EventAuditor
        if self._event_auditor:
            try:
                ea_result = await self._event_auditor.audit_and_heal()
                result["event_auditor"] = ea_result
            except Exception:
                logger.debug("event_auditor failed", exc_info=True)

        # 委托 HealthMonitor
        if self._health_monitor:
            try:
                hm_result = await self._health_monitor.run_full_check()
                result["health_monitor"] = hm_result.to_dict() if hasattr(hm_result, 'to_dict') else {}
            except Exception:
                logger.debug("health_monitor failed", exc_info=True)

        # 计算综合健康分
        scores = []
        if result.get("event_auditor"):
            ea = result["event_auditor"]
            healed = len(ea.get("healed", []))
            stillborn = ea.get("total_stillborn", 0)
            scores.append(1.0 - min(0.5, stillborn * 0.05))
        if result.get("health_monitor"):
            hm = result["health_monitor"]
            dims = hm.get("dimensions", {})
            if dims:
                scores.append(sum(dims.values()) / len(dims))

        result["health_score"] = sum(scores) / len(scores) if scores else None
        return result

    # ══════════════════════════════════════════════════════════
    # 3) 跨模块依赖（独有）
    # ══════════════════════════════════════════════════════════

    def _analyze_dependencies(self, mod: str, code: str, tree) -> Dict:
        imports = list(self._import_graph.get(mod, set()))
        dependents = [m for m, imps in self._import_graph.items()
                     if any(mod in i for i in imps)]

        # 循环依赖检测
        cycles = []
        for imp in imports:
            base = imp.split('.')[-1]
            if base in self._import_graph and any(mod in i for i in self._import_graph[base]):
                cycles.append(f"{mod}↔{base}")

        result = {
            "imports_count": len(imports),
            "dependents_count": len(dependents),
            "cycles": cycles,
            "high_fan_out": len(dependents) > 15,
            "high_fan_in": len(imports) > 20,
        }
        return result

    # ══════════════════════════════════════════════════════════
    # 4) 历史趋势（独有）
    # ══════════════════════════════════════════════════════════

    def _analyze_trend(self, mod: str) -> Dict:
        if mod not in self._history or len(self._history[mod]) < 3:
            return {"trend": "insufficient_data"}

        recent = [h['score'] for h in self._history[mod][-5:]]
        if all(recent[i] <= recent[i+1] for i in range(len(recent)-1)):
            return {"trend": "improving", "scores": recent}
        elif all(recent[i] >= recent[i+1] for i in range(len(recent)-1)):
            return {"trend": "degrading", "scores": recent}
        return {"trend": "stable", "scores": recent}

    # ══════════════════════════════════════════════════════════
    # 辅助
    # ══════════════════════════════════════════════════════════

    def _find_file(self, name: str) -> Optional[Path]:
        if name in self._module_index: return self._module_index[name]
        for n, p in self._module_index.items():
            if name in n: return p
        return None

    def _save_score(self, mod: str, score: float):
        if mod not in self._history: self._history[mod] = []
        self._history[mod].append({"time": datetime.now().isoformat(), "score": score})
        if len(self._history[mod]) > 50: self._history[mod] = self._history[mod][-50:]

    def _save_history(self):
        try:
            AUDIT_HISTORY.parent.mkdir(parents=True, exist_ok=True)
            AUDIT_HISTORY.write_text(json.dumps(self._history, ensure_ascii=False, indent=2), "utf-8")
        except Exception:
            logger.debug("non-critical operation failed", exc_info=True)

    async def _emit_alert(self, report: UnifiedReport):
        try:
            critical_findings = [f for s in report.eight_step for f in s.findings][:3]
            from nexus_agent.event_bus import get_event_bus
            get_event_bus().publish("sentinel.alert", {
                "level": "MODERATE",
                "reason": f"SelfAudit: {report.module} critical ({report.overall_score:.2f})",
                "module": report.module,
                "findings": critical_findings,
            })
        except Exception:
            logger.debug("non-critical operation failed", exc_info=True)

    # ── 格式化 ──

    def format_report(self, report: UnifiedReport) -> str:
        icon = {"healthy": "✅", "degraded": "⚠️", "critical": "🔴"}.get(report.status, "❓")
        lines = [f"{icon} **{report.module}** score={report.overall_score:.2f} status={report.status}"]

        # 8步
        lines.append("\n## 8步闭环（静态代码分析）")
        for sr in report.eight_step:
            si = {"ok": "✅", "warn": "⚠️", "error": "❌"}.get(sr.status, "?")
            lines.append(f"- {si} {sr.label}: {sr.score:.2f}")
            for f in sr.findings[:2]:
                lines.append(f"  - {f}")

        # 运行时（委托）
        if report.runtime_audit:
            lines.append("\n## 运行时审计（EventAuditor + HealthMonitor）")
            ea = report.runtime_audit.get("event_auditor", {})
            if ea:
                lines.append(f"- 死信: {ea.get('total_stillborn',0)} stillborn → {len(ea.get('healed',[]))} healed")
            hm = report.runtime_audit.get("health_monitor", {})
            if hm:
                dims = hm.get("dimensions", {})
                if dims:
                    warn_dims = [k for k, v in hm.get("statuses", {}).items() if v == "warn"]
                    if warn_dims:
                        lines.append(f"- 健康警告: {', '.join(warn_dims[:5])}")

        # 依赖
        deps = report.deps
        if deps.get("cycles"):
            lines.append(f"\n## 循环依赖")
            for c in deps["cycles"]:
                lines.append(f"- ⚠️ {c}")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# Singleton + 便捷入口
# ═══════════════════════════════════════════════════════════════════

_auditor: Optional[SelfAuditor] = None

def get_self_auditor() -> SelfAuditor:
    global _auditor
    if _auditor is None:
        _auditor = SelfAuditor()
        _auditor.load()
    return _auditor


async def run_full_audit() -> Dict[str, Any]:
    return await get_self_auditor().orchestrate_all()
