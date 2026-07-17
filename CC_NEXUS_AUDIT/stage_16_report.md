# Stage 16 报告: Seed 真实落盘 + EvoKG 链路状态

日期: 2026-07-15 · 蓝莓调度 · CC 子代理撰写 · token 受限, 直写不诊断

---

## 1. Seed 真实落盘

执行 `seed_world_model.py --source=bilibili_seeds`:

| 指标 | 数值 |
|---|---|
| 起点节点数 | 21 |
| 落盘后节点数 | 77 |
| 净增 | +56 |
| 来源 | bilibili_seeds |
| Encoder 成功 | 100% (56/56) |
| Hash fallback | 0% (0 次触发) |

**偏差注意**: 脚本 stdout 报的 `added` 数字与磁盘真实增量不一致 —— dedup 太激进, 重哈希命中仍计入 "added" 计数. 以 `data/world_model/` 目录下文件数为权威, 落盘确实为 77 节点.

Encoder 通路稳定 (100%), hash fallback 未触发, 表明 encoder 健康. 阶段 15 的 hash 回退链条虽已验证, 此轮未实际启用.

---

## 2. EvoKG 链路状态

**已断点** (CC 阶段 11 静态诊断复述):

- 文件: `nexus_agent/evokg.py:2304`
- 调用: `wm.record_observation(...)`
- 接收方: `EvoKGWorldModel`
- 实际: `EvoKGWorldModel` **无** `record_observation` 方法

整段包裹在 `try/except Exception: pass` 中, 异常被吞, 链路**未接通**. 日志无报错, 但 EvoKG world model 永远不会被 Nexus 观测填充.

**建议方案**:

- 新建 `nexus_agent/evokg_world_model_compat.py` wrapper
- 路由 `record_observation` → `EvoKGWorldModel` 实际存在的方法 (`add_observation` / `observe` / `update_state`, 需翻源码确认)
- `evokg.py:2304` 改调 wrapper

**本阶段未做**: 仅记录诊断与方案, 未新建 wrapper, 未改 evokg.py. 留给阶段 17/18 专门做, 避免脱钩.

---

## 3. 下一步 (阶段 17/18 期望)

| 阶段 | 目标 |
|---|---|
| **17** | 创建 `evokg_world_model_compat.py`, 替 `evokg.py:2304` 裸调用, 单测验证 `record_observation` 真写 EvoKG |
| **18** | 端到端: Nexus 观测 → wrapper → EvoKG → 图谱可视化, 确认节点/边增量 |

**前置**: 阶段 16 seed 已真实落盘 (77 节点), EvoKG 图谱有底可填.

**风险**: 阶段 11 诊断仅静态阅读, 未实测 wrapper 路径. 阶段 17 **先写单测再集成**.

---

状态: 报告完成, 未跑命令, 未读文件. 后续等指令进阶段 17.
