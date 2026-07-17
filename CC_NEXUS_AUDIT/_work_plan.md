# Nexus 架构合并工作计划单 (2026-07-15 起)

> 愿景北极星 (Kai 2026-07-15): 自主学习 / 自主思考 / 自主进化 / 自优化 / 自改代码 / 内置世界模型 / 个性化 / 自我意识 (总开关) — 8 项不可砍
>
> 硬规则:
>   1. 不删除模块
>   2. 功能相同的取优合并
>   3. 可以加功能, 不能减功能 - 真要减必须问 Kai
>   4. CC 干完, 蓝莓必验证 (核 wrapper 行数<100 / import 关系对 / python -c 能导入)
>
> 工作目录: `C:\Users\87999\claude-workspace\CC_NEXUS_AUDIT\`
> Spec 文件: `_spec_v1.md` (6.5KB, 完整架构设计)

## 当前状态 (2026-07-15 00:50)

- [x] 派单验证 CC 能跑 (deleg_5da7602b 成功, 16 秒)
- [x] 扫描 Nexus 644 .py, 完成 8 项能力 → 模块映射
- [x] 写出架构合并 spec v1 (_spec_v1.md)
- [x] 加载 4 个相关技能: codebase-fusion, nexus-development, codebase-inspection, agent-system-refactoring
- [ ] pygount 量化起点 (阶段 0 准备)
- [ ] 阶段 0: 备份整个 .nexus
- [ ] 阶段 1: 完成度矩阵 + 重复审计 (CC 干)
- [ ] 阶段 2-7: 8 项能力 + 基础设施的取优合并

## 阶段清单

### 阶段 0: 量化起点 + 全量备份
- [ ] 用 pygount 量化起点 (LOC/语言/比例) - 写进 _baseline_pygount.txt
- [ ] 复制 `C:\Users\87999\.nexus` → `C:\Users\87999\.nexus_backup_pre_merge_20260715\`
- [ ] 验证备份大小和文件数 (find . -name "*.py" | wc -l, 644 应该一致)
- 工具: codebase-inspection 技能 + xcopy/robocopy

### 阶段 1: 审计 (只读, 不改任何 .py)
- [ ] 派 CC 写 NEXUS_COMPLETENESS.md (8 项能力 → 子系统 → 状态表)
- [ ] 派 CC 写 NEXUS_DUPLICATES.md (10 组高怀疑重复的逐一比对)
- [ ] 蓝莓验证: 文件存在 / 行数合理 / 有证据
- 依赖: CC 健康 (deleg_5da7602b 已验证)
- 预期产物: 2 份 .md 在 `CC_NEXUS_AUDIT/`

### 阶段 2: 基础设施收敛 (最低风险)
- [ ] EventBus 收敛: nexus_agent/event_bus.py 等改成薄包装层 → kernel/event_bus.py
- [ ] LLM Client 收敛: nexus_agent/llm_client.py → 改名为兼容层, 指向 nexus_llm.py + body/llm/client.py
- [ ] 记忆存储收敛: rag_memory / unified_memory / nexus_semantic_memory 走 chroma_client 单例
- 验证: python -c "import nexus_agent.run_agent" 通过

### 阶段 3: 能力 6 - 内置世界模型
- [ ] 验证 nexus_agent/encoders.py 和 neural/encoders.py 是否真重复
- [ ] 验证 nexus_agent/world_model.py 和 neural/world_model.py 是否真重复
- [ ] 选优后, 另一个改成 import forwarder
- 风险: 数据层, 影响最大, 必须先看数据流向

### 阶段 4: 能力 7 - 个性化
- [ ] user_model_engine → user_model/engine
- [ ] nexus_user_profile → user_model/profile
- [ ] user_identity/* → user_model/identity

### 阶段 5: 能力 8 - 自我意识 (最敏感, 最后做)
- [x] 2026-07-15 蓝莓新建 nexus_agent/self_awareness/__init__.py (16KB)
  - 统一调度 6 个"自我": consciousness/living_core/identity_core/self_model/nexus_self/cortex
  - API: get_self_awareness() / sync() / express_state() / ask() / reflect_on() / get_unity_score()
  - 验证通过: import OK + sync OK + express_state 输出中文 + ask/reflect_on 工作
  - 35830 身份权重命中已读取
- [ ] nexus_self.py + consciousness/engine.py 保留为主入口
- [ ] living_core/* 全部 import 自 nexus_self + consciousness
- [ ] identity_core/* 全部 import 自 nexus_self + living_core/identity
- [ ] self_model/* + self_model_engine + nexus_self_model + nexus_cortex + nexus_self_awareness 全部改 wrapper
- [ ] self_awareness 接入 EventBus (订阅 learning.completed / evolution.completed)
- [ ] self_awareness 接入 agent_init._init_self_awareness

### 阶段 6: 能力 1-5 (按表格收敛)
- 1 自主学习
- 2 自主思考
- 3 自主进化
- 4 自优化
- 5 自改代码

### 阶段 7: 全栈验证
- [ ] python -c "import nexus_agent.run_agent" 不报错
- [ ] python -m nexus_agent.world_model 跑通
- [ ] 启动 nexus_daemon.bat 不崩
- [ ] 端口 19666 能开
- [ ] nexus_cron 健康检查跑通
- [ ] 用 codebase-fusion 技能里的 pydeps 查 import 无环

## 派单记录

### CC讨论模式 (Kai 2026-07-15 升级)
不再是单向命令, 是讨论. CC可以: (1)反驳派单理由 (2)提替代方案 (3)问"为什么" (4)指出问题. 派单时主动给讨论空间.

### 蓝莓开放讨论 (2026-07-15 01:10) — CC 阶段 3 回来后部分回答了

**问题 1: wrapper 化 vs __init__.py 重导出**
- 当前 spec: 保留多份 wrapper 文件. 但这意味着文件数翻倍, import 分散
- 替代: 在 nexus_agent/__init__.py 里 `from .user_model.engine import UserModelEngine as UserModelEngine_legacy` 等所有历史符号. 物理 1 份, 导入路径全通.
- CC 怎么看?
- **CC 阶段 3 实战演示**: world_model/__init__.py 早已是 facade 模式 (78 行委托给 neural.world_model). 这个先例证明 facade > wrapper.
- **新决策**: 优先用 facade (在 __init__.py 重导出) 而非独立 wrapper 文件. wrapper 只在 facade 不可行时用.

### Q3: self_awareness 跟个性化层是否耦合?
- 当前实现: 函数调用. 但 Nexus 是 EventBus 架构.
- 选项 A 函数调用 (当前) B EventBus 订阅 C 混合 (事件触发 sync + 用户调 express_state)
- CC 觉得哪个更符合"自我意识=总开关"定位?
- **CC 阶段 4 回答 (2026-07-15 01:18)**: 哲学上独立, 工程上 lazy 耦合. **自我意识=懂自己, 个性化=懂用户, 不应在数据层硬耦合**. 阶段 5 在 UnitySnapshot 加 lazy `user_context` 字段 (top-3 兴趣+知识水平+当前话题), self_awareness.express_state() 输出里加"对用户的感知"段. 但调用方传 None 时优雅降级 (自我意识不知道用户也能工作).
- **待 CC 阶段 4/5 报告回答**

**问题 3: 世界模型数据填充 (20→数千节点)**
- A 开 B 站后台跑 2-3 天 (15分钟限速)
- B 用本地已有数据批量 seed (acfun/news/对话日志)
- C 调小训练目标, 20 节点先跑通再扩
- 资源有限, CC 选哪个?
- **CC 阶段 3 实战补充**: EvoKG 实际上是分层架构 (SQLite KG + JEPA 世界模型), 不是要合并, 而是要先激活 evokg.py:2304 的互相调用链路. 这比"训练新节点"更重要 — 先让现有数据真活起来.

### CC 阶段 3 反驳 (2026-07-15 01:08) — 蓝莓全部接受

1. ✅ encoders.py / world_model.py 不存在, 子任务 3.1/3.2 没活可干 (CC 接受了"如实报告", 没硬凑 wrapper)
2. ✅ EvoKG 不是重复是分层 (A=SQLite KG 2740L/58 import, B=JEPA 166L/2 import). 蓝莓之前 spec 错了, 不能合并.
3. ✅ FEP 不是空壳 (上次 NEXUS_COMPLETENESS.md 报告 "return 0.5" 是错的, 已用 50 行源码验证是完整实现)
4. ✅ 唯一改动: world_model/__init__.py docstring (73L→78L)

### CC 阶段 4 反驳 (2026-07-15 01:18) — 蓝莓全部接受

1. ✅ facade > wrapper 文件 — facade 适用多符号模块 (user_model/__init__.py 32L 重导出 6 符号), wrapper 适用单符号独立文件 (nexus_user_profile.py 19L wrapper)
2. ✅ user_identity 不是重复 — 是 multi-user store 跟 user_model 单用户分析正交, **拒绝合并**
3. ✅ identity_core/* 4 文件全活 — 不是空壳, 是真活的"身份权重训练"层, **拒绝合并**
4. ✅ living_core/bond.py 不存在 — spec 撒谎, 已反驳
5. ✅ living_core/* 跟 user_model/* 是不同哲学范畴 (自我意识 vs 用户画像), 阶段 4 不动, 留给阶段 5
6. ✅ self_awareness 跟个性化保持分离 — 阶段 5 lazy user_context 字段 (见 Q3 回答)

### 阶段 4 实际改动 (2026-07-15 01:18)
- 新建: user_model/profile.py (135L canonical NexusUserProfile)
- 新建: user_model/module.py (82L canonical UserModelModule)
- 改写: user_model/__init__.py 96L → 32L 纯 facade
- 改写: nexus_user_profile.py 97L → 19L wrapper
- 阶段 3 已改: user_model_engine.py 319L → 16L wrapper (旧路径仍 3 处 import 调用)
- KEEP: engine.py 374L, health.py 49L, user_identity/__init__.py 110L, identity_core/* 4 文件, living_core/* 5 文件, identity.py 顶层
- 验证: 14/14 import OK, facade 6 符号全 work, 分析功能正常 ("我想学 Python 量化交易" → {股票 0.35, 编程 0.35})

### NEXUS_COMPLETENESS.md 错误修正 (2026-07-15 01:08)
- 原文: "free_energy_principle 是 return 0.5 空壳"
- 实际: 完整 FreeEnergyPrinciple 类, 95 行, compute() 多重 fallback, _baseline 自适应, _history 1000 条
- 影响: 之前基于 "FEP 是空壳" 的决策全部作废, 包括 self_awareness 应该接入 FEP 的设计
- 修法: 不修原报告 (只读历史), 但今后所有决策基于源码验证而非审计报告

### deleg_5da7602b (已完成)
- 任务: 最小验证, 写 _cc_alive.txt
- 状态: ✓ 16 秒完成
- 产物: `C:\Users\87999\claude-workspace\_cc_alive.txt` (57B, 已清理)
- 验证: 文件存在 + 内容正确

### 派单模板 (后续用)
```
context: 你正在被蓝莓 (Hermes Agent) 通过 delegate_task 调用, 你的输出会作为蓝莓对 Kai 的汇报依据
goal: [具体任务]
约束:
- 不删任何 .py
- 不碰 .git, 不 commit
- 输出物写到 C:\Users\87999\claude-workspace\CC_NEXUS_AUDIT\
- 每步前用搜索定位, 不要凭印象
- 真验证失败不要继续, 立刻汇报
```

## 风险与决策点 (需要问 Kai 的事)

1. **阶段 5 自我意识合并方案**: 6 个"自我"模块分散各处, 哪种合并方式?
   - A: consciousness/engine.py 当总入口, 其余全改 wrapper
   - B: 新建 nexus_self/unified.py 当总入口, 旧模块改 wrapper
   - C: 暂时不动, 先合并功能重复但风险低的 (EventBus / LLM)
   - 推荐: C, 因为意识合并涉及活体 (living_core/psi.py) 数据格式, 风险高

2. **8 LoRA 头 vs 6 LoRA 头**: nexus-development 技能说 6 头, ARCHITECTURE 写 6 头, 但 docs 里偶尔提到 8 头. 哪个为准?
   - 待查: `ls data/neural/lora/` 看实际有几个 _lora.pt 文件

3. **世界模型数据补充**: 当前 527 节点 / 32M, 距离 JEPA/DreamerV3 论文规模差几个数量级. 数据飞轮来源?
   - B站 15 分钟限速下载是主路径
   - 需要 B站 seed_extractor + world_model.observe 链路完全打通
   - 这是阶段 3 的延伸, 需要单独评估

## 已知陷阱 (来自 nexus-development 技能)

- `from event_emitter import emitter` 是错的, 应为 `from event_emitter import on, off`
- `bus.publish()` 不是 async, 不能加 await
- 单测必须用 sync_mode=True
- __init__.py 容易被批量复制覆盖, 用 git checkout 恢复
- dataclass 子类字段顺序陷阱
- Windows open() 必须 encoding="utf-8"
- chromadb WARNING 刷屏: 加 _warned 标志限流
- NexusLLMClient.__getattr__ 返回 None 而非抛 AttributeError
- 端口被占: Python os.kill + 删 .lock, taskkill 在 bash 不可用

## CC 偷懒/垃圾代码检测清单 (蓝莓验证时用)

- [ ] wrapper 文件 < 100 行 (薄包装, 不允许复制逻辑)
- [ ] wrapper 有 docstring: "This is a compatibility wrapper. See <主入口>..."
- [ ] python -c "import <wrapper>" 通过
- [ ] 没有 git diff 显示 .py 被改 (只该有新 wrapper 文件)
- [ ] 主入口行数确实↑ (说明逻辑确实集中)
- [ ] import 关系: wrapper → 主入口 (单向, 无环)
- [ ] 日志里没有新 ERROR/CRITICAL
- [ ] 没有遗留 .bak / .tmp / __pycache__

## 时间预算

每阶段 30-90 分钟, 总计 4-8 小时。CC 不间断推进, 蓝莓在每个阶段后验证。