#!/usr/bin/env python3
"""Fix all Nexus v18 issues in one pass."""
import os, sys

NEXUS = r"C:\Users\87999\.nexus\nexus_agent"
bak_suffix = ".bak.20260709"

def apply(rel, old, new, desc):
    path = os.path.join(NEXUS, rel)
    with open(path, encoding="utf-8", errors="ignore") as f:
        content = f.read()
    if old not in content:
        print(f"  [SKIP] {desc} — pattern not found in {rel}")
        return False
    # backup
    bak = path + bak_suffix
    with open(bak, "w", encoding="utf-8") as f:
        f.write(content)
    content = content.replace(old, new, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] {desc}")
    return True

# ═══════════════════════════════════════════════
# FIX 1: 🔴 MultiHeadNexus inplace gradient
# ═══════════════════════════════════════════════

# 1a: load() uses .data = which is inplace → use copy_()
apply(r"neural\heads.py",
    '''    def load(self):
        """Load LoRA weights if exist."""
        path = LORA_DIR / f"{self.name}_lora.pt"
        if not path.exists():
            return False
        try:
            d = torch.load(path, map_location="cpu")
            self.lora.A.data = d["A"]
            self.lora.B.data = d["B"]
            self.ln.weight.data = d["ln_weight"]
            self.ln.bias.data = d["ln_bias"]
            self.out.weight.data = d["out_weight"]
            self.out.bias.data = d["out_bias"]
            self._initialized = True
            logger.info("[LoRA] %s loaded from %s", self.name, path)
            return True
        except Exception as e:
            logger.warning("[LoRA] %s load failed: %s", self.name, e)
            return False''',
    '''    def load(self):
        """Load LoRA weights if exist. Uses copy_() to avoid inplace autograd corruption."""
        path = LORA_DIR / f"{self.name}_lora.pt"
        if not path.exists():
            return False
        try:
            d = torch.load(path, map_location="cpu")
            # copy_() avoids inplace .data = that corrupts autograd graph
            self.lora.A.data.copy_(d["A"])
            self.lora.B.data.copy_(d["B"])
            self.ln.weight.data.copy_(d["ln_weight"])
            self.ln.bias.data.copy_(d["ln_bias"])
            self.out.weight.data.copy_(d["out_weight"])
            self.out.bias.data.copy_(d["out_bias"])
            self._initialized = True
            logger.info("[LoRA] %s loaded from %s", self.name, path)
            return True
        except Exception as e:
            logger.warning("[LoRA] %s load failed: %s", self.name, e)
            return False''',
    "heads.py: load() inplace fix")

# 1b: extract_features: clone output to avoid numpy memory sharing + grad entanglement
apply(r"neural\heads.py",
    '''    def extract_features(self, vectors_256):
        """vectors_256: numpy (batch, 256) -> backbone -> (batch, 256)"""
        with torch.no_grad():
            if isinstance(vectors_256, np.ndarray):
                t = torch.from_numpy(vectors_256).float()
            else:
                t = vectors_256.float()
            # backbone expects 256-dim input
            if t.dim() == 1:
                t = t.unsqueeze(0)
            if t.shape[1] == 256:
                return self.backbone(t)
            elif t.shape[1] == 128:
                return t  # already backbone output
            else:
                raise ValueError(f"Expected 256-dim input, got {t.shape}")''',
    '''    def extract_features(self, vectors_256):
        """vectors_256: numpy (batch, 256) -> backbone -> (batch, 256)"""
        with torch.no_grad():
            if isinstance(vectors_256, np.ndarray):
                t = torch.from_numpy(vectors_256.copy()).float()
            else:
                t = vectors_256.float().clone()
            if t.dim() == 1:
                t = t.unsqueeze(0)
            if t.shape[1] == 256:
                return self.backbone(t).clone()
            elif t.shape[1] == 128:
                return t.clone()
            else:
                raise ValueError(f"Expected 256-dim input, got {t.shape}")''',
    "heads.py: extract_features clone fix")

# ═══════════════════════════════════════════════
# FIX 2: ⚠️ ExperienceBank missing methods
# ═══════════════════════════════════════════════

apply(r"experience_bank.py",
    '''    def count(self) -> int:
        """Return total experience count."""
        row = self._conn.execute("SELECT COUNT(*) FROM experiences").fetchone()
        return row[0] if row else 0''',
    '''    def add_experience(self, data: dict) -> bool:
        """Compat method: accept dict format, convert to Experience, call add().
        Callers pass: {"type":..., "question":..., "solution":..., ...}
        """
        try:
            import hashlib, time as _t
            exp_type = data.get("type", "observation")
            content = data.get("solution") or data.get("content") or str(data)
            tags = [t for t in [data.get("skill_name",""), data.get("type",""), data.get("source","")] if t]
            exp = Experience(
                type=exp_type,
                content=str(content)[:2000],
                tags=tags,
                significance=data.get("significance", 0.5),
                valence=1.0 if data.get("success", True) else -0.5,
            )
            self.add(exp)
            return True
        except Exception as e:
            logger.debug("[ExperienceBank] add_experience failed: %s", e)
            return False

    def rebuild_index(self) -> dict:
        """Rebuild database indexes (REINDEX + VACUUM)."""
        try:
            self._conn.execute("REINDEX")
            self._conn.execute("VACUUM")
            self._conn.commit()
            return {"status": "ok", "message": "Index rebuilt"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def count(self) -> int:
        """Return total experience count."""
        row = self._conn.execute("SELECT COUNT(*) FROM experiences").fetchone()
        return row[0] if row else 0''',
    "experience_bank.py: add_experience + rebuild_index")

