# Nexus 完成度矩阵 (2026-07-15)

> 扫描对象：`C:\Users\87999\.nexus`
> 审计者：Claude Code (delego subagent)
> 当前状态：Nexus 进程 PID=11848 存活 (nexus.pid mtime 2026-07-15 00:27, 当前时间 ~00:41)
> 入口：`nexus_gateway/run.py`（见 `nexus_daemon.bat`）
> 日志：`logs/nexus_startup.log` 共 27368 行，最近事件 2026-07-15 00:41:32
> 总 Python 文件：**644** 个（剔除 `__pycache__/backup/.nexus_backup/research_repos`）
> 启动以来累计 evolution_cycles=**2791**（来自 ClosedLoopEngine 状态恢复日志）

## 状态图例

| 标记 | 含义 |
|---|---|
| ✅ 活 | 有日志/数据持续写入，代码被 active 调用 |
| 🟡 部分活 | 入口存在，但日志稀疏或功能部分缺失 |
| ❌ 空壳 | 文件存在但无运行证据、永远报错、或被绕过 |

## 完成度矩阵

| # | 子系统 | 主要模块(.py) | 状态 | 关键证据 |
|---|---|---|---|---|
| 1 | **kernel (legacy)** | `kernel/__init__.py` 452L / `kernel/event_bus.py` 770L / `kernel/config.py` 654L | 🟡 部分活 | mtime 2026-07-07 01:13（8天前最后修改）。`kernel/event_bus.py` 顶部注释叫 "BlueberryOS Unified EventBus"（已迁去 nexus_agent/event_bus.py）。`nexus_agent/event_bus.py` 日志自述"统一 4 套分散的事件总线"已包含 kernel/event_bus。**kernel 文件 mtime 全部锁在 7月7日**：被复用但不再演化，事实空壳。 |
| 2 | **body/gateway** | `body/gateway/unified_gateway.py` 499L / `feishu_adapter.py` 4786L / `platform_base.py` 3367L | ✅ 活 | 启动日志 11:42:51 "Web UI 端口就绪: 19666"；Feishu 适配器初始化成功。但 `body/` 整体 mtime 2026-07-07 — **active 入口已迁去 `nexus_gateway/`（同源代码更新到 7月14日）**。body/是历史包袱但被 dead code 化。 |
| 3 | **body/llm** | `body/llm/client.py` 273L | ❌ 空壳 | mtime 2026-07-07 01:11。`nexus_agent/nexus_llm.py` (762L) 启动日志明确 "NexusLLM 2个提供商就绪" — 是真正生效的 LLM 客户端。body/llm/client.py 没在任何 active 代码中 import。 |
| 4 | **nexus_gateway** | `nexus_gateway/run.py` (启动入口) / `platforms/feishu_channel` / `web_server.py` | ✅ 活 | 实际启动入口（nexus_daemon.bat 调用）。日志 11:42:51-11:42:55 完成 Feishu + WebUI + 双通道绑定；PID 11848 持续运行。 |
| 5 | **consciousness** | `nexus_agent/consciousness/__init__.py` 77L / `engine.py` 526L | 🟡 部分活 | mtime 2026-07-12 ~ 7月14。日志里 `nexus_agent.consciousness` logger 名出现，但实际闭环由 `meta_cognition/__init__.py` (NexusMetaCognition) 驱动 — `closed_loop_engine.py` import 的是 meta_cognition。consciousness/engine.py 顶部 "8步闭环"描述完整但运行证据稀疏。 |
| 6 | **living_core** | `nexus_agent/living_core/{alive_core,psi,identity,methodology,integration}.py` 共 759L | ❌ 空壳 | mtime 2026-07-12 22:02~7月13 01:46。**无任何日志 logger 出现 living_core**。模块未接入主循环。文档 `ALIVE_DESIGN.md` 未验证被读。 |
| 7 | **identity_core** | `nexus_agent/identity_core/{consciousness_loop,identity_sampler,identity_trainer,integration}.py` 共 651L | 🟡 部分活 | mtime 2026-07-12 22:02~22:05。日志 11:43:00 `[NexusContextCompressor] Initialized`、`Identity Loaded 26291 weights`（这是从 `nexus.identity`，不是 identity_core）。**identity_core 子包 4 个文件在主循环中无 logger 输出** — 设计存在但未 wire。 |
| 8 | **identity (legacy)** | `nexus_agent/identity.py` 180L | ✅ 活 | 日志 00:40:49 `[Identity] Loaded 26291 weights` + `[Identity] No device identity found — running unauthenticated`。mtime 2026-06-16（4 周未更新）。承担运行时身份。 |
| 9 | **self_model (package)** | `nexus_agent/self_model/__init__.py` 142L / `engine.py` 523L / `health.py` 25L | 🟡 部分活 | mtime 2026-06-16（4 周未更新）。heartbeat_loop.py 第 56 行 import `SelfModelEngine().find_gaps({})` — 在 _get_dynamic_keywords 中用，但 try/except 兜底，静默失败时仍能跑。 |
| 10 | **self_model_engine (legacy)** | `nexus_agent/self_model_engine.py` 84L | ❌ 空壳 | mtime 2026-07-10 00:29。极小，可能是 wrapper。`grep` 在 active 代码中未发现引用。 |
| 11 | **nexus_self_model** | `nexus_agent/nexus_self_model.py` 453L | ✅ 活 | mtime 2026-07-14 03:31（昨日更新）。closed_loop_engine 间接引用。日产 self_model.json 持续刷新。 |
| 12 | **user_model (package)** | `nexus_agent/user_model/__init__.py` 96L / `engine.py` 374L / `health.py` 49L | 🟡 部分活 | mtime 2026-06-16（4 周未更新）。data/user_model.json 含 `interests: 股票/中医/自媒体`，message_count=13 — 极少量。 |
| 13 | **user_model_engine** | `nexus_agent/user_model_engine.py` 319L | 🟡 部分活 | mtime 2026-07-10 00:40。可能在 active 代码中被 import，但无独立 logger 输出。 |
| 14 | **nexus_user_profile** | `nexus_agent/nexus_user_profile.py` 133L | ✅ 活 | mtime 2026-07-13 16:43（昨日）。启动日志 11:42:55 `用户上下文（信任+user_profile）已加载`。 |
| 15 | **user_identity** | `nexus_agent/user_identity/__init__.py` 110L | 🟡 部分活 | mtime 2026-06-16（4 周未更新）。与 user_model 重叠。 |
| 16 | **knowledge_graph (package)** | `nexus_agent/knowledge_graph/__init__.py` 56L / `engine.py` 241L / `health.py` 13L | 🟡 部分活 | mtime 2026-06-16（4 周未更新）。`data/knowledge_graph.json` 只有 **2 个节点 / 1 条边**（节点 ID = conversation_9ad1e75c268f + test_dd557ea4c8c6）— **严重欠载**。 |
| 17 | **evokg** | `nexus_agent/evokg.py` 2740L | ✅ 活 | mtime 2026-07-14 (隐含)。启动日志 11:42:55 `能力评分已恢复（10项, top=2.83）`。meta_cognition 通过 evokg 恢复 1417 项目。承担实际知识图谱持久化。 |
| 18 | **self_play** | `nexus_agent/self_play/{challenger,cross_modal_challenger,kg_challenger,solver,verifier}.py` 共 ~1100L + `self_play_engine.py` | ✅ 活 | 日志 00:36:13 持续 `self_play_engine.py:课程选择 pattern_completion (tier=1 pass_rate=72% weight=1.64)`。运行活跃但 **FAIL 率极高**：score=0.43<0.5 → 升级 Tier2 → 仍 FAIL → 注入跨域知识 → 3600s 冷却。 |
| 19 | **self_reflection (package)** | `nexus_agent/self_reflection/{correl_tracer,cost_estimator,decision_logger,historical_analyzer,llm_interface,meta_controller,reasoner,shared_state,state_analyzer,trigger}.py` 共 1350L | 🟡 部分活 | mtime 全部 6月16日（4 周未更新）。`__init__.py` 仅 2 行（基本空）。`data/self_reflection_progress.json` + `self_reflection_5rounds.json` 存在 — 有数据但模块本体未演化。 |
| 20 | **metacognition (package)** | `nexus_agent/metacognition/{__init__.py 108L, engine.py 506L}` | 🟡 部分活 | mtime 6月16日+7月12日。和下条 meta_cognition 重叠。 |
| 21 | **meta_cognition (active)** | `nexus_agent/meta_cognition/__init__.py` 3156L | ✅ 活 | mtime 2026-07-14 06:20（含**142 KB** 单文件，是整个 nexus 最大模块）。**真正的元认知**。日志 11:42:55 `元认知系统初始化` / 00:36:04 `已知领域: 1179, 缺口: 0, 能力树: 3322 技能`。被 closed_loop_engine 直接实例化。 |
| 22 | **meta_governor** | `nexus_agent/meta_governor.py` 531L | 🟡 部分活 | mtime 2026-06-16（4 周未更新）。可能只是被早期版本使用。 |
| 23 | **evolution** | `nexus_agent/evolution.py` 1063L / `evolution_engine.py` 3738L / `evolution_decision_engine.py` 1333L | ✅ 活 | 日志 00:37:56 `[EvolutionDecisionEngine] #2040 — dispatching MEDIUM/improve target='execution_quality'`。3 个文件并存但 `evolution_decision_engine` 是 active dispatcher。evolution_engine.py 183 KB 是大块头，主线用不到的部分大概率冗余。 |
| 24 | **evolution_roadmap / evolution_validator** | `nexus_agent/evolution_roadmap.py` / `evolution_validator.py` | 🟡 部分活 | 不在主线 active 调用，但被 evolution_decision 间接使用。需进一步 grep 验证。 |
| 25 | **event_bus (kernel)** | `kernel/event_bus.py` 770L | ❌ 空壳 | mtime 2026-07-07。`nexus_agent/event_bus.py` 自述 "统一 4 套分散的事件总线" 已包含 kernel/event_bus。**被绕过**。 |
| 26 | **event_bus (nexus_agent, ACTIVE)** | `nexus_agent/event_bus.py` 701L | ✅ 活 | 日志 11:42:51 `[EventBus] Unified event bus initialized`。承担全部 pub/sub，142 次 event_bus 引用在日志中。 |
| 27 | **event_emitter (compat)** | `nexus_agent/event_emitter.py` 161L | ✅ 活（兼容层） | 日志 11:43:00 `[NexusEventEmitter] Initialized (delegates to EventBus)`。薄封装。 |
| 28 | **closed_loop_engine** | `nexus_agent/closed_loop_engine.py` 2219L | ✅ 活 | 日志 11:42:55 `ClosedLoopEngine 初始化 (HeartbeatLoop + 7Agent + MetaCognition + BrainAdapter + EventBus + NNTrainLoop)`、`10/10 critical events wired`。是 7Agent 闭环主入口。 |
| 29 | **cognitive_loop** | `nexus_agent/cognitive_loop/__init__.py` 3173L / `workflow.py` / `agents/` | ✅ 活 | mtime 2026-07-14 06:20（**107 KB** 单文件，事实主模块）。closed_loop_engine 第 48-58 行 import 7 个 Agent（Priority/Reasoner/GapAnalyzer/Decision/Implement/Guardian/Recorder）。 |
| 30 | **autonomous_planner** | `nexus_agent/autonomous_planner.py` 966L | ✅ 活 | 日志 00:36:04 `[AutonomousPlanner] Proactive check (idle=137s)`。持续运行。 |
| 31 | **autonomous (subpackage)** | `nexus_agent/autonomous/{bilibili_pipeline, dialogue_learner, video_learner, acfun_pipeline, seed_extractor, integration}.py` | 🟡 部分活 | mtime 2026-06-16 + 7月9日。**和 autonomous_planner.py 重叠**：planner 是总入口，autonomous/ 是早期散落实现。heartbeat_loop 中 `_get_dynamic_keywords` 仍用 `bilibili_pipeline` 的常量。 |
| 32 | **cron** | `nexus_cron/{scheduler.py, jobs.py, jobs.json}` | 🟡 部分活 | mtime 6月16日。`nexus_agent/cron_manager.py` 557L 是 active 实现（启动日志 `CronManager`）。`nexus_cron` 顶层目录未被 agent 引用。 |
| 33 | **cron_manager** | `nexus_agent/cron_manager.py` 557L | ✅ 活 | 日志 11:42:51 `[NexusCronManager] croniter not installed. Cron expressions will use simple interval fallback`（功能降级但仍跑）。 |
| 34 | **heartbeat_loop** | `nexus_agent/heartbeat_loop.py` 1999L | ✅ 活 | 日志 00:38:40 `HeartbeatLoop Tick #10 / Launch: scenario_gen, knowledge_gen` — 每分钟 1 tick。 |
| 35 | **neural/world_model** | `nexus_agent/neural/world_model.py` 425L | ✅ 活 | mtime 2026-07-14 23:46（昨日）。日志 00:39:16 `[FusedArchBridge] cycle #100 domain=knowledge_graph steps=['train', 'fe'] wm_nodes=26`。**注意：wm_nodes 当前=25-26（增量极慢）。`data/world_model/nodes.json` 只 21 个真实节点**（n00000000..n00000020），`edges.json` 23 真实边 — 但 **14/23 边全部指向 c000000 单 cluster（疑似 cluster 算法退化）**。 |
| 36 | **neural/evokg_world_model** | `nexus_agent/neural/evokg_world_model.py` 166L | 🟡 部分活 | mtime 2026-07-10 00:29。和上面的 neural/world_model + evokg.py 重叠。 |
| 37 | **neural/blind_spot_predictor** | `nexus_agent/neural/blind_spot_predictor.py` 78L | 🟡 部分活 | mtime 2026-07-07 15:08。无 logger 输出。 |
| 38 | **neural/free_energy_principle** | `nexus_agent/neural/free_energy_principle.py` 95L | 🟡 部分活 | mtime 2026-07-07 12:40。`intention_engine` 引用"Fusion:Friston"EFE门控 — 此模块是其源头之一。 |
| 39 | **neural/intrinsic_curiosity** | `nexus_agent/neural/intrinsic_curiosity.py` 340L | 🟡 部分活 | mtime 2026-07-07 01:48。无独立 logger，靠 curactor 间接调用。 |
| 40 | **neural/nexus_reasoner** | `nexus_agent/neural/nexus_reasoner.py` 333L | 🟡 部分活 | mtime 2026-07-10 00:29。和 reasoner.py 重叠。 |
| 41 | **neural/fused_arch_bridge** | `nexus_agent/neural/fused_arch_bridge.py` 250L | ✅ 活 | mtime 2026-07-13 13:53。日志 00:39:16 `[FusedArchBridge] cycle #100 wm_nodes=26`。 |
| 42 | **neural/heads / learning_heads** | `nexus_agent/neural/heads.py` 261L / `learning_heads.py` 150L | 🟡 部分活 | mtime 7月7日+9日。LoRA 多头架构。"6头 LoRA 共享 backbone" 设计来自 NEXUS_DIARY_2026-07-08。 |
| 43 | **neural/lora_auto_tuner** | `nexus_agent/neural/lora_auto_tuner.py` 360L | 🟡 部分活 | mtime 2026-07-10 00:29。和 `nexus_agent/lora_manager.py` 重叠。 |
| 44 | **neural/{router_nn, signal_bus_nn, knowledge_gate_nn, gap_analyzer_nn, complexity_scorer_nn}** | 共 5 文件 / 共 281L | ❌ 空壳 | mtime 2026-07-13 18:09（同一波修改）。**总行数 281L — 每个 47-87L 的占位实现**，全部用 `nexus_agent.neural.{name}` logger 名但**无任何日志输出**。疑似占位骨架，未接到主循环。 |
| 45 | **neural/training_loop** | `nexus_agent/neural/training_loop.py` 119L | 🟡 部分活 | mtime 2026-07-14 05:16。heartbeat_loop 周期性 Launch: training_executor，但此文件未见 logger 输出。 |
| 46 | **neural/fallback / distill** | `nexus_agent/neural/fallback.py` 60L / `neural/distill/` | 🟡 部分活 | mtime 6-9月。distill/ 是子目录，未细查。 |
| 47 | **encoders** | `nexus_agent/neural/encoders.py` 550L | ✅ 活 | mtime 2026-07-14 06:26。`feature_encoder.py` 337L 是外部接口。`nexus_agent/encoders.py` 文件**不存在**（冲突命名）。 |
| 48 | **experience_bank** | `nexus_agent/experience_bank.py` 465L | ✅ 活 | mtime 2026-07-13 12:36。日志 11:42:55 `[ExperienceBank] Initialized, DB=C:\Users\87999\.nexus\data\experience_bank.db`。DB 有 shm/wal → 在写入。 |
| 49 | **chroma_client** | `nexus_agent/chroma_client.py` 61L | ✅ 活 | mtime 2026-07-07 03:46。提供 `get_chroma_client()` 单例。`data/chroma_db/` 3 个 collection + sqlite。 |
| 50 | **llm_client (legacy)** | `nexus_agent/llm_client.py` 84L | ❌ 空壳 | mtime 2026-07-10 00:17。**3KB**。无日志输出。被 `nexus_llm.py` 取代。 |
| 51 | **nexus_llm (ACTIVE)** | `nexus_agent/nexus_llm.py` 762L | ✅ 活 | mtime 2026-07-14 11:27。日志 11:42:51 `[NexusLLM] 2个提供商就绪` (minimax + deepseek)。错误日志也来自此：HTTP 529 overloaded、read timeout。 |
| 52 | **sandbox** | `nexus_agent/sandbox/__init__.py` 132L | 🟡 部分活 | mtime 2026-07-09 11:21。`WorktreeSandbox` git worktree 实现。EvolutionEngine 调用但未验证。 |
| 53 | **run_agent (NexusAgent 主类)** | `nexus_agent/run_agent.py` 934L | ✅ 活 | mtime 2026-07-14 14:56。日志中调用栈多次命中 (line 641/693/810)。是 NexusAgent 主类。 |
| 54 | **nexus_web_server** | `nexus_agent/nexus_web_server.py` 286L | ✅ 活 | mtime 2026-07-14 01:21。`/maturity /api/maturity /api/rust /visual /health` 端点。 |
| 55 | **daemon** | `nexus_daemon.bat` + `nexus_gateway/run.py` | ✅ 活 | mtime 2026-07-13 20:17。bat 文件启动 nexus_gateway/run.py。PID 文件 nexus.pid (11848) 活跃。 |

