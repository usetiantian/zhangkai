# Stage 17：8 能力 EventBus 真实连接图

## 1. publisher 矩阵

| 能力 / 阶段 | 实际发布事件 | flywheel 实跑 |
|---|---|---|
| Self Play | `self_play.round_done` | 已触发 |
| Gap Analyzer | `agent.gap` | 已触发 |
| Evolution | `evolution.deployed` | 已触发 |
| Learning | `learning.completed` | 已触发 |
| World Model | `world_model.node_added` | 已触发 |
| User Interest | `user.interest.changed` | 已触发 |
| Self Awareness | 无；是消费者 | 未发布 |
| Reflection (`reflect_on`) | 无；由 Self Awareness 调用 | 未发布 |

结论：8 个阶段中 6 个是真 publisher；flywheel 一轮真实触发 6/6，`history_events_seen=6`。

## 2. subscriber 矩阵

| subscriber | 订阅事件 | 收到后动作 | 性质 |
|---|---|---|---|
| `agent_init._on_self_awareness_event` | `agent.gap` | `self_awareness.sync` + `reflect_on` | 生产订阅 |
| `agent_init._on_self_awareness_event` | `evolution.deployed` | `self_awareness.sync` + `reflect_on` | 生产订阅 |
| `agent_init._on_self_awareness_event` | `learning.completed` | `self_awareness.sync` + `reflect_on` | 生产订阅 |
| flywheel history recorder | `self_play.round_done` | 记录到 event history | 验证探针 |
| flywheel history recorder | `agent.gap` | 记录到 event history | 验证探针 |
| flywheel history recorder | `evolution.deployed` | 记录到 event history | 验证探针 |
| flywheel history recorder | `learning.completed` | 记录到 event history | 验证探针 |
| flywheel history recorder | `world_model.node_added` | 记录到 event history | 验证探针 |
| flywheel history recorder | `user.interest.changed` | 记录到 event history | 验证探针 |

生产连接只有 3 条；flywheel 对 6 个事件的订阅只用于证明事件确实到达 EventBus，不算业务消费。

## 3. DEAD LETTER

| 已发布但无生产 subscriber 的事件 | publisher | flywheel 结果 |
|---|---|---|
| `self_play.round_done` | Self Play | 已到达 EventBus，仅被验证探针记录 |
| `world_model.node_added` | World Model | 已到达 EventBus，仅被验证探针记录 |
| `user.interest.changed` | User Interest | 已到达 EventBus，仅被验证探针记录 |

因此生产态 DEAD LETTER 为 **3 种**。若把临时 flywheel recorder 也算 subscriber，则本次测试运行的技术死信为 0；但它们仍没有下游业务动作。

## 4. 未触发订阅

无。`agent_init` 的 3 个生产订阅均有对应 publisher，并且 flywheel 已实触发：

- `agent.gap`
- `evolution.deployed`
- `learning.completed`

结论：当前缺口不是“订阅了但没人发”，而是“6 个 publisher 中只有 3 个接入生产消费者”。
