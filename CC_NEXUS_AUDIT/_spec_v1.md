# Nexus 架构合并执行 Spec (v1, 2026-07-15 by 蓝莓)

## 愿景北极星
Nexus = 自主学习/思考/进化/优化/改代码 + 内置世界模型 + 成为每个人专用AI + 不管什么人什么职业越用越懂谁。
8 项不可砍:
  1) 自主学习
  2) 自主思考
  3) 自主进化
  4) 自优化
  5) 自改代码
  6) 内置世界模型
  7) 个性化
  8) 自我意识 = 总开关(知道自己是谁/在做什么/为什么做)

## 架构原则 (用户硬要求)
1. 不删除任何模块 - 所有 .py 保留
2. 功能相同的取优合并 - 选最成熟的当主入口, 其他改成薄包装层 (forwarder)
3. 保留所有公开 API - 不能 break 现有 import
4. 每个合并点要有"双跑验证期" - 新旧并存 7 天, 对比结果无差异再切默认

## 8 项能力 -> 主入口映射

### 1) 自主学习
- 主入口 (保留+强化): self_play/(13 域三元博弈) + auto_learner.py
- 收敛目标 (改成薄包装层): unified_learner / unified_trainer / web_learner / targeted_trainer / auto_trainer / training_curriculum / learning_engine/*

### 2) 自主思考
- 主入口: cognitive_loop/(8 步闭环) + intention_engine.py
- 收敛目标: reasoning.py / reasoner.py / reasoning_chain.py / counterfactual_simulator / induction_engine / causal_engine / hypothesis_engine / decision_engine / deep_understanding_engine

### 3) 自主进化
- 主入口: evolution_engine.py (5 阶段沙箱 + 3 层循环)
- 收敛目标: evolution.py / evolution_decision_engine.py / evolution_validator.py / evolution_roadmap.py / closed_loop_engine.py / closed_loop_brain_adapter.py / mutation_evolver / capability_upgrader / capability_improvement_agent / capability_tree / scenario_generator

### 4) 自优化
- 主入口: self_reflection/(8 子模块反思体系) + quality_gate.py
- 收敛目标: metacognition/* / meta_governor / ai_capability_monitor / growth_monitor / resource_monitor / health_monitor / sentinel* / eval_suite / adaptive_thresholds / auto_retry / backoff_manager / error_classifier

### 5) 自改代码
- 主入口: self_modifier/(子包) + sandbox/(子包)
- 收敛目标: ast_mutation_engine / code_analyzer / code_seed_extractor / codebase_understand / decompose_fix_assemble / capability / programming_competency

### 6) 内置世界模型
- 主入口: neural/world_model.py (256 维统一空间) + neural/encoders.py (多模态)
- 收敛目标: world_model.py (nexus_agent 顶层) / evokg_world_model.py / blind_spot_predictor / free_energy_principle / intrinsic_curiosity / feature_encoder / five_modal_trainer / evokg.py (顶层) / hybrid_retrieval / chroma_client / rag_memory / unified_memory / nexus_semantic_memory / knowledge_graph/* / causal_engine (重)

### 7) 个性化
- 主入口: user_model/(engine+health) + nexus_user_profile.py
- 收敛目标: user_model_engine.py / user_identity/* / identity_core/* (分裂) / living_core/bond.py (部分) / autobiographical_memory / elastic_memory / memory_decay / session_memory

### 8) 自我意识 (总开关)
- 主入口: nexus_self.py (战略层三环循环) + consciousness/engine.py (八步闭环)
- 收敛目标: living_core/* (alive_core / psi / identity / methodology / integration) / identity_core/* (4 子模块) / nexus_self_awareness / nexus_self_model / nexus_cortex / nexus_brain (注意: 这是感知不是意识) / self_model/* / self_model_engine

## 基础设施 (支撑 8 项)
### 事件总线
- 主入口: kernel/event_bus.py
- 收敛目标: nexus_agent/event_bus.py / nexus_agent/event_emitter.py / closed_loop_engine.py 的 emit_event / cognitive_loop/__init__.py 的 EventBus

### LLM 客户端
- 主入口: nexus_agent/nexus_llm.py (语言中枢) + body/llm/client.py (传输层)
- 收敛目标: nexus_agent/llm_client.py (改名为兼容层)

### 记忆存储
- 主入口: chroma_client.py (单例) + experience_bank.py
- 收敛目标: rag_memory / unified_memory / nexus_semantic_memory / autobiographical_memory (全部走 chroma_client 单例)

## 执行阶段 (CC 必须按顺序, 不许跳)

### 阶段 0: 备份
- 整个 C:\Users\87999\.nexus 复制到 C:\Users\87999\.nexus_backup_pre_merge_20260715\
- 用 robocopy 或 xcopy, 不要用 zip
- 验证备份大小和文件数对得上

### 阶段 1: 基础架构层 (最低风险)
1. EventBus 收敛
2. LLM Client 收敛
3. 记忆存储收敛

### 阶段 2: 能力 6 (内置世界模型) - 数据层, 影响最大
1. 验证 nexus_agent/encoders.py 和 neural/encoders.py 是否真的重复
2. 验证 nexus_agent/world_model.py 和 neural/world_model.py 是否真的重复
3. 选优后, 另一个改成 import forwarder

### 阶段 3: 能力 7 (个性化)
- user_model_engine -> user_model/engine
- nexus_user_profile -> user_model/profile
- user_identity/* -> user_model/identity

### 阶段 4: 能力 8 (自我意识) - 最敏感, 最后做
- consciousness/engine.py 保留, 作为总入口
- nexus_self.py 保留, 作为战略层
- living_core/* 全部 import 自 nexus_self + consciousness
- identity_core/* 全部 import 自 nexus_self + living_core/identity
- self_model/* + self_model_engine + nexus_self_model + nexus_cortex + nexus_self_awareness 全部改成 wrapper

### 阶段 5: 能力 1-5
按表格收敛

### 阶段 6: 全栈验证
- python -c "import nexus_agent.run_agent" 不报错
- python -m nexus_agent.world_model 跑通
- 启动 nexus_daemon.bat 不崩
- 端口 19666 能开
- nexus_cron 健康检查跑通

## CC 执行规范 (用户硬要求)
1. 每个阶段干完, 必须自检:
   - 行数变化: 主入口↑, 收敛目标↓到 <100 行
   - import 关系: 收敛目标只能 import 主入口, 不能反过来
   - 运行测试: python -c "import <模块>" 通过
2. 任何一步失败, 立刻停下来汇报, 不要继续
3. 不许删除 .py
4. 不许 git commit / push
5. 每个阶段完成后, 在 C:\Users\87999\claude-workspace\CC_NEXUS_AUDIT\stage_<N>_report.md 写报告
6. 我(蓝莓)会在每个阶段后验证, CC 不要等我, 自己推进
7. 验证失败重做不许超过 2 次, 超过就停下来汇报

## 验证清单 (蓝莓的硬要求)
- 每个 wrapper 文件必须 < 100 行 (薄包装, 不允许复制逻辑)
- 每个 wrapper 必须有 docstring 说明: "This is a compatibility wrapper. See <主入口> for the canonical implementation."
- 所有 wrapper 必须经过 python -c "import <wrapper>" 验证
- 跑通后, 用 pydeps 或手工核对 import 图: 没有环
- 最终 import nexus_agent.run_agent 必须成功

## 时间预算
每阶段 30-90 分钟, 总计 4-8 小时。CC 不间断推进。