## 数据完整性核查（任务 D 第 3 条）

> 用户给的"world_model 32M 数据 + 527 节点"陈述**不成立**。

| 度量 | 实际值 | 来源 |
|---|---|---|
| `data/world_model/nodes.json` 节点数 | **20 个真实节点 + 2 系统字段**（n00000000..n00000020） | 直接读 JSON |
| `data/world_model/edges.json` 边数 | **23 条边**（_next_eid=23） | 直接读 JSON |
| 其中指向 cluster `c000000` 的边 | **14 / 23 = 61%** | Counter 统计 |
| `data/world_model/clusters.json` cluster 数 | **1 个**（c000000） | 直接读 JSON |
| `data/world_model/wordvecs.json` 大小 | **33.8 MB** | ls -la |
| `data/knowledge_graph.json` 节点数 | **2**（conversation_xxx, test_xxx） | 直接读 JSON |
| `data/knowledge_graph.json` 边数 | **1** | 直接读 JSON |
| `data/self_model.json` 能力条目数 | **4**（code_generation/hardware/code_modification/network） | 直接读 JSON |
| `data/user_model.json` 用户消息数 | **13** 条 | 直接读 JSON |
| 运行日志显示 world_model 节点数 | `wm_nodes=25 → 26`（每 50 cycle 增长 1） | grep 日志 |

