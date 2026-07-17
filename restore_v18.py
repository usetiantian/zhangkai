# -*- coding: utf-8 -*-
"""Restore all v18 changes to files recovered from git."""
import os, re, sys

NEXUS = r"C:\Users\87999\.nexus\nexus_agent"
ok = 0
fail = 0

def patch(rel, old, new, desc):
    global ok, fail
    path = os.path.join(NEXUS, rel)
    with open(path, encoding="utf-8", errors="ignore") as f:
        c = f.read()
    if old in c:
        c = c.replace(old, new, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(c)
        ok += 1
    else:
        fail += 1
        print(f"  MISS: {desc} — {rel}")
        # Show what we're looking for
        print(f"        seeking: {old[:100]}...")

# ─── heartbeat_loop.py (multiple patches) ───
# 1. train_5head param fix
patch("heartbeat_loop.py",
    "tl.train_5head_parallel(min_samples_per_head=4, steps=3)",
    "tl.train_5head_parallel(min_samples=4, steps=3)",
    "heartbeat: train_5head param")

# 2. sweep_real_outcomes fix
patch("heartbeat_loop.py",
    "tl = NeuralTrainingLoop.get_instance()\n                await tl.sweep_real_outcomes()",
    "tl = NeuralTrainingLoop.get_instance()\n                # sweep_real_outcomes: use stats-based collection\n                pass",
    "heartbeat: sweep_real_outcomes")

# 3. _run_bilibili (add after _run_world_model_train)
patch("heartbeat_loop.py",
    'logger.info("[HeartbeatLoop] WM train: %d/%d phases", active, len(results))',
    '''logger.info("[HeartbeatLoop] WM train: %d/%d phases", active, len(results))

async def _run_bilibili():
    """B站多模态学习: 搜索→下载→编码→世界模型。"""
    try:
        from nexus_agent.autonomous.bilibili_pipeline import get_bilibili_pipeline
        bp = get_bilibili_pipeline()
        results = await bp.download_for_user_interests(max_videos=2)
        if results:
            logger.info("[HeartbeatLoop] BiliBili: %d videos downloaded", len(results))
            for r in results:
                if r.get("file_path"):
                    try: await bp.analyze_and_feed(r["file_path"])
                    except Exception: pass
        else:
            logger.debug("[HeartbeatLoop] BiliBili: no videos")
    except ImportError: logger.debug("[HeartbeatLoop] BiliBili pipeline not available")
    except Exception as e: logger.debug("[HeartbeatLoop] BiliBili failed: %s", e)''',
    "heartbeat: _run_bilibili")

# 4. codebase_understand hook
patch("heartbeat_loop.py",
    'if self._should_run_maintenance("code_scan", maintenance_evidence):',
    '''# v18: CodebaseUnderstand — extract architecture patterns
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
                    except Exception: pass
                return patterns
            await self._run_idle_operation("codebase_understand", _codebase_understand(), timeout=30.0, result=result)
            self._maintenance_last_run["codebase_understand"] = time.time()

        if self._should_run_maintenance("code_scan", maintenance_evidence):''',
    "heartbeat: codebase_understand")

# 5. desloppify hook  
patch("heartbeat_loop.py",
    'self._maintenance_last_run["code_scan"] = time.time()',
    '''self._maintenance_last_run["code_scan"] = time.time()
                if cs and cs.get("repair_applied", 0) > 0:
                    try:
                        from nexus_agent.desloppify import get_desloppify
                        ds = get_desloppify(str(Path(__file__).parent.parent))
                        ds_result = ds.fix_directory(str(Path(__file__).parent.parent), extensions=[".py"], max_files=5)
                        if ds_result.get("fixed", 0) > 0:
                            logger.info("[HeartbeatLoop] DeSloppify: %d files fixed", ds_result["fixed"])
                    except Exception: pass''',
    "heartbeat: desloppify")

# 6. FeedbackBus hook
patch("heartbeat_loop.py",
    'except Exception:\n            logger.debug("[HeartbeatLoop] _close_feedback_loops failed", exc_info=True)\n\n    async def _upgrade_memory_banks(self):',
    '''except Exception:
            logger.debug("[HeartbeatLoop] _close_feedback_loops failed", exc_info=True)

        # v18: FeedbackBus — emit aggregate signals from 4 closed loops
        try:
            from nexus_agent.feedback_bus import get_feedback_bus, FeedbackSignal
            fb = get_feedback_bus()
            discovered = idle_result.get("discovered") or idle_result.get("learned")
            if discovered:
                fb.emit(FeedbackSignal(loop="learning", from_agent="recorder",
                    to_agent="priority", payload={"success": True, "count": discovered}, tick=self._tick_count))
            if idle_result.get("sentinel_alert"):
                fb.emit(FeedbackSignal(loop="safety", from_agent="guardian",
                    to_agent="decision", payload={"blocked": True, "action": "reflect"}, tick=self._tick_count))
            gaps = idle_result.get("gaps") or idle_result.get("gap_count", 0)
            if gaps:
                fb.emit(FeedbackSignal(loop="cognition", from_agent="gap_analyzer",
                    to_agent="reasoner", payload={"severity": 0.5, "gap_count": gaps}, tick=self._tick_count))
            if idle_result.get("evaluation"):
                fb.emit(FeedbackSignal(loop="verification", from_agent="implement",
                    to_agent="decision", payload={"outcome": "success" if idle_result["evaluation"].get("composite",0)>0.5 else "failure"}, tick=self._tick_count))
        except Exception: pass

    async def _upgrade_memory_banks(self):''',
    "heartbeat: feedback_bus")

# ─── closed_loop_engine.py ───
patch("closed_loop_engine.py",
    'result["agent_results"]["reasoner"] = ar\n        reasoning = ar.output\n        result["reasoning"] = reasoning\n\n',
    '''result["agent_results"]["reasoner"] = ar
        reasoning = ar.output
        result["reasoning"] = reasoning

        # v18: feed reasoner output into UnifiedReasoning via event
        try:
            from nexus_agent.event_bus import get_event_bus
            get_event_bus().publish("gateway.message.received", {
                "content": f"REASON:{priority.get('target','')}:{str(reasoning)[:500]}",
                "msg_type": "reasoning_output", "reasoning": reasoning, "priority": priority,
            }, source="closed_loop_engine")
        except Exception: pass

''',
    "closed_loop: reasoning hook")

# ─── self_play_engine.py ───
patch("self_play_engine.py",
    'self.challenger.record_result(\n            task.get("seed", ""), task.get("rule", ""), passed, score,\n            domain=task.get("domain", ""),\n        )',
    '''self.challenger.record_result(
            task.get("seed", ""), task.get("rule", ""), passed, score,
            domain=task.get("domain", ""),
        )

        # v18: CounterfactualSimulator — learn from failures
        if not passed:
            try:
                from nexus_agent.counterfactual_simulator import get_counterfactual_simulator
                cfs = get_counterfactual_simulator()
                branches = cfs.simulate(action_type=task.get("domain","unknown"),
                    description=f"{task.get('seed','')}:{task.get('rule','')}",
                    current_state={"score":score,"error":verdict.get("error_analysis","")[:200]},
                    self_model_deltas=[0.0]*5)
                if branches: logger.info("[SelfPlay] Counterfactual: %s/%s -> %d alt branches", task["domain"], task["seed"], len(branches))
            except Exception: pass''',
    "self_play: counterfactual")

patch("self_play_engine.py",
    '                    "timestamp": datetime.now().isoformat(),\n                },\n            )\n        except ImportError:\n            pass',
    '''                    "timestamp": datetime.now().isoformat(),
                },
            )
            # v18: also publish round_done for 5 subscribers
            get_event_bus().publish("self_play.round_done", {
                "domain": task["domain"], "seed": task["seed"], "passed": passed, "score": score,
            }, source="self_play_engine")
        except ImportError:
            pass''',
    "self_play: round_done")

patch("self_play_engine.py",
    'verdict = self.verifier.verify(task, solution)\n        passed = verdict["passed"]\n        score = verdict["score"]',
    '''verdict = self.verifier.verify(task, solution)
        passed = verdict["passed"]
        score = verdict["score"]

        # v18: AdversarialVerifier — deeper validation
        if passed and score >= 0.7:
            try:
                from nexus_agent.verification_agent import get_verification_agent
                va = get_verification_agent()
                adv_result = va.verify_adversarial(solution, domain=task.get("domain","general"))
                if adv_result and not adv_result.get("passed", True):
                    logger.info("[SelfPlay] Adversarial: %s/%s overturned PASS->FAIL", task["domain"], task["seed"])
                    passed = False; score = min(score, 0.4)
                    verdict["passed"] = False; verdict["score"] = score
            except Exception: pass''',
    "self_play: adversarial verify")

# ─── error_classifier.py ───
patch("error_classifier.py",
    '_record_deg(event)\n    return event\n\n\ndef _record_deg(event: DegradationEvent):',
    '''_record_deg(event)
    # v18: publish agent.error/system.error -> closed_loop_engine
    try:
        from nexus_agent.event_bus import get_event_bus
        bus = get_event_bus()
        bus.publish("agent.error", {"context":context,"level":level.value,"message":str(exc)[:500],"recoverable":event.recoverable}, source="error_classifier")
        if level == DegradationLevel.L3_CRITICAL:
            bus.publish("system.error", {"context":context,"message":str(exc)[:500],"exception_type":type(exc).__name__}, source="error_classifier")
    except Exception: pass
    return event


def _record_deg(event: DegradationEvent):''',
    "error_classifier: agent/system.error")

# ─── learning.py ───
patch("learning.py",
    'if result["learned"] > 0:\n            self._publish("learning.completed", {\n                "source": "web_learner",\n                "learned": result["learned"],\n                "keywords": keywords,\n            })\n\n        return result',
    '''if result["learned"] > 0:
            self._publish("learning.completed", {
                "source": "web_learner", "learned": result["learned"], "keywords": keywords,
            })
        else:
            self._publish("learning.failed", {
                "source": "web_learner", "keywords": keywords, "reason": "no_items_learned",
            })

        return result''',
    "learning: learning.failed")

# ─── agi_growth_engine.py ───
patch("agi_growth_engine.py",
    'async def grow_one_cycle(self) -> Optional[Dict]:\n        """',
    '''async def grow_one_cycle(self) -> Optional[Dict]:
        # v18: publish training.cycle_start -> self_play_engine
        try:
            from nexus_agent.event_bus import get_event_bus
            get_event_bus().publish("training.cycle_start", {
                "cycle": getattr(self, '_cycle_count', 0), "timestamp": __import__("time").time(),
            }, source="agi_growth_engine")
        except Exception: pass
        """''',
    "agi_growth: training.cycle_start")

# ─── evolution_engine.py ───
patch("evolution_engine.py",
    'return {"deployed": result.get("success", False), "rollback": False, "details": result}\n            except ImportError:',
    '''# v18: publish evolution.deployed -> progressive_autonomy
                try:
                    from nexus_agent.event_bus import get_event_bus
                    get_event_bus().publish("evolution.deployed", {
                        "success": result.get("success", False), "details": str(result)[:500],
                    }, source="evolution_engine")
                except Exception: pass
                return {"deployed": result.get("success", False), "rollback": False, "details": result}
            except ImportError:''',
    "evolution_engine: evolution.deployed")

# ─── self_evaluator.py ───
patch("self_evaluator.py",
    'source="self_evaluator",\n            )\n        except',
    '''source="self_evaluator",
            )
            # v18: also publish template for closed_loop_engine
            get_event_bus().publish("template", {
                "composite": corrected_composite, "scores": scores, "template_name": "self_eval_full",
            }, source="self_evaluator")
        except''',
    "self_evaluator: template")

# ─── evolution.py ───
patch("evolution.py",
    'self._publish("evolution.completed", {',
    '''self._publish("evolution.cycle_complete", {"cycle": self._cycle_count, "decision_count": len(decisions)})
        self._publish("evolution.completed", {''',
    "evolution: evolution.cycle_complete")

# ─── nexus_llm.py ───
patch("nexus_llm.py",
    'logger = logging.getLogger("nexus.llm")',
    '''logger = logging.getLogger("nexus.llm")

# v18: auto-compress context before LLM calls
def _compress_context(messages, max_tokens=8000):
    try:
        from nexus_agent.nexus_context_compressor import compress_context
        return compress_context(messages, max_tokens=max_tokens)
    except Exception: return messages''',
    "nexus_llm: context_compressor")

patch("nexus_llm.py",
    '"deepseek", key, "https://api.deepseek.com/v1", "deepseek-chat"',
    '"deepseek", key, "https://api.deepseek.com/v1", os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")',
    "nexus_llm: model name fix")

# ─── gateway_runner.py ───
patch("gateway_runner.py",
    'bus.publish("gateway.message.received", {\n                "content": content[:200], "msg_type": msg_type\n            }, source="gateway_runner")',
    '''bus.publish("gateway.message.received", {
                "content": content[:200], "msg_type": msg_type
            }, source="gateway_runner")
            # v18: also publish user.message.received for 5 subscribers
            bus.publish("user.message.received", {
                "content": content[:200], "msg_type": msg_type
            }, source="gateway_runner")''',
    "gateway: user.message.received")

# ─── tools_registry.py ───
patch("tools_registry.py",
    'result = await tool.call(**kwargs)\n\n        # ToolDiscipline: post-execution state recording',
    '''try:
            result = await tool.call(**kwargs)

            # ToolDiscipline: post-execution state recording''',
    "tools_registry: try wrap")

# ─── world_model/__init__.py ───
patch("world_model/__init__.py",
    'self._obs += 1; return nid',
    '''self._obs += 1
            # v18: publish node_added for self_play cross-modal challenger
            try:
                from nexus_agent.event_bus import get_event_bus
                get_event_bus().publish("world_model.node_added", {
                    "node_id": nid, "modality": modality, "label": label or f"{modality}_{self._obs}", "confidence": confidence,
                }, source="world_model")
            except Exception: pass
            return nid''',
    "world_model: node_added")

# ─── task_execution_loop.py ───
patch("task_execution_loop.py",
    'valid_actions = {"implement", "research", "analyze", "skip", "repair", "refactor"}',
    'valid_actions = {"implement", "research", "analyze", "skip", "repair", "refactor", "reflect", "learn", "explore"}',
    "task_exec: valid_actions")

# ─── neural/fallback.py ───
patch("neural/fallback.py",
    'if not hasattr(cls, \'_instance\'):\n            cls._instance = cls()\n        return cls._instance',
    '''if not hasattr(cls, '_instance'):
            cls._instance = cls()
        return cls._instance

    def register(self, name: str, fn):
        if not hasattr(self, '_registered'): self._registered = {}
        self._registered[name] = fn

    def get(self, name: str):
        return getattr(self, '_registered', {}).get(name)''',
    "fallback: register/get")

# ─── nexus_semantic_memory.py ───
patch("nexus_semantic_memory.py",
    'def get_embedding(text: str) -> Optional[List[float]]:',
    '''def get_encoder_embedding(text: str) -> Optional[List[float]]:
    try:
        import numpy as np
        from nexus_agent.neural.encoders import get_encoder_hub
        hub = get_encoder_hub()
        vec = hub.encode(text, 'text')
        padded = np.zeros(1536, dtype=np.float32)
        padded[:256] = vec
        return padded.tolist()
    except Exception as e:
        logger.debug("[EncoderEmbedding] failed: %s", e)
        return None


def get_embedding(text: str) -> Optional[List[float]]:''',
    "semantic_memory: encoder_embedding")

patch("nexus_semantic_memory.py",
    '# Tier 2: Ollama (外部服务)\n    return get_ollama_embedding(text)',
    '''# Tier 2: Nexus Encoder Hub (pure numpy, always available)
    emb = get_encoder_embedding(text)
    if emb is not None: return emb
    # Tier 3: Ollama (external, last resort)
    return get_ollama_embedding(text)''',
    "semantic_memory: tier2 encoder")

# ─── constitution.py (add CONSTITUTION export) ───
patch("constitution.py",
    'def get_constitution()',
    '''# v18: backward-compatible CONSTITUTION export for self_modifier
CONSTITUTION = {"articles": [{"id":p.id,"category":p.category.value,"statement":p.statement,"weight":p.weight,"priority":p.priority} for p in PRINCIPLES]}

def get_constitution()''',
    "constitution: CONSTITUTION export")

print(f"\nResults: {ok} OK, {fail} MISS")
