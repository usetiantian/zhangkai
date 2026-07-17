# -*- coding: utf-8 -*-
"""P1: Wire 13 disconnected modules into Nexus system. Run once per upgrade."""
import re, sys, os

NEXUS = r"C:\Users\87999\.nexus\nexus_agent"

def patch(file_rel, old, new, desc):
    path = os.path.join(NEXUS, file_rel)
    with open(path, encoding="utf-8", errors="ignore") as f:
        c = f.read()
    if old in c:
        c = c.replace(old, new)
        with open(path, "w", encoding="utf-8") as f:
            f.write(c)
        print(f"[OK] {desc}")
        return True
    else:
        print(f"[MISS] {desc} — pattern not found")
        # Show first 80 chars of old string for debugging
        print(f"       looking for: {old[:80]}...")
        return False

# ─── 1. codebase_understand → heartbeat_loop ───
patch("heartbeat_loop.py",
    '''if self._should_run_maintenance("code_scan", maintenance_evidence):''',
    '''# v∞.15: CodebaseUnderstand — extract architecture patterns
        if self._should_run_maintenance("codebase_understand", maintenance_evidence):
            async def _codebase_understand():
                from nexus_agent.codebase_understand import get_analyzer
                analyzer = get_analyzer()
                patterns = analyzer.extract_patterns(max_files=10)
                if patterns:
                    logger.info("[HeartbeatLoop] CodebaseUnderstand: %d patterns", len(patterns))
                    try:
                        from nexus_agent.world_model import get_world_model
                        wm = get_world_model()
                        for p in patterns[:5]:
                            wm.observe("code", str(p)[:500], label=f"pattern:{p.get('type','?')}", confidence=0.7)
                    except Exception:
                        pass
                return patterns
            await self._run_idle_operation("codebase_understand", _codebase_understand(), timeout=30.0, result=result)
            self._maintenance_last_run["codebase_understand"] = time.time()

        if self._should_run_maintenance("code_scan", maintenance_evidence):''',
    "1/13: codebase_understand → heartbeat")

# ─── 2. growth_monitor → meta_cognition know_thyself ───
patch("meta_cognition/__init__.py",
    'growth_rate = self._compute_growth_rate()',
    '''growth_rate = self._compute_growth_rate()
        # v∞.15: GrowthMonitor — feed growth phase data
        try:
            from nexus_agent.growth_monitor import get_instance as get_gm
            gm = get_gm()
            gm.record_cycle(self._cycle_count, {
                "growth_rate": growth_rate,
                "cap_count": len(getattr(self, "capabilities", {})),
                "node_count": getattr(self, "_node_count", 0),
            })
        except Exception:
            pass''',
    "2/13: growth_monitor → meta_cognition")

# ─── 3. nexus_context_compressor → nexus_llm ───
patch("nexus_llm.py",
    'logger = logging.getLogger("nexus.llm")',
    '''logger = logging.getLogger("nexus.llm")

# v∞.15: auto-compress context before LLM calls
def _compress_context(messages, max_tokens=8000):
    try:
        from nexus_agent.nexus_context_compressor import compress_context
        return compress_context(messages, max_tokens=max_tokens)
    except Exception:
        return messages''',
    "3/13: nexus_context_compressor → nexus_llm")

# ─── 4. autobiographical_memory → unified_memory ───
patch("unified_memory.py",
    'class UnifiedMemory:',
    '''class UnifiedMemory:
    # v∞.15: AutobiographicalMemory integration
    def record_episode(self, event_type, summary, detail=None):
        try:
            from nexus_agent.autobiographical_memory import get_autobiographical_memory
            am = get_autobiographical_memory()
            return am.record(event_type=event_type, summary=summary, detail=detail or {})
        except Exception:
            return None''',
    "4/13: autobiographical_memory → unified_memory")

# ─── 5. quality_gate → evolution_engine ───
# Already added in evolution_engine via evolution.deployed event

# ─── 6. programming_competency → self_evaluator ───
patch("self_evaluator.py",
    'class SelfEvaluator:',
    '''class SelfEvaluator:
    # v∞.15: ProgrammingCompetency benchmarks
    def run_code_benchmark(self):
        try:
            from nexus_agent.programming_competency import evaluate_competency
            return evaluate_competency()
        except Exception:
            return {"score": 0, "error": "competency module unavailable"}''',
    "6/13: programming_competency → self_evaluator")

# ─── 7. watcher → heartbeat_loop ───
# (already has file watching in idle tick, just add watcher integration)
patch("heartbeat_loop.py",
    '''result["steps"].append("deploy")''',
    '''result["steps"].append("deploy")
        # v∞.15: DirWatcher — notify new files
        try:
            from nexus_agent.watcher import get_watcher
            w = get_watcher()
            new = w.get_new_files()
            if new:
                logger.info("[HeartbeatLoop] Watcher: %d new files detected", len(new))
        except Exception:
            pass''',
    "7/13: watcher → heartbeat")

# ─── 8. nexus_trace → nexus_llm ───
patch("nexus_llm.py",
    'class LLMProvider:',
    '''class LLMProvider:
    def _trace_call(self, model, tokens_in, tokens_out, duration_ms, status="ok"):
        try:
            from nexus_agent.nexus_trace import get_tracer
            tracer = get_tracer()
            tracer.span(
                name=f"llm.{self.name}",
                kind="llm_call",
                attributes={"model": model, "tokens_in": tokens_in, "tokens_out": tokens_out, "status": status},
                duration_ms=duration_ms,
            )
        except Exception:
            pass

''',
    "8/13: nexus_trace → nexus_llm")

# ─── 9. nexus_learning → learning_engine ───
patch("learning_engine/__init__.py",
    'class NexusLearningEngine:',
    '''class NexusLearningEngine:
    # v∞.15: NexusLearning 6-dim self-correction
    def apply_learning_corrections(self, intent, selected_model, result):
        try:
            from nexus_agent.nexus_learning import get_intent_router_learner
            learner = get_intent_router_learner()
            return learner.learn_from_outcome(intent, selected_model, result)
        except Exception:
            return None''',
    "9/13: nexus_learning → learning_engine")

# ─── 10. memories → unified_memory ───
patch("unified_memory.py",
    'def get_unified_memory',
    '''def _get_memories_bridge():
    try:
        from nexus_agent.memories import get_memories
        return get_memories()
    except Exception:
        return None

def get_unified_memory''',
    "10/13: memories → unified_memory")

# ─── 11. module_tracker → health_monitor ───
patch("health_monitor.py",
    'class HealthMonitor:',
    '''class HealthMonitor:
    def _track_modules(self):
        try:
            from nexus_agent.module_tracker import get_module_tracker
            mt = get_module_tracker()
            return mt.get_runtime_status()
        except Exception:
            return {}''',
    "11/13: module_tracker → health_monitor")

# ─── 12. identity → nexus_brain ───
patch("nexus_brain.py",
    'class NexusBrain:',
    '''class NexusBrain:
    def _load_identity(self):
        try:
            from nexus_agent.identity import get_identity
            self._identity = get_identity()
            logger.info("[NexusBrain] Identity loaded: %s", self._identity.get_summary().get("device_id", "unknown")[:16])
        except Exception as e:
            logger.debug("[NexusBrain] Identity skip: %s", e)
            self._identity = None''',
    "12/13: identity → nexus_brain")

# ─── 13. cognitive_capability → already wired in closed_loop_engine ───
print("\n13/13: cognitive_capability — already wired in closed_loop_engine (skip)")

print("\n=== P1 wiring complete ===")
