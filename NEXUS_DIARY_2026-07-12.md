# Nexus 工作日记 — 2026-07-12 (v19 架构升级 + CC教学)

## 今日主题：从外挂LLM到自感知系统 + CC亲自教学

### 核心变化
- Qwen角色明确：只管语言输出，不参与决策
- ToolOrchestrator上线：Nexus学会真正执行工具
- 8模块统一汇聚：self_model/mood/memory/research/selfheal/lora/evokg/experience
- 341模块全量审计：0僵尸，3冲突已处理
- CC教学9轮：从"0条证据"到真实工具执行

### 新增模块

| 模块 | 功能 |
|------|------|
| nexus_mood.py | 3D情绪 + 马斯洛7层需求 + 4级意识模式 |
| reasoning_chain.py | 5条预置推理链DSL + 可进化 + 领域匹配 |
| memory_decay.py | EvoKG图记忆衰减 + 情感锚点 + 梦境内化 |
| nexus_self_model.py | 11维自我感知 (替代LAAP的10维量子态) |
| neural_wiring.py | 22条神经突触, 事件驱动 |
| prediction_engine.py | 预测→追踪→Brier校准 |
| capability_upgrader.py | 研究发现→自动创建新模块 |
| self_heal_brain.py | 实时监控5类异常 + 8种修复策略 |
| tool_orchestrator.py | Qwen不管决策, 只管输出; 工具执行独立 |
| tool_learning.py | 工具使用→记录→LoRA训练闭环 |

### CC教学9轮记录

```
Round 1: "用self_model回答" → 学会用自身数据
Round 2: "读日志" → 发现不会用工具
Round 3: "glob搜索" → ToolOrchestrator接入网关
Round 4: "self_model关系" → 发现宪法没注入
Round 5: "先读再答" → 它在表演不是执行
Round 6-7: 列目录/自检 → ToolOrchestrator被Qwen截断
Round 8: 重排route() → 工具在Qwen之前
Round 9: 终极根因 → Any没import + 正则转义 + BOM编码
```

### 终极根因 (ToolOrchestrator返回None)

三个独立bug, 症状相同:
1. Any没import → run_direct()在import阶段崩溃 → except吞掉
2. 正则转义被多次编辑搞坏 → re.findall()匹配不到路径
3. SOUL.md有UTF-8 BOM字符 → readfile打印崩溃

### 架构原则 (今天确立)

1. Qwen=语言输出层, 不参与决策
2. 不硬编码限制, 从ToolLearningLoop经验中学习边界
3. 旧模块保留检测能力, 新模块替换执行能力
4. 螺旋是推理引擎, 不是过滤器
5. 不要裸except:pass, 至少打日志

### 删除清单
- research_engine/ (3文件, 48KB) — 僵尸, 0活动
- neural/wm_v2/ (16文件, 208KB) — 已删SpiralDecoder
- gateway SpiralDecoder引用 (40行)

### 待下次
- constitution/SOUL注入到Qwen聊天上下文
- ToolLearningLoop积累30条 → 自动LoRA微调
- ScenarioGenerator降低频率验证
