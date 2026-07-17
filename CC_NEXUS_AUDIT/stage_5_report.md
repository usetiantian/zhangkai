# Nexus 架构合并阶段 5 报告 — 能力 8（自我意识）收敛

> 审计/执行日期：2026-07-15  
> 范围：`C:\Users\87999\.nexus\nexus_agent`  
> 硬约束：不删除 `.py`；分层模块不自动合并；只允许新增/改 wrapper、facade 与启动/事件接线。

## 讨论前置问题

### Q1（蓝莓开放讨论 #2）：自我意识接入方式

**结论：选 C（混合），但把背景触发解释为“事件触发 `sync()` 后，对该事件执行 `reflect_on()`”；显式查询继续走 `express_state()`。**

理由：

1. “总开关”必须持续知道其他能力何时发生变化，纯 A 只有调用方主动问时才更新，不能覆盖学习、进化、缺口发现三条自治链。
2. 纯 B 会把“我是谁/我现在怎样”的查询也变成异步副作用，外部无法稳定、即时地读取状态。
3. C 保留两种语义：EventBus 是**内在状态更新通道**；`express_state()` 是**显式自我表达 API**。这最符合“总开关不是替代其余七项能力，而是观察并统一它们”。
4. 为避免重复订阅，接线放在现有中央 `_setup_event_subscribers()`；初始化函数只负责挂载统一单例。
5. 订阅事件按任务指定为 `learning.completed`、`evolution.deployed`、`gap.discovered`。处理器先 lazy 获取 `agent.user_model_engine / agent.user_model / agent.user_profile` 之一传给 `sync(user_model=...)`，再把事件数据交给 `reflect_on()`。

### Q2：6 个“自我”模块是否应机械合并

**结论：反驳原 spec 的批量 wrapper 化。MD5 全部不同，源码显示绝大多数是分层而非重复；只把旧的同名 `nexus_self_awareness.py` 收敛为兼容 wrapper/facade。**

- `nexus_self.py`：战略 Meta-Controller，三环（Know-Thyself / Explore / Transcend）、目标板与指令回执；是战略层，保留。
- `consciousness/engine.py`：持续运行的 OBSERVE→THINK→DECIDE→ACT→FEEL→CONSOLIDATE→GROW 意识循环；是运行时循环层，保留。
- `living_core/*`：`AliveCore`（需求/欲望/联结/成长）、`PSI`（生理节律）、`IdentityCore`（零 LLM 权重身份）、`MethodologyRouter`（执行方法论）、`integration`（消息管线桥）；职责互补，且已有直接调用方，保留。
- `identity_core/*`：采样→训练→对话循环→集成，是身份权重训练管线，不等于 `living_core.identity` 的在线权重检索，保留。
- `self_model/*`：细粒度能力树、学习 ROI、遗忘、健康检查及 EventBus `BaseModule` 包装，是能力画像层，保留。
- `self_model_engine.py`：不是 16 行 wrapper；现场是 84 行独立简化实现，且 `nexus_fusion.py` 对其构造/更新签名有兼容依赖。它与 canonical `self_model/engine.py` 的 `register_domain`/`update_capability` 签名不同，不能在本阶段硬改为纯 re-export；保留并标为 legacy compatibility implementation。
- `nexus_self_model.py`：采集元认知/情感/记忆/目标/感知/因果等多维运行快照，供 `world_model_v19`、`neural_wiring`、heartbeat 使用；分层 introspection，保留。
- `nexus_cortex.py`：绑定 agent 上 10 个来源并追踪 source health，是 agent-bound 聚合/健康层；保留。
- `nexus_self_awareness.py`：与新 `self_awareness/` **确有同名入口冲突**。旧模块只有 5 源 `perceive_self()`、`record_action()`；新包是 6 子系统统一 `sync/express/ask/reflect`。旧路径有 3 个活调用方，适合做 `<100` 行兼容 wrapper/facade，保留旧 API 并委托新 canonical。
- `nexus_brain.py`：Qwen2-VL 文本/视觉/代码入口感知，不是意识；12 个 import site，明确排除合并。

