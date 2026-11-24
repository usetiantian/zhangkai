# 2026-07-30 — 数据驱动分析发现

## 真实数据（5 小时运行）
- 92/97 experiments 成功 (95%)
- 2 个 failed (连续 4 retry 都失败)
- 平均每实验 179s (3 min)
- 16 实验/小时 吞吐量
- 318 run FAILED 中，全部 26s 内 retry 救活
- 65 placeholder 拦截（占 5.8%）

## 推翻之前的"假完成"假设
P1 假设（completed=0 但 status=success）只发生 1 次，不是模式。
真正的问题是 **plan-only 代码**——LLM 写计划不写代码。

## plan-only 代码例子（1553d6bdf979/run_5.py）
```python
# Run 5 - Fine-grained search around the sweet spot identified in Run 4
LEARNING_RATES = [0.003, 0.005, 0.007]
HIDDEN_DIMS = [32, 64, 96]
print(f"Run 5: ...")
```
- 有 3+ 个 body line（不是 placeholder）
- 没 main() 函数
- 没 json.dump 调用
- 跑了 returncode 0，没写 final_info.json → Layer 2 拦截

## 修复（待做）
加 AST 检测：无 main() 函数 + 无 json.dump 调用 → 拒绝 + 让 LLM 重写
具体: `ast.walk(tree)` 检查 `ast.FunctionDef(name='main')` 和 `ast.Call(func=json.dump)`

## 长 gap 来源
- 17 个 >2 min 的 gap
- 大多是 PDF 下载 + vision 解析（每篇 1-3 min）
- 1 个 508s 异常 gap（10:32:52 → 10:40:34），没 log，可能是 API 卡死
