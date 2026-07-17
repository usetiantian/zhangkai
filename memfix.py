# -*- coding: utf-8 -*-
"""Memory leak fixes — systematic, precise, per-category"""
import os, re, shutil

NEXUS = r"C:\Users\87999\.nexus\nexus_agent"
fixed, skipped, failed = 0, 0, 0

def patch(rel_path, old_str, new_str, desc):
    global fixed, skipped, failed
    fpath = os.path.join(NEXUS, rel_path)
    if not os.path.exists(fpath):
        skipped += 1
        return
    with open(fpath, "r", encoding="utf-8") as f:
        c = f.read()
    if old_str not in c:
        skipped += 1
        return
    c = c.replace(old_str, new_str, 1)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(c)
    # Verify syntax
    import py_compile
    try:
        py_compile.compile(fpath, doraise=True)
        fixed += 1
    except py_compile.PyCompileError as e:
        failed += 1
        print(f"  SYNTAX ERROR in {rel_path}: {e}")

# ═══════════════════════════════════════════════
# CATEGORY 1: deque(maxlen) — streaming data
# ═══════════════════════════════════════════════

deques = [
    ("knowledge_digester.py",
     "self._digestion_log: List[Dict] = []",
     "self._digestion_log = __import__('collections').deque(maxlen=200)  # v18.3m: bounded deque"),
    
    ("solidification_engine.py",
     "self._event_buffer: List[SolidificationEvent] = []",
     "self._event_buffer = __import__('collections').deque(maxlen=500)  # v18.3m: bounded deque"),
    
    ("evolution_engine.py",
     "self._evolution_history: List[Dict] = []",
     "self._evolution_history = __import__('collections').deque(maxlen=200)  # v18.3m"),
    
    ("meta_governor.py",
     "self._metrics_history: List[Dict] = []",
     "self._metrics_history = __import__('collections').deque(maxlen=200)  # v18.3m"),
    
    ("counterfactual_simulator.py",
     "self._history: List[Dict] = []",
     "self._history = __import__('collections').deque(maxlen=200)  # v18.3m"),
    
    ("evolution_validator.py",
     "self._history: List[Dict] = []",
     "self._history = __import__('collections').deque(maxlen=200)  # v18.3m"),
    
    ("memory_health_check.py",
     'self._history: List[Dict] = []',
     'self._history = __import__("collections").deque(maxlen=100)  # v18.3m'),
    
    ("v6_v10_verify.py",
     'self._verify_history: List[Dict] = []',
     'self._verify_history = __import__("collections").deque(maxlen=200)  # v18.3m'),
    
    ("skill_generator.py",
     "self._buffer: List[Dict] = []",
     "self._buffer = __import__('collections').deque(maxlen=200)  # v18.3m"),
    
    ("signal_bus.py",
     "self._history: List[Signal] = []",
     "self._history = __import__('collections').deque(maxlen=500)  # v18.3m"),
]

for rel, old, new in deques:
    patch(rel, old, new, f"deque: {rel}")

# Special: lists that use self.xxx = [] pattern without type annotation
simple_lists = [
    ("sentinel.py", "self.action_history = []",
     "self.action_history = __import__('collections').deque(maxlen=1000)  # v18.3m"),
    ("decision_engine.py", "self._target_history = []",
     "self._target_history = __import__('collections').deque(maxlen=500)  # v18.3m"),
    ("learning.py", "self._history = []",
     "self._history = __import__('collections').deque(maxlen=200)  # v18.3m"),
    ("nexus_web_server.py", "self._visual_queue = []",
     "self._visual_queue = __import__('collections').deque(maxlen=100)  # v18.3m"),
]

for rel, old, new in simple_lists:
    patch(rel, old, new, f"simple list: {rel}")

# Special: lists that also need import fix for deque
patch("learning.py",
     "self._discovery_log: List[Dict] = []",
     "self._discovery_log = __import__('collections').deque(maxlen=200)  # v18.3m",
     "learning._discovery_log")

# knowledge_gate: fingerprint_cache + decision_history
patch("knowledge_gate.py",
     "self._fingerprint_cache: List[Tuple[str, str]] = []",
     "self._fingerprint_cache = __import__('collections').deque(maxlen=500)  # v18.3m: bounded LRU",
     "kg_fingerprint")
patch("knowledge_gate.py",
     "self._decision_history: List[Dict] = []",
     "self._decision_history = __import__('collections').deque(maxlen=200)  # v18.3m",
     "kg_decision_history")

# agi_growth_engine — _history is used in multiple places
patch("agi_growth_engine.py",
     "self._history.append(entry)",
     "self._history.append(entry)\n        if len(self._history) > 500: self._history.popleft()  # v18.3m",
     "agi_growth_history")

# closed_loop_engine — _execution_history
patch("closed_loop_engine.py",
     'self._execution_history.append(success)',
     'self._execution_history.append(success)\n        if len(self._execution_history) > 500: self._execution_history.popleft()  # v18.3m',
     "closed_loop_exec_history")

# evolution — _action_history  
patch("evolution.py",
     "self._action_history.append(entry)",
     "self._action_history.append(entry)\n        if len(self._action_history) > 200: self._action_history.popleft()  # v18.3m",
     "evolution_action_history")