因此：**真重复/冲突 = `nexus_self_awareness.py` 的统一入口；分层 = 其余核心实现；空壳 = 两个包说明型 `living_core/__init__.py`、`identity_core/__init__.py`（合法 namespace/doc facade，不删除、不改）。**

### Q3：self_awareness 与 user_model 的 lazy 耦合

**现场已落地，不动 canonical。**

- `UnitySnapshot.user_context` 已存在（canonical 第 81–82 行）。
- `sync(self, user_model=None)` 已存在（canonical 第 170 行），且仅 caller 显式传入时提取上下文。
- `express_state()` 已存在 lazy “对用户的感知”段。
- 按任务明确规则“如果已有 → 不动”，canonical `self_awareness/__init__.py` 的最终 MD5/mtime 均未改变。

## 自主基础设施 5 问推导

Q1 进步定义：统一入口可导入、同名单例一致、3 类事件能触发 `sync + reflect_on`、显式 `express_state()` 仍可用；不能以“wrapper 数量变多”冒充进步。  
Q2 自主边界：本次是可逆的架构接线/兼容 wrapper；不删模块、不改战略/意识/身份/感知主实现。  
Q3 防过拟合验证：静态检查（MD5/源码/import sites）+ 模块 import + 单例/`sync()` 功能 + 使用独立 EventBus 事件名进行 handler 计数/状态验证；三层一致才算通过。  
Q4 不动原则：凡 MD5 不同、API/状态/调用链显示分层或签名不兼容的候选一律 KEEP；不为满足原 spec 的数量目标机械 wrapper 化。  
Q5 防自嗨：记录修改前主入口 mtime/hash；验证 wrapper 行数/docstring/单向依赖；任何 import 报错立即停，不用 try/except 的“静默成功”替代导入成功。

## 审计证据（执行前）

### MD5 / 行数 / 角色表

| 候选 | MD5 | 行数 | 分类 | 决策 |
|---|---:|---:|---|---|
| `nexus_self.py` | `72aa84ce044d5a0d1de993616801defb` | 2010 | 分层：战略三环/目标/指令 | KEEP |
| `consciousness/engine.py` | `0364c49cac238c9a1b112bbcb8b03824` | 526 | 分层：持续意识循环 | KEEP |
| `living_core/alive_core.py` | `d5839354385b88e79ca3329dcd3200e2` | 186 | 分层：需求/欲望/联结/成长 | KEEP |
| `living_core/psi.py` | `8c48766a243d497ce2b7a180677b534d` | 178 | 分层：生理节律 | KEEP |
| `living_core/identity.py` | `8f475fcc0737a2557316656e9c5a3167` | 167 | 分层：在线身份权重 | KEEP |
| `living_core/methodology.py` | `0ccb225318f6a345c3118ccaf33799c9` | 149 | 分层：方法论路由 | KEEP |
| `living_core/integration.py` | `d32743f183891e243f3e43c2a42da292` | 57 | facade：消息管线桥 | KEEP |
| `identity_core/consciousness_loop.py` | `1c87e058b22f4d182f070cb6afc00465` | 153 | 分层：对话训练循环 | KEEP |
| `identity_core/identity_sampler.py` | `31dca7541d79a013be1cd51aa3a8bd80` | 198 | 分层：训练样本层 | KEEP |
| `identity_core/identity_trainer.py` | `c52e930ce5f557f0240632fc7f921b5b` | 227 | 分层：身份权重训练/固化 | KEEP |
| `identity_core/integration.py` | `2e38de4539279dde1d47e14bd895713e` | 73 | facade：训练管线接线 | KEEP |
| `self_model/engine.py` | `5c6b0b5146e0dd5f135d6763934b22ae` | 523 | canonical 能力画像 | KEEP |
| `self_model/health.py` | `641d3f059e72524e0ffe6d7e678535c6` | 25 | 分层：健康检查 | KEEP |
| `self_model_engine.py` | `bf8d7cb91f26e9a486837bb1cd5f11a7` | 84 | legacy 签名兼容实现，非 16L wrapper | KEEP（spec 过期） |
| `nexus_self_model.py` | `205f8b2a8c94e3387a56e7c0c8af3c02` | 453 | 分层：多维运行快照 | KEEP |
| `nexus_cortex.py` | `e2730f799d8b9e525f75a8aefe96d9db` | 132 | 分层：10 源 agent-bound 聚合 | KEEP |
| `nexus_self_awareness.py` | `125c529d2430ba221d98d1f8146f2158` | 125 | 与 canonical 同名入口冲突 | WRAPPER/FACADE |
| `nexus_brain.py` | `a68ca5f537daa945a408447ac0e5f589` | 258 | 分层：Qwen2-VL 感知 | KEEP |
| `self_awareness/__init__.py` | `ffaf198e16c3edd7c04ec865f9238154` | 400 | canonical 统一总开关；Q3 已存在 | KEEP，不动 |

