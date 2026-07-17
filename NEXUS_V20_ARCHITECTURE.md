# Nexus v20 完整架构设计

> 基于 2026-07-13 全量扫描 354 模块，按功能域重组。
> 每层定义：职责、模块清单、输入、输出、当前状态。

---

## 总览：七域三层

```
                    ┌──────────────────────────┐
                    │      用户交互域            │
                    │  feishu / web / cli / tui │
                    └────────────┬─────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
  ┌─────▼──────┐          ┌──────▼──────┐          ┌──────▼──────┐
  │  认知推理域  │          │  知识工厂域  │          │  工具执行域  │
  │  (大脑)     │◄────────►│  (消化系统)  │          │  (手脚)     │
  └─────┬──────┘          └──────┬──────┘          └──────┬──────┘
        │                        │                        │
        └────────────────────────┼────────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
  ┌─────▼──────┐          ┌──────▼──────┐          ┌──────▼──────┐
  │  自我进化域  │          │  自我意识域  │          │  用户理解域  │
  │  (肌肉骨骼)  │◄────────►│  (内省)     │          │  (共情)     │
  └─────┬──────┘          └──────┬──────┘          └──────┬──────┘
        │                        │                        │
        └────────────────────────┼────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │      基础设施域           │
                    │  event_bus / evokg / ... │
                    └─────────────────────────┘
```

---

## 域 1：认知推理域 — "大脑"

**职责**：接收用户输入，理解意图，推理决策，生成回复。

### 1.1 网关子域 (对外接口)

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `nexus_gateway/run` | — | 主启动入口，初始化所有子系统 | ✅ |
| `nexus_gateway/web_server` | — | Web UI (19666 端口) | ✅ |
| `nexus_gateway/platforms/feishu_channel` | — | 飞书 WS 长连接 | ✅ |
| `nexus_web_server` | — | 独立 Web 服务 | ⚠️ |
| `nexus_cli/tui` | — | 命令行 TUI 界面 | ⚠️ |

**数据流**：飞书消息 → `feishu_channel` → `_compat` → `agent_response`

### 1.2 消息处理子域

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `_compat` | 249 | 兼容层，桥接旧模块导入 | ✅ |
| `agent_response` | 3446 | 消息路由+响应生成 | ✅ |
| `agent_commands` | 1601 | 命令处理器 | ✅ |
| `message_entities` | — | 消息实体定义 | ✅ |
| `message_renderer` | — | 消息渲染（飞书 post 格式） | ✅ |
| `nexus_handoff` | — | 消息交接 | ⚠️ |

**数据流**：`_compat` → `agent_response` → `cognitive_loop` → LLM → 回复

### 1.3 认知闭环子域

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `cognitive_loop/__init__` | 3151 | 7Agent 闭环引擎 | ✅ |
| `cognitive_loop/agents` | 2620 | 7 个协作 Agent | ✅ |
| `cognitive_loop/workflow` | 214 | 工作流阶段追踪 | ✅ |
| `cognitive_capability` | 159 | 认知槽位注册 | ✅ |
| `closed_loop_engine` | 2202 | 统一闭环引擎（心跳+7Agent+MetaCog） | ✅ |
| `closed_loop_brain_adapter` | 506 | 闭环↔子系统适配器 | ✅ |
| `orchestrator/engine` | 227 | 编排器（追踪/把关/反馈） | ⚠️ 空转 |
| `router/engine` | 158 | 消息路由第一站 | ✅ |
| `gateway_runner` | — | 网关运行器 | ✅ |
| `intent_matcher` | — | 意图匹配 | ✅ |

**数据流**：`agent_response` → `cognitive_loop` → `closed_loop_engine` → LLM / 工具

