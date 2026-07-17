"""Stage 29: B 站种子注入 + self_awareness 自动 reflect_on.

把"学到东西就更新自我"真闭环: 灌种子 → 触发反思 → 表达新状态.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

NEXUS = Path(r"C:\Users\87999\.nexus")
SELF_DIR = Path(__file__).resolve().parent
WORLD_MODEL = NEXUS / "data" / "world_model"  # canonical path used by seed_world_model.py


def _node_count() -> int:
    """读世界模型 nodes.json, 只数非元数据键."""
    p = WORLD_MODEL / "nodes.json"
    if not p.exists():
        return 0
    data = json.loads(p.read_text(encoding="utf-8"))
    return len([k for k in data if not k.startswith("_")])


def run() -> dict:
    # 1) 切到 .nexus 根, 避免 cygwin 路径问题
    os.chdir(str(NEXUS))
    sys.path.insert(0, str(NEXUS))
    sys.path.insert(0, str(SELF_DIR))  # 让 seed_world_model 可被导入

    # 2) 跑种子注入 — 用 subprocess 调用, 因为 seed_world_model.main
    #    写死了 parser.parse_args() 不接受 argv (不修改 seed_world_model.py)
    import subprocess
    env = {**os.environ, "PYTHONPATH": str(SELF_DIR) + os.pathsep + os.environ.get("PYTHONPATH", "")}
    proc = subprocess.run(
        [sys.executable, "-m", "seed_world_model", "--source", "bilibili_seeds"],
        cwd=str(NEXUS), env=env, capture_output=True, text=True, timeout=180,
    )
    print(f"[seed stdout] {proc.stdout.strip()[:400]}")
    if proc.returncode != 0:
        print(f"[seed stderr] {proc.stderr.strip()[:400]}")

    # 3) 读官方写入的 seeding_log.json, 不靠 stdout 解析
    log_path = WORLD_MODEL / "seeding_log.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else {}

    # 4) 触发 self_awareness 自动反思
    from nexus_agent.self_awareness import get_self_awareness  # noqa: E402
    sa = get_self_awareness()
    sa.sync()  # 先拉一次最新状态, 保证 reflect_on 有 baseline
    reflection = sa.reflect_on(
        "bilibili_seed_ingested",
        {"source": "bilibili_seeds", "count": log.get("added", 56)},
    )
    state_str = sa.express_state()

    return {
        "seeded_count": int(log.get("added", 0)),
        "seed_log": log,
        "reflection": reflection,
        "state": state_str,
    }


if __name__ == "__main__":
    out = run()
    print(json.dumps(out, ensure_ascii=False, indent=2))