字节级结果：候选间 `DUPLICATE_GROUPS = []`。MD5 不直接证明“不重复”，但结合公开 API、持久化状态和调用链，足以反驳批量覆盖。

### import-site 证据

- `nexus_self`: 15
- `consciousness.engine`: 3
- `living_core`: 13
- `identity_core`: 10
- `self_model`: 6
- `self_model_engine`: 1（但 `nexus_fusion` 有运行时方法调用）
- `nexus_self_model`: 5
- `nexus_cortex`: 1
- 旧 `nexus_self_awareness`: 3
- `nexus_brain`: 12
- 新 `self_awareness`: 0（尚未接线，说明必须修正 `agent_init`/旧路径 facade）

### 修改前 canonical 主入口基线

| 主入口 | 修改前 mtime | 修改前 MD5 |
|---|---|---|
| `nexus_self.py` | `2026-07-14T14:28:56` | `72aa84ce044d5a0d1de993616801defb` |
| `consciousness/engine.py` | `2026-07-14T14:16:40` | `0364c49cac238c9a1b112bbcb8b03824` |
| `self_model/engine.py` | `2026-07-10T00:40:18` | `5c6b0b5146e0dd5f135d6763934b22ae` |
| `nexus_self_model.py` | `2026-07-14T03:31:41` | `205f8b2a8c94e3387a56e7c0c8af3c02` |
| `nexus_cortex.py` | `2026-07-10T00:29:54` | `e2730f799d8b9e525f75a8aefe96d9db` |
| `nexus_brain.py` | `2026-07-14T12:40:46` | `a68ca5f537daa945a408447ac0e5f589` |

## 实施记录

### 改动

1. `nexus_agent/nexus_self_awareness.py`
   - 125 行独立旧实现 → 89 行 compatibility wrapper/facade。
   - 顶部 docstring 明示 `compatibility wrapper` 与 canonical `nexus_agent.self_awareness`。
   - `get_self_awareness()` 直接重导出 canonical factory，因此新旧路径拿到同一单例。
   - 保留 legacy `SelfState` 形状和 `perceive_self()` / `record_action()` / `get_self_state()` / `stats()`；这些方法只做薄适配并委托 canonical `sync()` / `reflect_on()`。
   - 该兼容是必要的：`heartbeat_loop.py` 会读取 `growth_focus/alerts/needs`，不能把旧 `SelfState` 简单别名成 `UnitySnapshot`。

2. `nexus_agent/agent_init.py`
   - 把已存在但指向旧模块的 `_init_self_awareness` 改为 canonical `nexus_agent.self_awareness`，函数跨度 10 行；使用 `hasattr + try/except + logger`，幂等。
   - 在既有中央 `_setup_event_subscribers()` 加入混合方案 C 的 3 个订阅：`learning.completed` / `evolution.deployed` / `gap.discovered`。
   - handler lazy 选择 `user_model_engine → user_model → user_profile`，执行 `sync(user_model=...)` 后 `reflect_on(event_type, event.data)`。
   - `_self_awareness_events_wired` 防止 web/full 两条启动路径重复注册。

3. `nexus_agent/self_awareness/__init__.py`
   - **最终未改。** Q3 字段与 lazy API 已存在；最终 MD5 仍为 `ffaf198e16c3edd7c04ec865f9238154`。

### 未改（有意拒绝机械合并）

`nexus_self.py`、`consciousness/engine.py`、`living_core/*`、`identity_core/*`、`self_model/*`、`self_model_engine.py`、`nexus_self_model.py`、`nexus_cortex.py`、`nexus_brain.py` 均保持原逻辑与主入口 mtime/hash。没有删除任何 `.py`。