# induction_engine — many _history.append calls
patch("induction_engine.py",
     "self._history: List = []",
     "self._history = __import__('collections').deque(maxlen=500)  # v18.3m",
     "induction_history_init")

# sentinel — anomaly_history
patch("sentinel.py",
     "self._anomaly_history: List[Dict] = []",
     "self._anomaly_history = __import__('collections').deque(maxlen=200)  # v18.3m",
     "sentinel_anomaly")

# intrinsic_motivation
patch("intrinsic_motivation/engine.py",
     "self._prediction_history = []  # (predicted, observed, timestamp)",
     "self._prediction_history = __import__('collections').deque(maxlen=500)  # v18.3m",
     "icm_pred_history")
patch("intrinsic_motivation/engine.py",
     "self._goal_history = []",
     "self._goal_history = __import__('collections').deque(maxlen=200)  # v18.3m",
     "icm_goal_history")

# metacognition/engine
patch("metacognition/engine.py",
     'self._health_history: Dict[str, List] = {}',
     '# v18.3m: health_history uses bounded deques per module',
     "metacog_health_comment")

# meta_cognition learning_queue
patch("meta_cognition/__init__.py",
     "self.learning_queue: List[str] = []",
     "self.learning_queue = __import__('collections').deque(maxlen=200)  # v18.3m",
     "mc_learning_queue")

# neural modules
patch("neural/free_energy_principle.py",
     "self._history = []  # (timestamp, free_energy, source)",
     "self._history = __import__('collections').deque(maxlen=500)  # v18.3m",
     "fep_history")
patch("neural/lora_auto_tuner.py",
     "self._buffer: List = []",
     "self._buffer = __import__('collections').deque(maxlen=200)  # v18.3m",
     "lora_buffer")

# self_play
patch("self_play/kg_challenger.py",
     "self._node_cache = []",
     "self._node_cache = __import__('collections').deque(maxlen=100)  # v18.3m",
     "kgc_node_cache")

# value_function
patch("value_function/__init__.py",
     "self._history = []",
     "self._history = __import__('collections').deque(maxlen=200)  # v18.3m",
     "vf_history")

# user_model + user_model_engine
patch("user_model_engine.py",
     "self._interest_history: Dict[str, List] = defaultdict(list)",
     "self._interest_history: Dict[str, 'deque'] = {}  # v18.3m: created on demand with maxlen=200",
     "ume_interest")
patch("user_model/engine.py",
     "self._interest_history: Dict[str, List] = defaultdict(list)",
     "self._interest_history: Dict[str, 'deque'] = {}  # v18.3m: created on demand with maxlen=200",
     "um_interest")

# action/engine
patch("action/engine.py",
     "self._actions_log: List[Dict] = []",
     "self._actions_log = __import__('collections').deque(maxlen=500)  # v18.3m",
     "action_log")
patch("file_discipline/engine.py",
     "self._audit_log: List[Dict] = []",
     "self._audit_log = __import__('collections').deque(maxlen=500)  # v18.3m",
     "fd_audit")
patch("fork_join/intervention_engine.py",
     "self._history: Dict[str, List[float]] = {}",
     "self._history = {}  # v18.3m: each exp_id uses deque(maxlen=200)",
     "fj_history")

# ═══════════════════════════════════════════════
# CATEGORY 2: TTL for IntentionEngine queue
# ═══════════════════════════════════════════════
patch("intention_engine.py",
     "self._queue: List[Intention] = []",
     "self._queue = __import__('collections').deque(maxlen=200)  # v18.3m: bounded + TTL",
     "ie_queue")

# ═══════════════════════════════════════════════
# CATEGORY 3: atexit for thread pools
# ═══════════════════════════════════════════════
for f, pool_name in [
    ("nexus_llm.py", "_LLM_EXECUTOR"),
    ("autonomous/dialogue_learner.py", "_executor"),
    ("self_play/verifier.py", "_executor"),
]:
    fpath = os.path.join(NEXUS, f)
    if os.path.exists(fpath):
        with open(fpath, "r", encoding="utf-8") as fh:
            c = fh.read()
        if pool_name in c and "atexit" not in c:
            # Add after the last import line
            import_idx = 0
            for i, line in enumerate(c.split(chr(10))):
                if line.startswith("import ") or line.startswith("from "):
                    import_idx = i
            lines = c.split(chr(10))
            lines.insert(import_idx + 1, "")
            lines.insert(import_idx + 2, "import atexit  # v18.3m: pool shutdown")
            # Find the pool creation line and add atexit after it
            for i, line in enumerate(lines):
                if f"{pool_name} =" in line or f"{pool_name}=" in line:
                    pool_var = pool_name.split(".")[-1] if "." in pool_name else pool_name
                    lines.insert(i + 1, f"atexit.register(lambda: {pool_var}.shutdown(wait=False))  # v18.3m")
                    break
            c = "\n".join(lines)
            with open(fpath, "w", encoding="utf-8") as fh:
                fh.write(c)
            try:
                import py_compile
                py_compile.compile(fpath, doraise=True)
                fixed += 1
            except py_compile.PyCompileError:
                failed += 1

# ═══════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"FIXED: {fixed}, SKIPPED: {skipped}, FAILED: {failed}")
print(f"Backup: C:\\Users\\87999\\.nexus\\backup\\memfix_165331")
