# Stage 22 报告: 修 seed_world_model.py dedup + 真验证落盘

日期: 2026-07-15 · 蓝莓调度 · CC 子代理 · 直读 + 真跑
范围: 仅 `seed_world_model.py`, 未触碰 Nexus 源码

---

## 1. 真实诊断

**根因** = `add_node` 返回 `nid` (string, 例如 `"n00000087"`),
**不是** boolean 也 **不是** count. 旧版脚本 `added += 1`
**无条件执行** —— 当 `dedup=True` (默认) 触发 vector-cosine > 0.95
合并时, `add_node` 返回已有 nid, mem **不增长**, 但 `added` 仍 +1.

世界模型 `Unified256Space.add_node` (world_model.py:35-92) 有两层
dedup: (a) label 精确匹配 → 返回旧 nid, (b) cosine > 0.95 + 同模态
→ 合并并返回旧 nid. 旧版脚本未传 `dedup=False`, 且未对返回值做
truth-check, 故 5056 个 candidate 落盘仅 +56.

阶段 16 已部分修复: 加了 `dedup=False` 参数 + mem 前后对比,
但 `added += 1` 仍无条件 —— **latent bug 仍在**. 阶段 22 收尾.

## 2. 修法 (seed_world_model.py:119-149)

```python
nodes_before_call = space.node_count()
ret = space.add_node(vector, ..., dedup=False)
nodes_after_call = space.node_count()
grew_in_mem = (nodes_after_call - nodes_before_call) >= 1
ret_in_dict = (ret in space._nodes)
if not grew_in_mem or not ret_in_dict:
    deduped += 1
    print(f"[WARN] add_node returned {ret!r} ...")
else:
    added += 1
    methods[method] += 1
...
space.close()  # 强制落盘, 保证 disk_delta 真实
```

并在结果字典里新增 `mem_delta` + `truth_ok` 字段, 三方对账:
`added == mem_delta == disk_delta`. 不一致打 `[FAIL]` 并写入日志.

## 3. 跑前/跑后对比 (--source=identity_weights --limit=20)

| 指标 | 数值 |
|---|---|
| 起点 in-mem | 87 |
| 起点 disk (independent read) | 87 |
| 处理 | 20 |
| 报告 added | **20** |
| mem_delta | **20** |
| 跑后 disk (independent read) | **107** |
| disk_delta | **+20** |
| truth_ok | **true** |
| encoder | 20/20 (hash fallback 0) |
| 耗时 | 0.23s |

三方账目一致. 阶段 22 的修复有效, `dedup=False` + mem 前后比对 +
`space.close()` 三重保证下, 报告数字与磁盘真值完全对齐.

## 4. 风险与遗留

- `_save()` 失败被 `logger.warning` 吞 (world_model.py:417), 脚本层
  仍会报 success. 已通过 `space.close()` 在脚本末尾强制触发, 但若
  进程崩溃在 mid-loop, 仍可能丢最后 < 10 节点. 可接受 (周期性
  `_total_added % 10 == 0` 自动落盘).
- 未触碰 Nexus 代码 (按要求).

状态: 报告完成, 修复已实跑验证.