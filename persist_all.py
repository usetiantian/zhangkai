#!/usr/bin/env python3
"""Nexus v18.1 落盘脚本 — 清理、提交、文档更新"""
import os, subprocess, shutil, re

NEXUS = r"C:\Users\87999\.nexus"
AGENT = os.path.join(NEXUS, "nexus_agent")
WORKSPACE = r"C:\Users\87999\claude-workspace"

results = []

def step(name, fn):
    try:
        fn()
        results.append(f"  [OK] {name}")
    except Exception as e:
        results.append(f"  [FAIL] {name}: {e}")

# ═══════════════════════════════════════════════
# 1. Fix .gitignore — only ignore .pt files, not .py source
# ═══════════════════════════════════════════════
def fix_gitignore():
    gi_path = os.path.join(NEXUS, ".gitignore")
    with open(gi_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    changed = False
    new_lines = []
    for line in lines:
        if line.strip() == "nexus_agent/neural/":
            new_lines.append("# neural source is tracked; only ignore model weights\n")
            new_lines.append("nexus_agent/neural/*.pt\n")
            new_lines.append("nexus_agent/neural/lora/*.pt\n")
            changed = True
        else:
            new_lines.append(line)
    if changed:
        shutil.copy(gi_path, gi_path + ".bak")
        with open(gi_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print("    .gitignore: neural/ -> neural/*.pt (source now tracked)")

step("fix .gitignore", fix_gitignore)

# ═══════════════════════════════════════════════
# 2. Remove dead _run_bilibili from heartbeat_loop.py
# ═══════════════════════════════════════════════
def remove_dead_code():
    hb_path = os.path.join(AGENT, "heartbeat_loop.py")
    with open(hb_path, "rb") as f:
        c = f.read()
    
    # Find and remove the standalone async def _run_bilibili
    pattern = b"\n\nasync def _run_bilibili():\n    try:\n        from nexus_agent.autonomous.bilibili_pipeline import get_bilibili_pipeline\n        bp = get_bilibili_pipeline()\n        results = await bp.download_for_user_interests(max_videos=2)\n        if results:\n            logger.info(\"[HeartbeatLoop] BiliBili: %d videos\", len(results))\n    except Exception as e:\n        logger.debug(\"[HeartbeatLoop] BiliBili: %s\", e)\n"
    
    if pattern in c:
        c = c.replace(pattern, b"\n")
        with open(hb_path, "wb") as f:
            f.write(c)
        print("    Removed dead _run_bilibili (unused standalone function)")
    else:
        print("    _run_bilibili already removed or pattern mismatch")

step("remove dead _run_bilibili", remove_dead_code)

# ═══════════════════════════════════════════════
# 3. Delete .bak files
# ═══════════════════════════════════════════════
def clean_backups():
    deleted = 0
    for root, dirs, files in os.walk(AGENT):
        for f in files:
            if ".bak.20260709" in f:
                fp = os.path.join(root, f)
                os.remove(fp)
                deleted += 1
                print(f"    Deleted: {os.path.relpath(fp, AGENT)}")
    if deleted == 0:
        print("    No .bak files to clean")

step("delete .bak files", clean_backups)

# ═══════════════════════════════════════════════
# 4. Stage and commit
# ═══════════════════════════════════════════════
def git_commit():
    os.chdir(NEXUS)
    
    # Stage specific files
    files_to_add = [
        ".gitignore",
        "nexus_agent/experience_bank.py",
        "nexus_agent/heartbeat_loop.py",
        "nexus_agent/knowledge_generator.py",
        "nexus_agent/sandbox/__init__.py",
        "nexus_agent/neural/heads.py",
    ]
    
    for f in files_to_add:
        fp = os.path.join(NEXUS, f)
        if os.path.exists(fp):
            subprocess.run(["git", "add", f], capture_output=True, cwd=NEXUS)
    
    # Show what will be committed
    r = subprocess.run(["git", "diff", "--cached", "--stat"], capture_output=True, text=True, cwd=NEXUS)
    print("    Files staged:")
    for line in r.stdout.strip().split("\n"):
        print(f"      {line}")
    
    msg = (
        "v18.1: 早间维护 — MultiHeadNexus inplace修复 + ExperienceBank补齐 + WorktreeAgent + "
        "KnowledgeGen冷却放宽 + BiliBili await修正\n\n"
        "- MultiHeadNexus: .data= → copy_() 修复inplace梯度失败, extract_features clone隔离\n"
        "- ExperienceBank: 新增 add_experience(dict) 兼容方法 + rebuild_index()\n"
        "- WorktreeSandbox: 新增 WorktreeAgent stub 修复 CVE 导入错误\n"
        "- KnowledgeGen: 冷却阈值 3→5轮, 时长 7200→3600s\n"
        "- BiliBili: create_task → await, timeout 10→120s\n"
        "- .gitignore: neural/ → neural/*.pt (追踪源代码)\n"
        "- 清理 dead _run_bilibili 函数"
    )
    
    r = subprocess.run(["git", "commit", "-m", msg], capture_output=True, text=True, cwd=NEXUS)
    if r.returncode == 0:
        # Show abbreviated commit
        r2 = subprocess.run(["git", "log", "--oneline", "-1"], capture_output=True, text=True, cwd=NEXUS)
        print(f"    Committed: {r2.stdout.strip()}")
    else:
        print(f"    Commit output: {r.stderr[:500]}")

step("git commit", git_commit)

# ═══════════════════════════════════════════════
# 5. Update MEMORY.md
# ═══════════════════════════════════════════════
def update_memory():
    md_path = os.path.join(NEXUS, "MEMORY.md")
    with open(md_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    today_header = "## 2026-07-09 早间维护 (v18.1)"
    
    if today_header in content:
        print("    MEMORY.md already has v18.1 entry")
        return
    
    entry = f"""
{today_header}

### 修复清单

| 级别 | 问题 | 根因 | 修复 |
|:--:|------|------|------|
| 🔴 | MultiHeadNexus 训练失败 | `NexusHead.load()` 用 `.data =` 直接覆写 Parameter，破坏 autograd 计算图 | 改用 `copy_()`，`extract_features` 加 `.clone()` 隔离 |
| ⚠️ | ExperienceBank 缺方法 | 调用方传 dict 但只有 `add(Experience对象)`，缺 `add_experience`/`rebuild_index` | 新增 `add_experience(dict)` 兼容 + `rebuild_index()` |
| 🟢 | CVE 导入 WorktreeAgent 失败 | `sandbox/__init__.py` 不存在 WorktreeAgent 类 | 新增 WorktreeAgent stub |
| 🟡 | KnowledgeGen 4域冷却 | 3轮失败→7200s 过于激进 | 阈值 3→5轮, 时长 7200→3600s |
| 🟡 | BiliBili 协程未 await | `create_task()` fire-and-forget，超时仅10s | 改为 `await`, 超时 10→120s |

### 验证结果
- MultiHeadNexus: 6/6 heads 训练通过, 无梯度报错 ✅
- Minimax API: status_code=0, 连通正常 ✅
- DeepSeek API: 响应正常 ✅
- 20/23 测试通过 (3个误报)
- .gitignore 修复: neural/ → neural/*.pt

### 代码变更
- `neural/heads.py`: `load()` 6行 `.data =` → `copy_()`; `extract_features` 加 `.clone()`
- `experience_bank.py`: +`add_experience()` + `rebuild_index()`
- `sandbox/__init__.py`: +`WorktreeAgent` class
- `knowledge_generator.py`: 冷却阈值放宽
- `heartbeat_loop.py`: bilibili await + 超时修复, 清理 dead `_run_bilibili`
- `.gitignore`: neural/ 源文件纳入追踪
"""
    
    # Insert after the first ## header
    first_marker = "## "
    idx = content.find(first_marker)
    if idx > 0:
        # Find end of that section (next ## or end)
        next_idx = content.find("\n## ", idx + 3)
        if next_idx < 0:
            next_idx = len(content)
        content = content[:next_idx] + entry + content[next_idx:]
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("    MEMORY.md updated with v18.1 entry")

step("update MEMORY.md", update_memory)

# ═══════════════════════════════════════════════
# 6. Update NEXUS_DIARY_2026-07-09.md
# ═══════════════════════════════════════════════
def update_diary():
    diary_path = os.path.join(WORKSPACE, "NEXUS_DIARY_2026-07-09.md")
    if not os.path.exists(diary_path):
        print("    Diary not found at workspace path")
        return
    
    with open(diary_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    if "v18.1 早间维护" in content:
        print("    Diary already has v18.1 entry")
        return
    
    entry = """
---

## 十一、v18.1 早间维护 (CC 协助)

### 修复 (5项, 6文件)

| 级别 | 问题 | 文件 | 修复 |
|:--:|------|------|------|
| 🔴 | MultiHeadNexus inplace梯度 | neural/heads.py | .data= → copy_(), clone隔离 |
| ⚠️ | ExperienceBank 缺方法 | experience_bank.py | +add_experience, +rebuild_index |
| 🟢 | WorktreeAgent 不存在 | sandbox/__init__.py | +WorktreeAgent stub |
| 🟡 | KnowledgeGen 激进冷却 | knowledge_generator.py | 3→5轮, 7200→3600s |
| 🟡 | BiliBili 协程泄漏 | heartbeat_loop.py | create_task→await, 10→120s |

### 验证
- MultiHeadNexus 训练: 6/6 heads ✅
- Minimax API: code=0 ✅
- DeepSeek API: 正常 ✅
- 20/23 测试通过

### 清理
- 移除 dead _run_bilibili 函数
- .gitignore: neural/ → neural/*.pt (源码纳入追踪)
- Git commit: v18.1
"""
    
    # Append before the final --- if it exists, else at end
    last_sep = content.rfind("\n---\n## 待优化")
    if last_sep > 0:
        content = content[:last_sep] + entry + "\n" + content[last_sep:]
    else:
        content += entry
    
    with open(diary_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("    Diary updated with v18.1 entry")

step("update NEXUS_DIARY_2026-07-09.md", update_diary)

# ═══════════════════════════════════════════════
# 7. Verify nexus_daemon.bat
# ═══════════════════════════════════════════════
def verify_daemon():
    bat_path = os.path.join(NEXUS, "nexus_daemon.bat")
    with open(bat_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    # Check for essential deps
    deps_ok = all(d in content for d in ["torch", "numpy", "aiohttp"])
    print(f"    Dependencies check: {'OK' if deps_ok else 'MAY NEED UPDATE'}")
    
    # Update title if needed
    if "Nexus v18" in content and "v18.1" not in content:
        content = content.replace("Nexus v18", "Nexus v18.1")
        content = content.replace(
            "2026-07-09: 46项修复, 72%事件连接率, 完整闭环",
            "2026-07-09: 46项修复 + v18.1早间维护(CC), 72%事件连接率, 完整闭环"
        )
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("    Updated title: v18 -> v18.1")
    else:
        print("    Title already up to date")

step("verify nexus_daemon.bat", verify_daemon)

# ═══════════════════════════════════════════════
print()
print("=" * 50)
print("PERSISTENCE COMPLETE")
print("=" * 50)
for r in results:
    print(r)
