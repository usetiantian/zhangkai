# 2026-07-30 — Fix "实验结果: success (0 runs)" 计数 bug

## TL;DR
两处 bug 导致 KG/经验库记录的 runs 永远是 0：
1. `loop.py` 用错 key: `result.get('runs', 0)` → 实际 key 是 `runs_completed`
2. `experiment.py` 的 `runs_completed: run` 有 off-by-one（ALL_COMPLETED 后 run 已++ 但那 run 没真完成）

## 改动
- `D:\wending\_build\experiment.py` — perform_experiments 新增 3 个独立计数器:
  - `runs_completed`: 真实成功数（不含 retry）
  - `runs_attempted`: 总尝试数（含 retry）
  - `runs_failed_final`: 4 次 retry 后仍失败的 run 数
- `D:\wending\_build\loop.py` L58 — 修 key 名 + 输出三项

## 新 log 格式
之前: `实验结果: success (0 runs)`   ← 永远是 0
现在: `实验结果: success (completed=2 attempted=3 failed_final=0)`

## 验证
3 个 E2E case 全过：
- 全成功: completed=2 attempted=2 failed_final=0
- 失败+retry: completed=2 attempted=3 failed_final=0
- 全失败: completed=0 attempted=4 failed_final=1

## 待办
正在跑的 pid 4496 (05:13 启动) 还在用旧代码，需要重启 wending 让新逻辑生效。
