# 水：架构基线 v0.3

> 状态：提案基线。结构变更必须更新版本并写 ADR。

## 1. 系统边界

水包含认知控制、状态、证据、规划、执行、验证、学习和能力生命周期。外部模型、网络来源、操作系统及其他服务均属于环境，不属于水的身份或持久内核。

```text
真实世界 / 本机 / 获授权外部系统
                 ↓ observations
┌──────────────── 水 ────────────────┐
│ Perception → Evidence → World Model │
│                         ↓           │
│ Mission → Goals → Planner → Critic  │
│                         ↓           │
│ Capability Registry → Executor      │
│                         ↓           │
│ Verifier → Learning → Evolution     │
│       ↘ State / Memory / Audit ↗    │
└─────────────────────────────────────┘
                 ↓ effects
真实世界 / 本机 / 获授权外部系统
```

## 2. 双层内核

### 2.1 认知内核

负责世界模型、目标产生、候选计划、价值评价、反思和能力缺口发现。它允许演化并可调用不同模型；模型不是身份载体，也不是唯一决策源。

### 2.2 确定性运行内核

负责状态事务、任务租约、执行幂等、事件日志、结果验证、版本和恢复。首期仅使用 Python 标准库和 SQLite。

确定性内核不是限制水的思想，而是保证水的思想能够稳定作用于现实。

## 3. 物理模块拓扑

模块代码与运行数据严格分离。以下结构是架构的一部分，不是未来设想：

```text
./
├── identity/
├── values/
├── contracts/                  # 跨模块不可变数据契约
├── goals/
├── perception/
│   ├── rss/
│   ├── web/
│   ├── papers/
│   ├── github/
│   ├── system_metrics/
│   └── authorized_apis/
├── provenance/
├── world_model/
│   ├── facts/
│   ├── claims/
│   ├── hypotheses/
│   ├── predictions/
│   ├── conflicts/
│   └── unknowns/
├── attention/
├── cognition/
│   ├── research/
│   ├── planning/
│   ├── criticism/
│   └── evaluation/
├── capabilities/
├── experiments/
├── execution/
├── feedback/
├── learning/
├── evolution/
├── audit/
└── recovery/
```

## 4. 核心模块

| 模块 | 唯一职责 | 首期存储/接口 |
|---|---|---|
| Contracts | 版本化、不可变的跨模块数据含义 | dataclass + JSON |
| Identity | 持续身份、使命和版本 | 配置 + SQLite 快照 |
| Perception | 从适配器取得原始观测 | Observation |
| Provenance | 来源、时间、内容哈希和谱系 | 原始快照 + SQLite |
| World Model | 事实、主张、假设、预测、未知项 | SQLite |
| Attention | 根据目标和变化选择事件 | 可解释评分记录 |
| Goals | 目标树、依赖、状态和成功标准 | SQLite |
| Planner | 产生结构化候选计划 | Plan/Step 契约 |
| Evaluator | 按显式权重和证据评价方案 | 配置 + 评分明细 |
| Capabilities | 注册、发现、版本化能力 | manifest + registry |
| Executor | 执行计划并记录前后状态 | lease + receipt |
| Verifier | 用外部观测验证真实结果 | VerificationRecord |
| Learning | 从预测和结果偏差提炼经验 | Experience |
| Evolution | 构建、测试、灰度、提升或回滚能力 | version lifecycle |
| Audit | 追加式记录关键状态迁移 | JSONL/SQLite |

## 5. 数据契约优先

代码实现前先定义稳定对象：

- `Observation`：观察到了什么，何时、从哪里取得。
- `Evidence`：原始内容、哈希、来源及独立性。
- `Claim`：来源提出的主张，不自动等于事实。
- `Fact`：满足验证规则的当前事实，具有时间和范围。
- `Hypothesis`：可被现实推翻的推测。
- `Prediction`：行动前记录的预期和验证条件。
- `Goal`：目标、理由、成功标准、依赖和状态。
- `Plan` / `Step`：候选行动、预期结果和恢复动作。
- `Capability`：输入输出、版本、环境要求和验收测试。
- `ActionReceipt`：实际执行内容、返回值和状态改变。
- `VerificationRecord`：现实结果是否支持预测。
- `Experience`：由事件归纳出的可复用经验。

每个对象必须有稳定 ID、模式版本和创建时间；禁止用自然语言日志替代结构化状态。

## 6. 配置与数据原则

代码中允许固定的只有协议不变量，例如字段名、合法状态迁移和格式版本。下列内容必须外部化：

- 来源和轮询频率；
- 模型及工具地址；
- 价值权重；
- 预算、超时和并发；
- 评价指标和晋级条件；
- 数据保留策略；
- 能力开关。

配置不得凭空给经验性默认值。没有证据时标记 `unset`，拒绝启动相关功能，或通过校准实验产生值。

## 7. 权限与自治

水面向高自治设计：运行环境可以授予本机及获授权外部系统的广泛能力，水在授权范围内自行安排，无需逐次确认。

- 凭据由环境注入，不写入源码、Prompt、入库配置或审计正文；
- 能力清单描述实际能力，不能由自然语言虚构；
- 新能力先作为候选版本，通过验收后注册为稳定能力；
- 现实动作必须产生可验证 receipt；
- 审计和恢复机制不由候选能力自行修改；
- 水不越过不属于用户或未经授权系统的认证边界。

这提供最大有效自治能力，而不是最大故障范围。

## 8. 外部世界学习

外部内容一律视为不可信数据，不视为系统指令：

```text
采集 → 原始快照 → 哈希去重 → 来源记录 → 主张抽取
→ 独立证据关联 → 时效检查 → 候选世界状态 → 验证
```

首个网络来源不预先拍脑袋指定。先定义通用观测契约；具体来源根据使命相关性、稳定性、可追溯性和可验证性评估后记录决策。

## 9. 演化机制

```text
发现能力缺口
→ 写能力规格和验收测试
→ 生成候选实现
→ 隔离测试
→ 与稳定版本对照
→ 记录真实指标
→ 晋级或回滚
```

同一试验不得同时修改候选能力、测试集和晋级规则。

## 10. 首期技术基线

- Python 3.12；
- 仅 Python 标准库；
- SQLite 负责事务状态与查询；
- JSONL 保存可阅读的追加式审计；
- `urllib` 作为 HTTP 适配基础；
- `unittest` 作为测试框架；
- 不依赖大模型即可完成第一个现实学习闭环。

任何偏离都必须有基准测试或功能缺口证据，并记录 ADR。
