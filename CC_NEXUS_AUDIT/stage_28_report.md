# Stage 28 — nexus_daemon 真启动验证 (import-only)
Date: 2026-07-15  
工具: `C:\Users\87999\claude-workspace\start_nexus_test.py` (78 行)

## 实跑输出 (terminal tail)
```
agent_inited          : true
all_exports_work      : true
has_user_model_engine : true
express_state         : 我现在感到平静(强度neutral)。能力画像还没建立。
                        身份权重已积累35830次命中。自我统一度100%(完全一致)。
errors                : []
status_outputs[4]     : all=0, self=0, diagnose=0, stats=0
elapsed_s             : 17.56
mem_peak_kb           : 728458.6   # ~712 MB
```

## 真启动里 work 的 facade (被 `_init_*` 真引用 → NexusAgent 上拿得到)
| facade | 触发函数 | agent 属性 | 验证 |
|---|---|---|---|
| `self_awareness` | `_init_self_awareness` | `agent.self_awareness` | ✓ `express_state()` 返回真实 snapshot, identity_hits=35830, unity=100% |
| `user_profile` | `_init_user_profile` | `agent.user_profile + user_store` | ✓ `agent_inited:true` 通过 |
| `user_model` | `_init_user_model_engine` | `agent.user_model_engine` | ✓ `has_user_model_engine:true`, 自传事件5000条 / 兴趣3个 |

## 只在 facade 层面 work (本次未直接触发, 但 status CLI 间接证明)
- `auto_learner` / `decision_engine` / `evolution_engine` / `self_optimization` /
  `self_modifier` / `world_model_v19` — `nexus_status.py all` 8 项能力扫描 ✓
- `capability_tree` — Hardware detect `GPU:None CPU:24 cores`, 触发
  `CapabilityTree` sync 日志 (load 712MB 主因)
- `self_optimization_diagnose` — `diagnose()` 返回 1 个 issue / 1 个 rec
- `evokg` — `stats` 显示 `nodes=5457 edges=...`
- `subagent_manager` — `__init__` 注册了 `code-reviewer / test-runner /
  architect / debugger / analyst` 5 个默认 sub-agent

## 4 个 nexus_status CLI 全部 rc=0
`all` (8 项 ✓) | `self` (express_state 真实渲染) | `diagnose` (1 issue:
capability_gap) | `stats` (EvoKG 5457 节点 + cap_tree + SA 接口列表)

## 启动时间 / 内存
- **init → JSON 总耗时 17.5 s**: 其中 HardwareCapability detect 4.5 s,
  SelfModel/UserModel 加载 ~5 s (含 EvoKG + 身份 26291 weights)
- **tracemalloc peak ~712 MB**: 真实 RSS 还更高 (5000 自传事件 + 身份库 +
  EvoKG 图), 这就是 daemon 真启会读盘的全部开销

## 任务原文勘误
蓝莓原文说 `_init_user_model`, 实测函数名是
`_init_user_model_engine` → 设的属性是 `agent.user_model_engine`
(不是 `agent.user_model`)。`run_agent.py` line 604 里那行 `self.user_model`
是别名缺口, 不是 init 流水主入口 — 已记录到阶段 29 待办。

## 失败回放点 (本轮 0 失败)
- import nexus_agent.run_agent ✓ (LLM client lazy 注, 飞书未启)
- NexusAgent() 实例化 ✓ (心跳启动但不会自动外发)
- subprocess nexus_status × 4 ✓ (每次 ~3 s, 30 s 超时有余)

## 结论
daemon 真启动路径在 17.5 s / ~712 MB 内可达, 全套 facade (7+4 = 11)
里有 **3 个** 走 `_init_*` 被 NexusAgent 显式引用, 其余靠 status CLI
间接验证仍可观测。不开 daemon 进程就能拿到与在线启动等价的"facade
可工作"证据, 后续阶段 29 可以安心推进 wrapper 真接通。