### 1.4 LLM 推理子域

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `nexus_llm` | 733 | LLM 中枢（DeepSeek+MiniMax） | ✅ 今天修 |
| `nexus_brain` | 170 | 本地 Qwen2-VL-2B 推理 | ⚠️ dtype 错 |
| `llm_client` | — | LLM 客户端 | ✅ |
| `llm_parser/__init__` | — | 响应解析+修复 | ✅ |
| `llm_health_cron` | 237 | LLM 健康检查 cron | ✅ |
| `reasoner` | 334 | 螺旋推理引擎 | ✅ |
| `reasoning` | — | 推理框架 | ✅ |
| `nexus_reasoner` | — | 统一预测层 | ✅ |
| `predictive_router` | — | 预测路由 | ✅ |
| `nexus_fusion` | — | 融合引擎 | ✅ |

**数据流**：`nexus_llm.achat()` ← `cognitive_loop` / `knowledge_generator` / `self_play`

### 认知域总计：~40 模块

---

## 域 2：知识工厂域 — "消化系统"

**职责**：获取外部知识 → 转化 → 存储 → 训练 → 提升模型能力。

### 2.1 知识获取子域

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `knowledge_generator` | 1092 | LLM+EvoKG→Q&A 生成 | ✅ 今天修 |
| `external_explorer` | 532 | arXiv+GitHub+PyPI 探索 | ⚠️ |
| `external_fetcher` | — | 外部数据采集 | ⚠️ |
| `trending_fetcher` | — | 热榜采集 | ⚠️ |
| `web_learner` | — | 网页学习 | ⚠️ |
| `web_learning_pipeline` | — | 网页学习管线 | ⚠️ |
| `paper_fetcher` | — | 论文采集 | ⚠️ |
| `auto_learner` | 646 | 自主学习引擎 | ⚠️ |
| `deep_understanding_engine` | 190 | 深度理解引擎 | ⚠️ |

### 2.2 知识存储子域

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `evokg` | 2719 | 进化知识图谱（54 模块依赖） | ✅ |
| `experience_bank` | 435 | 经验存储 SQLite（48 模块依赖） | ✅ 今天扩展 |
| `knowledge_graph/engine` | 242 | 知识图谱引擎 | ✅ |
| `knowledge_graph/health` | 14 | 知识图谱健康检查 | ⚠️ |
| `world_model/__init__` | 72 | 世界模型（256 维统一空间） | ⚠️ |
| `world_model/training` | 22 | 世界模型训练（今天新建） | ⚠️ |
| `elastic_memory` | 605 | 弹性记忆协调器 | ✅ |

### 2.3 知识处理子域

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `knowledge_trainer` | 217 | Q&A→ExperienceBank 注入 | ✅ 今天修 |
| `knowledge_gate` | — | 知识门禁（质量过滤） | ✅ |
| `knowledge_digester` | — | 知识消化+衰减 | ✅ |
| `knowledge_internalizer` | — | 知识内化到 EvoKG | ✅ |
| `unified_learner` | — | 统一学习器 | ✅ |
| `self_directed_learner` | — | 自主学习器 | ✅ |
| `learning` | 839 | 学习引擎 | ⚠️ |
| `learning_engine/engine` | 783 | 自主学习引擎 | ⚠️ |
| `concept_verification` | 1242 | 概念验证引擎 | ✅ |
| `solidification_engine` | — | 知识固化 | ⚠️ |
| `domain_bootstrapper` | 183 | 17 域种子知识引导 | ⚠️ |

### 2.4 训练执行子域

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `training_executor` | 220 | LoRA 训练执行器 | ✅ 今天修 |
| `training_curriculum` | — | 训练课程管理 | ✅ |
| `neural/training_loop` | 109 | 神经网络训练循环 | ⚠️ shape 错 |
| `neural/lora_auto_tuner` | 361 | LoRA 自动微调 | ⚠️ |
| `neural/distill/loader` | 33 | LoRA 蒸馏（今天新建） | ⚠️ |
| `neural/heads` | 262 | LoRA 头管理 | ✅ |
| `neural/learning_heads` | 151 | 学习头枢纽 | ✅ |
| `neural/unified_heads` | 72 | 统一头枢纽 | ✅ |
| `targeted_trainer` | — | 靶向训练器 | ⚠️ |
| `lora_manager` | 174 | LoRA 管理器 | ⚠️ |

