# Stage 25 — 世界模型真增量注入报告

日期：2026-07-15

## 结论

世界模型磁盘真实节点数从 **157 → 1057**，累计真增量 **+900**，超过阶段目标 500+。
两次运行均通过 `added == mem_delta == disk_delta` 三方对账，`truth_ok=true`。

## 实跑结果

| 排名 | Source / 命令 | 磁盘节点（前 → 后） | 真增量 | 耗时 | 编码器 |
|---|---|---:|---:|---:|---:|
| 1 | `--no-dedup --source=identity --limit=500` | 157 → 657 | **+500** | 4.83s | 500/500 |
| 2 | `--source=curiosity --limit=400` | 657 → 1057 | **+400** | 4.80s | 400/400 |

累计：**157 → 1057（+900，约 6.73 倍）**。

## Seed log 摘要

### Identity

```json
{"source":"identity_weights","before_nodes":157,"added":500,"after_nodes":657,"disk_delta":500,"mem_delta":500,"truth_ok":true,"methods":{"encoder":500,"hash_fallback":0},"elapsed_sec":4.83}
```

完整日志：`stage_25_identity_seed.log`。

### Curiosity

```json
{"source":"curiosity","before_nodes":657,"added":400,"after_nodes":1057,"disk_delta":400,"mem_delta":400,"truth_ok":true,"methods":{"encoder":400,"hash_fallback":0},"elapsed_sec":4.8}
```

完整日志：`stage_25_curiosity_seed.log`；源文件按 JSONL 逐行解析，无 import/JSON 错误。

## 性价比排序

1. **identity**：单次增量最多（+500），约 103.5 节点/秒。
2. **curiosity**：单次增量 +400，约 83.3 节点/秒；问题数据对知识探索更直接。

## Stage 25+ 建议

1. 让 B 站采集/文本提取/seed 注入管线后台连续运行 **2–3 天**。
2. 分批注入并每批执行内存、磁盘、脚本计数三方对账，避免“报告增长、磁盘未增长”。
3. 以 **10000+ 磁盘真实节点**为下一里程碑；当前还需至少 **+8943**。
4. 记录每个 source 的新增量、耗时、fallback 率和失败率，动态优先高 ROI 数据源。
5. 保留 `--no-dedup` 给明确要求“每条记录一个节点”的批次；知识质量批次继续使用输入预去重。

**核心结论**：阶段 25 已完成真增量数据飞轮启动，磁盘节点稳定达到 **1057**。