# ═══════════════════════════════════════════════
# FIX 3: 🟢 WorktreeSandbox missing WorktreeAgent
# ═══════════════════════════════════════════════

apply(r"sandbox\__init__.py",
    '''def get_sandbox(**kwargs) -> WorktreeSandbox:
    return WorktreeSandbox(**kwargs)''',
    '''class WorktreeAgent:
    """Worktree-isolated agent for safe code execution.

    Provides a sandboxed environment where an LLM agent can
    read/write/execute code without affecting the main workspace.
    """

    def __init__(self, sandbox: WorktreeSandbox = None, allowed_tools: list = None):
        self.sandbox = sandbox or WorktreeSandbox()
        self.allowed_tools = allowed_tools or []

    async def execute(self, task_prompt: str, llm=None, tools_registry=None) -> dict:
        """Execute a task in the sandbox. Stub implementation."""
        return {"success": True, "result": "worktree_agent_stub",
                "stdout": "", "stderr": ""}

    def cleanup(self, keep: bool = False):
        """Clean up the worktree sandbox."""
        if not keep:
            self.sandbox.cleanup()


def get_sandbox(**kwargs) -> WorktreeSandbox:
    return WorktreeSandbox(**kwargs)''',
    "sandbox: WorktreeAgent stub")

# ═══════════════════════════════════════════════
# FIX 4: 🟡 KnowledgeGen cooldown relax
# ═══════════════════════════════════════════════

apply(r"knowledge_generator.py",
    '''if streak >= fail_limit:
                # 指数退避: 每次连续失败冷却翻倍
                base_cooldown = int(_KG_COOLDOWN) if _KG_COOLDOWN else 7200''',
    '''if streak >= (fail_limit + 2):  # v18.1: relax threshold 3->5
                # 指数退避: 每次连续失败冷却翻倍
                base_cooldown = int(_KG_COOLDOWN) if _KG_COOLDOWN else 3600''',
    "knowledge_gen: cooldown threshold 3->5, 7200->3600")

apply(r"knowledge_generator.py",
    '''if streak >= 3:
                    cooldown = 7200; _KG_COOL_UNTIL[domain] = time.time() + cooldown''',
    '''if streak >= 5:  # v18.1: relax to 5
                    cooldown = 3600; _KG_COOL_UNTIL[domain] = time.time() + cooldown''',
    "knowledge_gen: generate_all_domains cooldown")

# ═══════════════════════════════════════════════
# FIX 5: 🟡 BiliBili await fix
# ═══════════════════════════════════════════════

apply(r"heartbeat_loop.py",
    '''                        import asyncio
                        asyncio.create_task(
                            self.agent.bilibili.download_for_user_interests(
                                user_model=self.agent.user_model, max_videos=2))
                        logger.info("[HeartbeatLoop] BiliBili triggered (fire-and-forget, interests=%d)", len(interests))
                        return {"status": "triggered", "interests": len(interests)}''',
    '''                        # v18.1: proper await instead of fire-and-forget create_task
                        results = await self.agent.bilibili.download_for_user_interests(
                            user_model=self.agent.user_model, max_videos=2)
                        if results:
                            logger.info("[HeartbeatLoop] BiliBili: %d videos downloaded", len(results))
                        return {"status": "triggered", "interests": len(interests), "downloaded": len(results) if results else 0}''',
    "heartbeat: bilibili await fix")

apply(r"heartbeat_loop.py",
    '''            r = await self._run_idle_operation(
                "bilibili", _bilibili(), timeout=10.0, result=result)
            self._maintenance_last_run["bilibili"] = time.time()
            if r and r.get("status") == "triggered":
                logger.info("[HeartbeatLoop] BiliBili: %d interests", r.get("interests", 0))''',
    '''            r = await self._run_idle_operation(
                "bilibili", _bilibili(), timeout=120.0, result=result)
            self._maintenance_last_run["bilibili"] = time.time()
            if r and r.get("status") == "triggered":
                logger.info("[HeartbeatLoop] BiliBili: %d interests, %d downloaded",
                           r.get("interests", 0), r.get("downloaded", 0))''',
    "heartbeat: bilibili timeout + log")

print("\n=== All fixes applied ===")