### 知识域总计：~45 模块

---

## 域 3：自我进化域 — "肌肉骨骼"

**职责**：自我博弈 → 发现弱点 → 研究改进 → 代码/模型进化。

### 3.1 自博弈子域

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `self_play_engine` | 1619 | 自博弈编排 | ⚠️ |
| `self_play/challenger` | 2843 | 13 域问题生成器 | ⚠️ |
| `self_play/solver` | 3455 | LLM+Internal 解题 | ⚠️ 代码质量差 |
| `self_play/verifier` | 953 | 多域多维验证 | ✅ 今天修 |
| `self_play/cross_modal_challenger` | 384 | 跨域联想引擎 | ⚠️ |
| `self_play/kg_challenger` | 583 | KG 驱动出题器 | ⚠️ |
| `ast_mutation_engine` | 257 | AST 语义变换 | ⚠️ |
| `mutation_evolver` | — | 变异进化器 | ⚠️ |

### 3.2 缺口分析子域

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `gap_analyzer/__init__` | 2238 | 能力缺口分析（20 模块依赖） | ⚠️ 路由全 0 |
| `gap_detector` | — | 缺口检测 | ⚠️ |
| `neural/gap_analyzer_nn` | 50 | NN 缺口分析器 | ⚠️ |
| `neural/blind_spot_predictor` | 79 | 盲点检测 | ⚠️ |
| `neural/complexity_scorer_nn` | 40 | 复杂度评分 | ⚠️ |
| `neural/intrinsic_curiosity` | 341 | 内在好奇心模块 | ⚠️ |

### 3.3 研究院子域

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `research_institute` | 497 | 7 阶段研究闭环 | ✅ |
| `research_engine/engine` | — | 研究引擎 | ⚠️ |
| `research_engine/health` | — | 研究引擎健康 | ⚠️ |
| `capability_upgrader` | 325 | 研究院执行臂（今天重构） | ✅ |
| `curiosity_engine` | 1733 | 好奇心驱动研究 | ✅ |
| `curiosity_core/engine` | 508 | 三颗心引擎 | ✅ |
| `intrinsic_motivation/engine` | 1088 | 内在动机引擎 | ⚠️ |
| `hypothesis_engine` | — | 假设引擎 | ⚠️ |
| `induction_engine` | — | 归纳引擎 | ⚠️ |

### 3.4 代码进化子域

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `evolution_engine` | 3650 | 元认知自修改引擎 | ❌ |
| `evolution_decision_engine` | 1334 | 进化决策引擎 | ⚠️ |
| `evolution` | 1064 | 统一进化引擎 | ⚠️ |
| `evolution_roadmap` | 681 | 进化路线图 | ✅ |
| `evolution_validator` | 106 | 进化验证器 | ⚠️ |
| `self_modifier/__init__` | 972 | 安全自改系统 | ❌ |
| `self_heal` | — | 自愈引擎 | ⚠️ |
| `self_heal_brain` | — | 自愈大脑 | ⚠️ |
| `capability_improvement_agent` | 156 | 能力改进执行器 | ⚠️ |
| `deep_architect` | 152 | 深度架构师 | ⚠️ |
| `desloppify` | 507 | 自动格式化+Lint | ⚠️ |

### 进化域总计：~40 模块

---

## 域 4：自我意识域 — "内省"

