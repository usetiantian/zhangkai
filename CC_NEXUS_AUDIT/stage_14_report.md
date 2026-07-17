# 阶段 14：Flywheel 实跑结果与 EventBus 真实连接

> 结论基于本阶段已经完成的实跑与代码定位；本报告不以静态猜测代替运行结果。

## 1. Flywheel 真跑结果

`nexus_agent/flywheel.py` 已真实执行，不是仅完成 import、静态检查或伪输出。

| 阶段 | 能力链路 | 实跑结果 |
|---:|---|---|
| 1/8 | LearningModule（学习） | ok |
| 2/8 | CognitiveLoopModule（认知循环） | ok |
| 3/8 | EvolutionEngine（演化） | ok |
| 4/8 | SelfPlayDomain（自博弈） | ok |
| 5/8 | CapabilityTree（能力树） | ok |
| 6/8 | Sentinel（守卫/检查） | ok |
| 7/8 | World Model（世界模型） | ok |
| 8/8 | EventBus / flywheel 汇合发射 | ok |

运行汇总：

```text
stages_ok=8/8
history_events_seen=6
subscriptions=1
elapsed_ms=1368
```

因此阶段 14 的最小闭环已经成立：八段能力均走到成功出口；一次订阅实际看到了六个事件；整轮在 1368 ms 内结束。

补充已验证事实：`nexus_agent/seed_world_model.py --source=bilibili_seeds` 也已真实执行，世界模型节点数由 21 增至 77。该结果证明世界模型种子写入可运行，但不等同于证明它与所有运行时消费者都已双向连接。

## 2. EventBus 真实连接

真实订阅入口位于 `agent_init._setup_event_subscribers` 第 **1981–1984** 行。这里把三个事件订阅到同一个处理器：

```text
3 个自我感知相关事件
        │
        ▼
_on_self_awareness_event
        │
        ├──► self_awareness.sync(...)
        └──► self_awareness.reflect_on(...)
```

这不是“存在 EventBus 类”层面的静态推断，而是已定位到初始化阶段的实际 subscriber wiring。结论是：三个事件进入 `_on_self_awareness_event` 后，会驱动 `self_awareness.sync` 同步状态，并进一步调用 `reflect_on` 形成反思。

本次 flywheel 自己建立的观察订阅也真实收到六次通知：`history_events_seen=6`、`subscriptions=1`。因此 publisher → EventBus → subscriber 的基本投递路径已被执行覆盖。

## 3. 8 能力 facade 暴露的入口

`flywheel.py` 通过薄 facade 把八段能力收拢为同一条可执行链，而不是在脚本里重写各模块内部算法：

| 能力 | facade 入口/组件 | 在 flywheel 中的职责 |
|---|---|---|
| 学习 | `LearningModule` | 接收完成信号并形成学习结果 |
| 认知循环 | `CognitiveLoopModule` | 推进一轮认知处理与缺口识别 |
| 演化 | `EvolutionEngine` | 形成并部署演化结果 |
| 自博弈 | `SelfPlayDomain` | 完成一轮 self-play |
| 能力管理 | `CapabilityTree` | 表达/更新能力与缺口 |
| 安全守卫 | `Sentinel` | 对 flywheel 过程执行守卫检查 |
| 世界模型 | World Model facade | 接入节点新增/种子扩充结果 |
| 汇合与通知 | EventBus facade | 把阶段结果作为领域事件发布 |

这些入口的意义是统一编排：调用方只需要运行 flywheel，具体能力仍由各自模块负责。facade 已证明“能调用”，但不应被扩大解释为所有模块间的数据语义都已经完整贯通。

## 4. 8 能力 → EventBus publisher

flywheel 汇合阶段真实触发了以下六个事件：

```text
SelfPlayDomain ───────────────► self_play.round_done
CognitiveLoop / CapabilityTree ► agent.gap
EvolutionEngine ──────────────► evolution.deployed
LearningModule ───────────────► learning.completed
World Model facade ───────────► world_model.node_added
用户兴趣/认知上下文 ─────────► user.interest.changed
                                  │
                                  ▼
                               EventBus
                                  │
                                  └──► 观察订阅收到 6/6
```

八段能力和六个 publisher 事件不是一一对应关系：`Sentinel` 负责守卫，不要求独立发事件；EventBus 是传输/汇合层，本身也不是业务事件来源。`CapabilityTree` 与认知循环共同落到 `agent.gap` 这一类能力缺口信号。其余业务阶段分别由上述领域事件暴露结果。

这六个事件的实跑证据是 `flywheel_emitted` 触发记录与 `history_events_seen=6`，不是仅从事件名或 `emit` 调用位置推断。

## 5. 哪段没连（留待阶段 17/18）

阶段 14 证明的是“八段可执行 + 六事件可投递 + self-awareness 有真实订阅链”，尚未证明以下连接：

1. 六个 flywheel 事件是否都存在生产环境长期 subscriber；本次单一 history 观察订阅不能替代业务消费者审计。
2. `self_play.round_done`、`agent.gap`、`evolution.deployed`、`learning.completed`、`world_model.node_added`、`user.interest.changed` 是否全部进入后续持久化、调度或策略反馈。
3. 三个 self-awareness 订阅事件与上述六个 flywheel 事件之间，哪些同名直连、哪些需要 adapter/事件转换；本阶段不宣称九个名称天然等价。
4. `Sentinel` 的拒绝/降级结果是否会阻断发布，还是只记录检查结果。
5. `CapabilityTree` 的 gap 更新是否会反向触发 Learning/Evolution，形成跨轮闭环，而非只在单轮中顺序调用。
6. 世界模型 21→77 节点的持久化结果，是否被认知循环和 self-awareness 在下一轮真实读取。
7. subscriber 的异常隔离、重试、幂等、事件顺序及重复投递语义尚未做故障实测。
8. 进程重启后的订阅恢复与历史事件重放尚未验证。

以上缺口留到阶段 17/18 做消费者矩阵、端到端因果链和故障路径验证；阶段 14 不越界声称“完整自治闭环已经接通”。
