# 2026-07-30 (verified) — runs_completed fix 生效

## ⚠️ 第一次重启时改错文件了

`_build/loop.py` (6222 bytes) 不是 wending 实际加载的代码。
引擎从 `from wending.scheduler.loop import Loop` (15478 bytes) 加载。
**真正的修复文件**：`D:\wending\wending\scheduler\loop.py` L104-116

## 教训
不要假设 `_build/` 是 dev 入口。先 grep `import` 找实际加载路径。
对比 `_build/experiment.py`（唯一，被加载）vs `_build/loop.py`（死代码，从未 import）。

## 重启后实测（3 实验样本）
- 11:16:57 Physics-Ordered: completed=5 attempted=11 failed_final=0 (6 retry 救活)
- 11:17:30 Qubit-Flow: completed=0 attempted=0 (LLM 直接 ALL_COMPLETED 偷懒)
- 11:21:19 Energy-Efficient: completed=5 attempted=9 failed_final=0 (4 retry 救活)

累计: completed=10 attempted=20 retry 救活率=50%

## 新观察: LLM 偷懒 ALL_COMPLETED
当 completed=0 但 status=success 时，说明 LLM 第一次 API 调用就返回 ALL_COMPLETED
没写任何代码。这种"假完成"应该被检测 + 给 LLM 至少跑一次真实实验再允许结束。