**结论**：
1. world_model 实际只有 ~20 个手工/早期种子节点（猫/狗/Python/动物等基础词），**不是 527**。
2. cluster 算法严重退化（1 个 cluster 吃 14 条边 → 后续 grow 都聚合进 c000000）。
3. knowledge_graph.json 仅 2 节点 ≈ 完全没用。
4. 词向量文件 33.8 MB 可能是预训练模型加载，与"527 节点"无对应。

## 启动健康度（任务 D 第 1 条）

**Nexus 今天确实成功启动过**（PID=11848，2026-07-15 00:27 启动），仍在运行。但有真实问题：

| 类别 | 计数 | 例子 |
|---|---|---|
| `ERROR` | 81 | minimax HTTP 529 (overloaded) × 多次；Feishu adapter `name 'time' is not defined` Traceback × 1；Feishu `reply send failed` × 4 次 |
| `WARNING` (主要) | 多 | `croniter not installed`（降级到 interval fallback）；`Sentinel MODERATE 循环模式`（多次）；`LEARNING_FAILED: topic=你扫描完成再汇报 reason=all_strategies_failed` × 8（CONFIG FAILURE 阻塞 3600s） |
| `Traceback` | ≥ 1 | `name 'time' is not defined` 在 `feishu_channel` reply 处理中（模块顶缺 `import time`） |
| `all_strategies_failed` | 8 次 | 全部来自 `topic=你扫描完成再汇报` (Kai 给的指令)，全部是 **CONFIG FAILURE**（需要 Firecrawl API key 等未配置）。被 cooldown 3600s 阻塞。 |

## 死代码/早期代码（任务 D 第 2 条预判）

**mtime < 2026-06-01 且不在 active 调用链上的文件数**：**196 个 .py 文件**。其中：
- `nexus_cli/*.py` 全部（约 70 个文件） — mtime 6月16日，是早期未接入新架构的命令行外壳
- `nexus_cron/*.py` — `nexus_agent/cron_manager.py` 才是 active 实现
- `skills/*.py`（18 个） — 大部分是 hermes-style superpowers 模板，未 wire
- `tests/*.py` — 不在 active agent 启动路径
- `body/*.py`（除 entry） — 已迁去 `nexus_agent/` 和 `nexus_gateway/`

详细审计见姊妹文档 `NEXUS_DUPLICATES.md`。