#!/bin/bash
# nexus_demo.sh — Stage 29 完整 demo, 让 Kai 看到所有 CLI 真在工作.
# 用法: bash nexus_demo.sh  →  把 stdout/stderr 一起捕获.

set +e  # import 报错就让脚本停, 不要吞
cd /c/Users/87999/claude-workspace

echo "=== Demo 1: nexus_status self ==="
python nexus_status.py self
echo ""

echo "=== Demo 2: nexus_status all ==="
python nexus_status.py all
echo ""

echo "=== Demo 3: nexus_status diagnose ==="
python nexus_status.py diagnose
echo ""

echo "=== Demo 4: nexus_status stats ==="
python nexus_status.py stats
echo ""

echo "=== Demo 5: flywheel (8-stage closed loop) ==="
cd /c/Users/87999/.nexus
python -c "from nexus_agent.flywheel import run_flywheel; import json; print(json.dumps(run_flywheel('stage29_demo'), ensure_ascii=False, indent=2))"
echo ""

echo "=== Demo 6: seed_world_model --report-only --source=bilibili_seeds ==="
# Windows-bash 下 /c/... 会被再套一层 C:\\c\\... → 用 Windows 原生绝对路径.
SEED_PY="C:/Users/87999/claude-workspace/seed_world_model.py"
python "$SEED_PY" --report-only --source=bilibili_seeds
echo ""

echo "=== END OF DEMO ==="