**职责**：知道自己是谁、会什么、缺什么、情绪怎样、该做什么。

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `meta_cognition/__init__` | — | 元认知系统（15 模块依赖） | ✅ |
| `metacognition/engine` | 507 | 元认知引擎 v2 | ✅ |
| `self_model/engine` | 524 | 自我认知引擎 | ✅ |
| `self_model/health` | 26 | 自我模型健康检查 | ⚠️ |
| `autobiographical_memory` | 787 | 自传记忆（5000 集） | ✅ |
| `consciousness/engine` | 521 | 意识循环 | ✅ |
| `nexus_mood` | — | 3D 情绪+马斯洛需求 | ✅ |
| `nexus_self` | 1887 | 战略决策层 | ✅ |
| `nexus_self_model` | — | 11 维自我感知 | ✅ |
| `living_core/psi` | 179 | 生理节律核心 | ✅ |
| `living_core/identity` | 168 | 身份权重核心 | ✅ |
| `living_core/alive_core` | 187 | 活体核心 | ✅ |
| `living_core/methodology` | 150 | 方法论路由 | ✅ |
| `living_core/integration` | 58 | 消息管线集成 | ✅ |
| `identity_core/consciousness_loop` | 154 | 永续意识循环 | ✅ |
| `identity_core/identity_sampler` | 199 | 训练样本生成 | ✅ |
| `identity_core/identity_trainer` | 228 | 身份 LoRA 训练 | ✅ |
| `identity_core/integration` | 74 | 消息管线接入 | ✅ |

### 自知域总计：~20 模块

---

## 域 5：工具执行域 — "手脚"

**职责**：文件操作、代码执行、浏览器控制、桌面控制、B站/A站管线。

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `tools_registry` | — | 工具注册中心（61 工具） | ✅ |
| `tools_registry_core` | — | 工具注册核心 | ✅ |
| `tools_code` | — | 代码工具 | ✅ |
| `tools_file` | — | 文件工具 | ✅ |
| `tools_web` | — | 网络工具 | ✅ |
| `tools_system` | — | 系统工具 | ✅ |
| `tools_knowledge` | — | 知识工具 | ✅ |
| `tools_skills` | — | 技能工具 | ✅ |
| `tools_agent` | — | Agent 工具 | ✅ |
| `windows_tools` | — | Windows 专用工具 | ✅ |
| `speech_tools` | — | 语音工具 | ✅ |
| `vision_tools` | — | 视觉工具 | ✅ |
| `browser_control` | 400 | Playwright 浏览器 | ⚠️ |
| `desktop_control` | 479 | pyautogui 桌面控制 | ⚠️ |
| `tool_bridge` | — | 工具桥接 | ⚠️ |
| `tool_discipline` | — | 工具纪律 | ⚠️ |
| `tool_guardrails` | — | 工具护栏 | ✅ |
| `tool_learning` | — | 工具学习 | ⚠️ |
| `tool_router` | — | 工具路由 | ✅ |
| `tool_search` | — | 语义工具发现 | ⚠️ |
| `setup_tools` | — | 工具安装 | ⚠️ |

### 管线子域

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `autonomous/bilibili_pipeline` | 848 | B站视频管线 | ✅ |
| `autonomous/acfun_pipeline` | 265 | A站视频管线 | ⚠️ |
| `autonomous/seed_extractor` | 736 | 多模态种子提取 | ⚠️ |
| `autonomous/video_learner` | 606 | 视频学习器 | ⚠️ |
| `autonomous/dialogue_learner` | 671 | 对话学习器 | ⚠️ |
| `autonomous/integration` | 584 | 自主集成 | ⚠️ |
| `scenario_generator` | 533 | 场景生成 | ⚠️ 崩溃 |
| `code_seed_extractor` | 270 | 代码种子提取 | ⚠️ |
| `web_learning_pipeline` | — | 网页学习管线 | ⚠️ |

### 工具域总计：~30 模块

---

## 域 6：用户理解域 — "共情"

**职责**：理解用户画像、偏好、知识水平；越用越懂用户。

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `user_model/engine` | 320 | 用户模型引擎 | ⚠️ 只有 3 关键词 |
| `user_model/health` | 50 | 用户模型健康 | ⚠️ |
| `user_model_engine` | — | 用户模型（旧版） | ⚠️ |
| `user_identity/__init__` | — | 用户身份检测 | ⚠️ |
| `agent_bridge/memory_manager` | 558 | 记忆管理器 | ✅ |
| `agent_bridge/memory_provider` | 281 | 记忆提供者基类 | ✅ |
| `agent_bridge/skill_utils` | 474 | 技能工具 | ✅ |
| `agent_bridge/nexus_state` | 2249 | SQLite 状态存储 | ✅ |
| `agent_bridge/nexus_time` | 105 | 时区感知时钟 | ✅ |

