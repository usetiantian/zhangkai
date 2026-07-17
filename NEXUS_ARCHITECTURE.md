# Nexus 功能架构设计 (2026-07-15)

> 基于全模块审计(365.py文件)重新设计。
> 原则: 按功能分层, 每层自治, 层间通过EventBus+EvoKG通信。

---

## 八层架构

```
                     ┌──────────────────────────┐
                     │     入口层 (Gateway)       │  飞书/Web/CLI/API
                     │  gateway_runner, nexus_   │
                     │  gateway/run.py, feishu_  │
                     │  client, nexus_web_server │
                     └────────────┬─────────────┘
                                  │
                     ┌────────────▼─────────────┐
                     │     编排层 (Orchestrate)   │  调度+上下文
                     │  heartbeat_loop, autono-  │
                     │  mous_planner, Context-   │
                     │  Orchestrator(wm_v19),    │
                     │  task_runner, cron_manager│
                     └────────────┬─────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
  ┌───────▼──────┐    ┌──────────▼──────────┐    ┌───────▼──────┐
  │ 感知层        │    │   认知层 (Cognition) │    │ 安全层        │
  │ (Perception)  │    │                     │    │ (Safety)      │
  │              │    │  cognitive_loop/     │    │              │
  │ nexus_brain  │    │  closed_loop_engine  │    │ sentinel     │
  │ (Qwen2-VL)   │    │  intention_engine    │    │ constitution │
  │ encoder_hub  │    │  meta_cognition      │    │ gatekeeper   │
  │ llm_engine/  │    │  curiosity_engine    │    │ self_heal    │
  │ vision/      │    │  gap_analyzer/       │    │ verification │
  │ speech/      │    │  reasoner            │    │ sandbox      │
  │ perception/  │    │  decision_engine     │    │ permission   │
  │              │    │  predictive_router   │    │              │
  │ 10文件       │    │  thinking/ why_chain │    │ 25文件       │
  └───────┬──────┘    └──────────┬──────────┘    └───────┬──────┘
          │                       │                       │
          └───────────────────────┼───────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
  ┌───────▼──────┐    ┌──────────▼──────────┐    ┌───────▼──────┐
  │ 学习层        │    │   进化层 (Evolution) │    │ 自我层 (Self) │
  │ (Learning)    │    │                     │    │              │
  │              │    │  evolution_engine    │    │ self_aware-  │
  │ self_play/   │    │  evolution_decision  │    │ ness/        │
  │ self_play_   │    │  solidification_     │    │ nexus_self   │
  │ engine       │    │  engine              │    │ self_model/  │
  │ training_    │    │  mutation_evolver    │    │ self_reflec- │
  │ executor     │    │  capability_upgrader │    │ tion/        │
  │ neural/      │    │  self_modifier/      │    │ identity_    │
  │ training_    │    │  ast_mutation_engine │    │ core/        │
  │ loop         │    │  sandbox/            │    │ living_core/ │
  │ lora_manager │    │  evolving/           │    │ conscious-   │
  │ auto_learner │    │  evolution_validator │    │ ness/        │
  │ auto_trainer │    │  capability_tree     │    │ autobiogra-  │
  │ targeted_    │    │  signal_tracker      │    │ phical_      │
  │ trainer      │    │                     │    │ memory       │
  │ unified_     │    │                     │    │              │
  │ learner      │    │                     │    │ 30文件       │
  │ skill_       │    │ 30文件               │    │              │
  │ generator    │    │                     │    │              │
  │              │    │                     │    │              │
  │ 35文件       │    │                     │    │              │
  └───────┬──────┘    └──────────┬──────────┘    └───────┬──────┘
          │                       │                       │
          └───────────────────────┼───────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
  ┌───────▼───────────────────────▼───────────────────────▼──────┐
  │                    知识层 (Knowledge)                         │
  │                                                              │
  │  evokg (66消费者)  chroma_client  experience_bank             │
  │  memory_bus  memory_coordinator  memory_store  memory_index   │
  │  memory_decay  memory_health_check  nexus_semantic_memory     │
  │  rag_memory  unified_memory  elastic_memory                   │
  │  knowledge_generator  knowledge_internalizer  knowledge_gate  │
  │  knowledge_graph/  knowledge_trainer  knowledge_digester      │
  │  claims_system  capability  domain_bootstrapper               │
  │                                                              │
  │  25文件                                                       │
  └──────────────────────────────────────────────────────────────┘
                                  │
  ┌───────────────────────────────▼──────────────────────────────┐
  │                  基础设施层 (Infrastructure)                   │
  │                                                              │
  │  event_bus (71消费者)  event_emitter  signal_bus             │
  │  nexus_llm (15消费者)  llm_client  llm_engine/               │
  │  agent_init  run_agent  module_base  nexus_fusion            │
  │  config  constants  nexus_constants  nexus_logging           │
  │  error_classifier  auto_retry  backoff_manager               │
  │  checkpoint  checkpoint_manager  state                       │
  │  skills/  code_templates/  tools_registry                    │
  │  workspace_organizer  file_discipline/  workspace_manager/   │
  │  multi_agent  agent_bridge/  agent_commands                  │
  │  cognitive_capability  capability                            │
  │                                                              │
  │  50文件                                                       │
  └──────────────────────────────────────────────────────────────┘
```

