# -*- coding: utf-8 -*-
"""v18.3: NexusSelf 七模块闭环 — cycle.summary handler + advisor pipeline"""
import py_compile

path = r"C:\Users\87999\.nexus\nexus_agent\nexus_self.py"
with open(path, "r", encoding="utf-8") as f:
    c = f.read()

# 1. Add subscribe_to_cycle_summary + _on_cycle_summary + advisor methods
# Insert after the _on_directive_response method
idx = c.find("def _on_directive_response")
rest = c[idx:]
next_def = rest.find("\n    def ", 10)
insert_point = idx + next_def

new_methods = """

    # ================================================================
    # v18.3: cycle.summary handler - HeartbeatLoop reports -> NexusSelf decides
    # ================================================================

    def subscribe_to_cycle_summary(self):
        try:
            from nexus_agent.event_bus import get_event_bus
            get_event_bus().subscribe("cycle.summary", self._on_cycle_summary)
            logger.info("[NexusSelf] Subscribed to cycle.summary")
        except Exception:
            logger.debug("cycle.summary subscribe failed", exc_info=True)

    def _on_cycle_summary(self, event):
        data = event.data if hasattr(event, "data") else {}
        tasks = data.get("tasks", {})
        if not tasks:
            return
        tick = data.get("tick", 0)
        logger.info("[NexusSelf] === Cycle #%d: %d tasks ===", tick, len(tasks))
        
        # Step 1: reconcile
        self._reconcile_with_goals(tasks, data)
        # Step 2: consult advisors
        analysis = self._consult_advisors(data)
        # Step 3: decide
        self._decide_from_analysis(analysis, data)

    def _reconcile_with_goals(self, tasks, data):
        for goal in list(self._goal_board.values()):
            if goal.status != "ACTIVE":
                continue
            phase = goal.current_phase_obj()
            if phase is None or phase.status != "ACTIVE":
                continue
            subsystem = phase.assigned_to or ""
            metric = goal.target_metric or ""
            for task_name, result in tasks.items():
                if subsystem in task_name or metric.split(":")[0] in task_name:
                    status = result.get("status", "") if isinstance(result, dict) else ""
                    if status in ("triggered", "ok", "completed"):
                        Report = type("Report", (), {})
                        r = Report()
                        r.parent_goal_id = goal.goal_id
                        r.phase_id = phase.phase_id
                        r.outcome = "phase_completed"
                        r.summary = str(result)[:200]
                        r.subsystem = task_name
                        self._progress_reports.append(r)
                        logger.info("[NexusSelf] Goal '%s' phase %d done by %s",
                                   goal.title[:60], phase.phase_id, task_name)
                        self._evaluate_goal(goal)

    def _consult_advisors(self, data):
        analysis = {"patterns": [], "root_causes": [], "lessons": []}
        # Advisor 1: MetaCognition
        try:
            from nexus_agent.meta_cognition import get_meta_cognition
            mc = get_meta_cognition()
            if hasattr(mc, "_detect_behavior_patterns"):
                from nexus_agent.autobiographical_memory import get_autobiographical_memory
                abm = get_autobiographical_memory()
                recent = abm.get_recent_episodes(limit=20) if hasattr(abm, "get_recent_episodes") else []
                patterns = mc._detect_behavior_patterns(recent) if recent else []
                if patterns:
                    analysis["patterns"] = patterns
                    logger.info("[NexusSelf] MetaCognition: %d patterns", len(patterns))
        except Exception as e:
            logger.debug("[NexusSelf] MetaCognition: %s", e)
        # Advisor 2: CausalEngine
        try:
            from nexus_agent.causal_engine import get_causal_engine
            ce = get_causal_engine()
            if hasattr(ce, "graph") and hasattr(ce.graph, "get_effects"):
                composite = data.get("evaluation", {}).get("composite", 0.5)
                if composite < 0.6:
                    effects = ce.graph.get_effects("low_composite_score")
                    if effects:
                        analysis["root_causes"] = [{"effect": e[0], "weight": e[1]} for e in effects[:3]]
                        logger.info("[NexusSelf] CausalEngine: %d root causes", len(effects))
        except Exception as e:
            logger.debug("[NexusSelf] CausalEngine: %s", e)
        # Advisor 3: SelfReflection
        try:
            from nexus_agent.self_reflection import get_self_reflection
            sr = get_self_reflection()
            if hasattr(sr, "step"):
                decision = sr.step()
                if decision and not decision.get("skipped"):
                    analysis["lessons"] = [decision]
                    logger.info("[NexusSelf] SelfReflection: lesson from past")
        except Exception as e:
            logger.debug("[NexusSelf] SelfReflection: %s", e)
        return analysis

    def _decide_from_analysis(self, analysis, data):
        patterns = analysis.get("patterns", [])
        root_causes = analysis.get("root_causes", [])
        lessons = analysis.get("lessons", [])
        # Decision 1: root cause + lesson -> corrective goal
        if root_causes and lessons:
            rc = root_causes[0]
            cause = rc.get("effect", str(rc))
            lesson_text = str(lessons[0])[:200] if lessons else "apply past solution"
            Goal = type("Goal", (), {})
            Phase = type("Phase", (), {})
            g = Goal()
            g.goal_id = self._gen_id("RC")
            g.goal_type = "CORRECTIVE"
            g.title = "Fix root cause: " + cause[:60]
            g.description = "CausalEngine: " + cause + ". SelfReflection: " + lesson_text
            g.source_ring = "advisor_synthesis"
            g.target_metric = "root_cause:" + cause[:40]
            g.priority = 7.0
            g.reason = "Advisor-synthesized: " + cause[:80]
            g.lessons_learned = [lesson_text]
            g.progress_notes = []
            g.current_phase = 0
            g.completed_at = None
            g.status = "ACTIVE"
            p0 = Phase(); p0.phase_id = 0; p0.name = "Diagnose"; p0.status = "ACTIVE"; p0.assigned_to = "intention_engine"; p0.required_outcome = "verify root cause"
            p1 = Phase(); p1.phase_id = 1; p1.name = "Fix"; p1.status = "LOCKED"; p1.assigned_to = "evolution_engine"; p1.required_outcome = "apply fix"
            g.phases = [p0, p1]
            self._add_goal(g)
            logger.info("[NexusSelf] New corrective goal from advisors")
        # Decision 2: pattern only -> observation goal
        if patterns and not root_causes:
            for p in patterns[:2]:
                existing = [g for g in self._goal_board.values() if p[:30] in getattr(g, "title", "")]
                if not existing:
                    Goal = type("Goal", (), {})
                    Phase = type("Phase", (), {})
                    g = Goal()
                    g.goal_id = self._gen_id("PT")
                    g.goal_type = "OBSERVATION"
                    g.title = "Monitor: " + p[:60]
                    g.description = "MetaCognition detected: " + p
                    g.source_ring = "self_knowledge"
                    g.target_metric = "pattern:" + p[:40]
                    g.priority = 4.0
                    g.reason = p[:80]
                    g.lessons_learned = []
                    g.progress_notes = []
                    g.current_phase = 0
                    g.completed_at = None
                    g.status = "ACTIVE"
                    p0 = Phase(); p0.phase_id = 0; p0.name = "Monitor"; p0.status = "ACTIVE"; p0.assigned_to = "intention_engine"; p0.required_outcome = "observe"
                    g.phases = [p0]
                    self._add_goal(g)
        # Decision 3: update self-model
        evaluation = data.get("evaluation", {})
        composite = evaluation.get("composite", 0)
        if composite > 0:
            self._self_model["last_cycle_score"] = composite
            self._self_model["cycle_count"] = self._self_model.get("cycle_count", 0) + 1

"""

c = c[:insert_point] + new_methods + c[insert_point:]

# 2. Add subscription trigger in wake() — lazy subscribe on first pulse
wake_idx = c.find("async def wake")
wake_rest = c[wake_idx:]
# Find right after the throttling check
throttle_line = "return {\"status\": \"throttled\"}"
throttle_idx = wake_rest.find(throttle_line)
# Insert subscription after throttle check
old_wake = 'self._last_pulse_at = now\n        self._pulse_count += 1\n\n        self._clean_expired_directives()'
new_wake = '''self._last_pulse_at = now
        self._pulse_count += 1

        # v18.3: lazy subscribe to cycle.summary on first pulse
        if not self._cycle_summary_subscribed:
            self.subscribe_to_cycle_summary()
            self._cycle_summary_subscribed = True

        self._clean_expired_directives()'''

if old_wake in c:
    c = c.replace(old_wake, new_wake, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(c)

try:
    py_compile.compile(path, doraise=True)
    print("[OK] nexus_self.py compiles cleanly")
except py_compile.PyCompileError as e:
    print(f"ERROR: {e}")