### 用户域总计：~10 模块

---

## 域 7：基础设施域 — "地基"

### 7.1 事件系统

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `event_bus` | 702 | 统一事件总线（64 模块依赖） | ✅ |
| `event_emitter` | 162 | 事件发射器（兼容旧接口） | ✅ |
| `event_auditor` | 464 | 事件审计+自愈 | ✅ |
| `signal_bus` | — | 信号总线 | ✅ |
| `signal_tracker` | 126 | 信号追踪（今天修） | ✅ |
| `feedback_bus` | — | 反馈总线 | ⚠️ |
| `memory_bus` | — | 记忆总线 | ✅ |

### 7.2 存储系统

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `evokg` | 2719 | 进化知识图谱 | ✅ |
| `experience_bank` | 435 | 经验银行 SQLite | ✅ |
| `memory_system` | — | 记忆系统 | ⚠️ |
| `memory_store` | — | 记忆存储 | ⚠️ |
| `memory_index` | — | 记忆索引 | ⚠️ |
| `memory_coordinator` | — | 记忆协调 | ⚠️ |
| `unified_memory` | — | 统一记忆 | ✅ |
| `session_memory` | — | 会话记忆 | ✅ |
| `session_store` | — | 会话存储 | ✅ |
| `rag_memory` | — | RAG 记忆 | ⚠️ |
| `chroma_client` | 62 | ChromaDB 客户端 | ✅ |
| `hybrid_retrieval` | — | 混合检索 | ⚠️ |
| `memories` | 192 | 记忆工具 | ⚠️ |
| `memory_health_check` | 169 | 记忆健康检查 | ❌ 死模块 |

### 7.3 监控系统

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `sentinel` | 1183 | 哨兵监控 | ✅ |
| `sentinel_safety` | — | 哨兵安全 | ✅ |
| `health_monitor` | — | 健康监控 | ⚠️ |
| `ai_capability_monitor` | 348 | AI 能力监控 | ⚠️ |
| `resource_monitor` | — | 资源监控 | ⚠️ |
| `checkpoint` | 334 | 检查点系统 | ⚠️ |
| `checkpoint_manager` | 575 | 检查点管理 | ⚠️ |
| `watcher` | — | 文件监视 | ⚠️ |
| `growth_monitor` | — | 成长监控 | ⚠️ |

### 7.4 调度系统

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `heartbeat_loop` | 1784 | 心跳调度（今天修） | ✅ |
| `task_runner` | — | 任务执行器 | ✅ |
| `task_execution_loop` | — | 任务执行循环 | ✅ |
| `cron_manager` | 558 | 定时任务管理 | ✅ |
| `autonomous_planner` | 967 | 主动规划引擎 | ✅ |

### 7.5 基础组件

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `constants` | 138 | 全局常量（29 模块依赖） | ✅ |
| `nexus_constants` | — | Nexus 常量 | ✅ |
| `module_base` | — | 模块基类（13 模块依赖） | ✅ |
| `nexus_types` | — | 类型定义 | ✅ |
| `error_classifier` | 242 | 错误分类器 | ✅ |
| `except_scanner` | 379 | 静默异常扫描 | ✅ |
| `backoff_manager` | 201 | 统一退避策略 | ✅ |
| `auto_retry` | 50 | 自动重试 | ✅ |
| `timeout_config` | — | 超时配置 | ⚠️ |
| `state` | — | 状态管理 | ⚠️ |
| `runtime` | — | 运行时 | ⚠️ |
| `checkpoint` | 334 | 检查点 | ⚠️ |
| `path_conventions` | — | 路径约定 | ✅ |
| `workspace_manager` | 251 | 工作区管理 | ⚠️ |
| `workspace_organizer` | — | 工作区组织 | ⚠️ |
| `file_discipline/engine` | 669 | 文件管理铁律 | ✅ |
| `process_discipline` | — | 流程纪律 | ⚠️ |
| `workflow_discipline` | — | 工作流纪律 | ⚠️ |