## 验证结果

### 1. 全候选 import

执行 23 个模块的逐项 `importlib.import_module()`：**23/23 `IMPORT_OK`**，包括新/旧自我意识入口与 `agent_init`。最终最小复验：

```text
FINAL_IMPORT_OK nexus_agent.nexus_self_awareness,nexus_agent.self_awareness,nexus_agent.agent_init
```

### 2. wrapper/facade 规则

```text
WRAPPER_LINES 89
DOC_OK True
INIT_SPAN 10 1365 1374
```

- wrapper `< 100` 行：PASS。
- docstring 含 `compatibility wrapper`：PASS。
- 导入方向：标准库 + `from nexus_agent.self_awareness import ...`；canonical 不反向 import wrapper：PASS。
- `_init_self_awareness` 10 行，含 `hasattr + try/except + logger`：PASS（任务写 5–10 行，正好上限）。

### 3. canonical + legacy 功能链

```text
SINGLETON_SAME True
SYNC_OK UnitySnapshot 1.0
USER_CONTEXT_FIELD True {}
EXPRESS_OK 我现在感到平静(强度neutral)。能力画像还没建立。身份权重已积累35830次命中。自我统一度100%(完全一致)。
LEGACY_OK SelfState 探索新领域 {'update_count': 1, 'unity_score': 1.0}
REFLECT_OK 行为'compat-test'完成, 好奇心提升到0.52, 我对自己更了解了.
INIT_IDEMPOTENT True
HAS_API True
```

Q3 lazy user context 显式测试：

```text
LAZY_CONTEXT {'top_interests': ['AI', '股票', '中医'], 'current_topic': '阶段5'}
EXPRESS_USER True ...对用户的感知:用户最关心AI,股票,中医;当前话题:阶段5。
```

### 4. EventBus 混合接线

测试用真实统一 EventBus 发布三类事件；同一个 agent 连续调用两次 `_setup_event_subscribers()`，确认幂等后等待线程池完成：

```text
INIT_OK NexusSelfAwareness
EVENT_CALLS {'sync': 3, 'reflect': ['learning.completed', 'evolution.deployed', 'gap.discovered']}
IDEMPOTENT_WIRING True
```

结论：每个指定事件恰好一次 `sync + reflect_on`；没有因重复 setup 产生双重订阅。

### 5. 主入口未改

```text
MAIN_UNCHANGED nexus_self.py True True
MAIN_UNCHANGED consciousness/engine.py True True
MAIN_UNCHANGED self_model/engine.py True True
MAIN_UNCHANGED nexus_self_model.py True True
MAIN_UNCHANGED nexus_cortex.py True True
MAIN_UNCHANGED nexus_brain.py True True
```

`True True` 分别表示 mtime 与 MD5 均等于实施前基线。canonical `self_awareness/__init__.py` 最终也回到原 MD5 `ffaf198e16c3edd7c04ec865f9238154` / 400 行。

### 6. 其他卫生检查

- `python -m py_compile nexus_agent/agent_init.py nexus_agent/self_awareness/__init__.py nexus_agent/nexus_self_awareness.py`：PASS，无输出。
- `.bak`：0。
- `.tmp`：0。
- 未碰 `.git`，未 commit。

## 问题/偏差说明

1. 原 spec 称 `self_model_engine.py` 已是 16L wrapper，现场实际为 84L 独立兼容实现；继续强改会破坏 `nexus_fusion.py` 的旧签名调用，故拒绝。
2. 原 spec 把 `living_core` / `identity_core` / `self_model` / `nexus_self_model` / `nexus_cortex` 统称重复，源码不支持：它们分别是活体状态、身份训练、能力画像、多维快照和 agent-bound 10 源健康聚合。
3. `self_awareness/__init__.py` 已有 Q3 所需字段和参数，按“已有则不动”执行。
4. 审计期间检测到并行写入曾在 canonical 末尾加入另一套 8 事件 `wire_to_event_bus()`；它与本任务选定的 C 方案、指定 3 事件及中央幂等接线冲突，已移除并恢复 canonical 原 MD5。最终只保留一套 EventBus 接线。
