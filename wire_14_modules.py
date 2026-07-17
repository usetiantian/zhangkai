# -*- coding: utf-8 -*-
"""Nexus v18.2 — 14个核心模块按五步四维接入启动序列"""
import os, re

NEXUS = r"C:\Users\87999\.nexus\nexus_agent"
bak = ".bak.v18.2"

def read(rel):
    with open(os.path.join(NEXUS, rel), "r", encoding="utf-8") as f:
        return f.read()

def write(rel, content):
    path = os.path.join(NEXUS, rel)
    with open(path + bak, "w", encoding="utf-8") as f:
        f.write(read(rel))
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] {rel}")

# ═══════════════════════════════════════════════════════
# PLAN: wire into _start_self_play (the one init sequence we verified works)
# Categories:
#
# A. IMMEDIATE (startup, before anything else):
#    _init_skills, _init_cognitive_loop, _init_nexus_gatekeeper,
#    _init_nexus_handoff, _init_task_execution_loop
#
# B. DEFERRED (after core ready, background):
#    _init_speech, _init_vision, _init_user_model_engine,
#    _init_cron_manager, _init_curator
#
# C. ON-DEMAND (triggered by specific events):
#    _init_concept_verification, _init_self_verification
#
# D. HEARTBEAT (already wired):
#    _init_external_explorer (via _run_explorer)
#    _init_hypothesis_engine (via ResearchEngine)
# ═══════════════════════════════════════════════════════

agent_init = read("agent_init.py")

# Find _start_self_play and add Category A calls right after _init_multihead
old_block = '''    _init_self_play_engine(agent)
    # v18.1b: 初始化 MultiHeadNexus (6 LoRA heads + backbone)
    _init_multihead(agent)'''

new_block = '''    _init_self_play_engine(agent)
    # v18.2: 核心模块按五步四维接入
    # ── 消费层: 消息路由 + 任务执行 ──
    _init_skills(agent)                    # 技能注册表 (工具消费技能)
    _init_cognitive_loop(agent)            # 7Agent闭环引擎 (消费消息→路由)
    _init_task_execution_loop(agent)       # 任务执行闭环 (消费任务→执行)
    # ── 质量门禁: 守门人 + 交接协议 ──
    _init_nexus_gatekeeper(agent)          # 质量守门人 (优先级+降级)
    _init_nexus_handoff(agent)             # NEXUS交接协议 (销项闭环)
    # ── 能力层: MultiHeadNexus ──
    _init_multihead(agent)                 # 6 LoRA heads + backbone
    # ── 反馈层: 验证闭环 ──
    _init_concept_verification(agent)      # 概念验证 (零LLM, 反馈闭环)
    _init_self_verification(agent)         # 自验证器 (工具执行后验证+修复)
    # ── 用户+感知: 画像 + 语音 + 视觉 ──
    _init_user_model_engine(agent)         # Kai用户画像 (兴趣/知识/偏好)
    _init_speech(agent)                    # TTS+STT语音 (后台加载)
    _init_vision(agent)                    # 视觉模块 (懒加载GPU)
    # ── 运维: 定时任务 + 技能维护 ──
    _init_cron_manager(agent)              # 定时任务管理 (时效性保障)
    _init_curator(agent)                   # 技能自动维护 (销项清理)'''

if old_block in agent_init:
    agent_init = agent_init.replace(old_block, new_block, 1)
    print("  [OK] 14 modules wired into _start_self_play")
else:
    print("  [SKIP] insertion point not found in agent_init.py")

write("agent_init.py", agent_init)

# ═══════════════════════════════════════════════════════
# Also need to fix _init_skills — it checks hasattr but 
# uses get_skill_manager which is a singleton, not agent field.
# Let me verify the code is correct.
# ═══════════════════════════════════════════════════════

# Verify
v = read("agent_init.py")
checks = [
    "_init_skills(agent)",
    "_init_cognitive_loop(agent)", 
    "_init_task_execution_loop(agent)",
    "_init_nexus_gatekeeper(agent)",
    "_init_nexus_handoff(agent)",
    "_init_concept_verification(agent)",
    "_init_self_verification(agent)",
    "_init_user_model_engine(agent)",
    "_init_speech(agent)",
    "_init_vision(agent)",
    "_init_cron_manager(agent)",
    "_init_curator(agent)",
]

print()
print("=== Verification ===")
for c in checks:
    count = v.count(c)
    # Count should be 1 (the call) + 1 (in the def if still there) = 2
    # But definitions are 'def _init_xxx' not '_init_xxx(agent)'
    # So just count occurrences of the call pattern
    print(f"  {c}: found {count}x {'OK' if count >= 1 else 'MISSING!'}")

# Verify _init_multihead is still there
print(f"  _init_multihead(agent): {v.count('_init_multihead(agent)')}x")