### 7.6 桥接/集成

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `neural/fused_arch_bridge` | 251 | 6 NN 融合桥（今天修） | ✅ |
| `neural/evokg_world_model` | 167 | EvoKG↔WorldModel 桥 | ⚠️ |
| `neural/free_energy_principle` | 96 | 自由能原理 | ⚠️ |
| `neural/nexus_reasoner` | 334 | 统一预测层 | ✅ |
| `neural/encoders` | 548 | 5 模态编码器 v3 | ✅ |
| `neural/fallback` | 61 | NN 不可用时的启发式回退 | ✅ |
| `neural/router_nn` | 69 | 神经网络路由器 | ✅ |
| `neural/signal_bus_nn` | 40 | 神经网络信号总线 | ✅ |
| `neural/world_model` | 415 | 统一 256 维空间 | ⚠️ |
| `wm_v19_hook` | — | World Model v19 钩子 | ⚠️ |
| `world_model_v19` | — | World Model v19 | ⚠️ |
| `neural_wiring` | — | 22 条神经突触 | ✅ |
| `nexus_brain` | 170 | Qwen 推理（今天修） | ⚠️ |
| `nexus_integration` | — | 集成层 | ⚠️ |
| `nexus_pipeline` | — | 管线 | ⚠️ |
| `prism_pipeline` | — | 棱镜管线 | ⚠️ |

### 7.7 代码分析/管理

| 模块 | 行数 | 职责 | 状态 |
|------|:--:|------|:--:|
| `code_analyzer` | 1333 | 全系统代码分析器 | ⚠️ |
| `codebase_understand` | 217 | 代码库理解 | ⚠️ |
| `code_seed_extractor` | 270 | 代码种子提取 | ⚠️ |
| `self_study/scan` | 183 | 自认知扫描入口 | ⚠️ |
| `self_study/static_parser` | 379 | 静态代码解析（AST） | ✅ |
| `self_study/self_evokg` | 680 | 自认知 EvoKG 集成 | ⚠️ |
| `capability_tree` | 907 | 能力树（21 模块依赖） | ✅ |
| `capability` | 195 | 能力追踪 | ⚠️ |
| `eval_suite` | 196 | 综合评测套件 | ⚠️ |
| `reflection/*` | 10 模块 | 自我反思系统 | ✅ |

### 基础设施域总计：~90 模块

---

## 各域状态汇总

| 域 | 模块数 | ✅可用 | ⚠️半成品 | ❌坏/死 |
|------|:--:|:--:|:--:|:--:|
| 认知推理 | ~40 | 30 | 10 | 0 |
| 知识工厂 | ~45 | 15 | 28 | 2 |
| 自我进化 | ~40 | 5 | 30 | 5 |
| 自我意识 | ~20 | 18 | 2 | 0 |
| 工具执行 | ~30 | 10 | 20 | 0 |
| 用户理解 | ~10 | 6 | 4 | 0 |
| 基础设施 | ~90 | 40 | 45 | 5 |
| **总计** | **~275** | **124** | **139** | **12** |

---

## 当前最长端到端链路

```
用户消息(飞书) → gateway → agent_response → cognitive_loop → LLM → 回复
                                                                    ✅ 通

B站搜索 → yt-dlp下载 → 文件落盘
                                                                    ✅ 通

knowledge_generator → knowledge_trainer → experience_bank
  → training_executor → LoRA微调 → 模型变强
                       ⚠️ 今天接线, 有3处断点待修

self_play → gap_analyzer → research_institute
  → capability_upgrader → 训练数据 → knowledge_trainer → ...
                       ⚠️ SelfPlay代码质量差, 闭环未验证
```