---

## 数据流 (四件套互补)

```
入口层 → 编排层 → 感知层(理解) → 认知层(推理) → 知识层(存储)
                     │                │              │
                     │                ├──────────────┤
                     │                │ 学习层(训练)  │
                     │                │ 进化层(自改)  │
                     │                │ 自我层(意识)  │
                     │                └──────────────┘
                     │
              安全层(全链路保护)
```

**四件套:**
```
Qwen      = 感知层 (理解文本/图像/音频) + 学习层 (微调)
EvoKG     = 知识层 (结构化关系 + 图遍历)
ChromaDB  = 知识层 (语义向量搜索)
ExperienceBank = 知识层 (任务轨迹)
```

---

## 层间通信协议

所有跨层通信通过两个中枢:

| 中枢 | 消费者 | 用途 |
|------|--------|------|
| EventBus | 71 | 事件驱动异步通信 |
| EvoKG | 66 | 共享知识存储 |

**层间不直接调用。** A层需要B层的服务 → 发EventBus事件 → B层订阅响应。

---

## 每层所有权

| 层 | 文件数 | 核心入口 | 自主权 |
|----|--------|---------|:---:|
| 入口 | 5 | gateway_runner | 无 |
| 编排 | 6 | heartbeat_loop | 定时调度 |
| 感知 | 10 | nexus_brain | 模型推理 |
| 认知 | 15 | cognitive_loop | 7Agent自主 |
| 学习 | 35 | self_play_engine | 13域自博弈 |
| 进化 | 30 | evolution_engine | 沙箱自修改 |
| 自我 | 30 | self_awareness | 6模块统一 |
| 知识 | 25 | evokg | 知识中枢 |
| 安全 | 25 | sentinel | 全链路 |
| 基础设施 | 50 | event_bus | 通信骨干 |

---

## 与旧架构的差异

| 旧 | 新 |
|----|----|
| 世界模型独立(已删) | 四件套互补覆盖 |
| metacognition独立(已删) | 合并到meta_cognition |
| FullCycle外部编排(已删) | LocalModel内置训练采集 |
| FullCycle外部编排(已删) | LocalModel内置训练采集 |
| B站→EvoKG冗余(已删) | 仅走Qwen微调 |
| 死代码(~1800行) | 已清理 |

---

## 下一步架构演进

1. **自我层接入学习层** — self_awareness读取CapabilityTree数据
2. **进化层接入学习层** — evolution_engine从SelfPlay失败模式生成修复
3. **知识层自动整理** — EvoKGAgent每日维护
4. **编排层智能调度** — heartbeat按能力优先级动态调整tick频率
