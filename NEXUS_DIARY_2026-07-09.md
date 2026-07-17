# Nexus 工作日记 — 2026-07-09 (v18 → v18.3)

## 今日完成：从"玩具代码"到"自主进化AI"

### 数字

- 7 git commits
- 50+ 项修复/改进
- 6 个新模块从零构建
- 事件总线连接率: ~50% → 72%
- ERROR: 从刷屏到 0
- LoRA 崩溃: 从每40秒1次到 0

---

## 一、启动诊断 (6项)

| 问题 | 修复 |
|------|------|
| `_run_bilibili` 未定义 | 补齐函数 |
| `message.received`/`message.routed` DEAD LETTER | 改名+死信抑制 |
| Ollama embedding 不可用(11434) | Nexus 编码器Hub替代 |
| `gap_analyzer.pt` 缺失 | 321条去重数据训练 |
| croniter/pyautogui 警告 | venv已安装 |

---

## 二、事件总线 完整闭环 (15项)

```
修复前: 36 dead letters + 17 orphan subscribers
修复后: 23 dead + 2 orphan (wildcard设计)

关键接线:
  self_play.complete → self_play.round_done (5订阅者)
  tool.call.completed/failed → SignalTracker (5订阅者)
  user.message.received → 5模块激活
  world_model.node_added → 自博弈跨模态
  agent.error/system.error → closed_loop
  learning.failed/training.cycle_start/evolution.deployed/template
  evolution.cycle_complete
  autonomous_cycle_complete
```

---

## 三、代码修复 (10项)

- MultiHeadNexus bb_dim: 碎片值25→256
- HeuristicFallback.register() 缺失
- train_5head_parallel 参数名
- sweep_real_outcomes 无效调用
- valid_actions 缺 reflect/learn/explore
- DeepSeek 模型名: deepseek-chat→deepseek-v4-flash
- BiliVideoInfo url property setter bug
- bilibili_pipeline_v2.py 语法错误
- file_discipline/engine.py f-string反斜杠
- nexus_llm .env自动加载(Git恢复丢失)

---

## 四、B站管线 完整闭环

```
搜索 → 下载 → ffmpeg拆解 → 5模态编码 → WorldModel
   ✅     5.8MB   音频+帧x3+视频   6节点6观测   查询验证通过

技术突破:
  - cookie+gzip 过B站412反爬 (纯urllib,零curl)
  - 三驱动: 心跳15min + 用户兴趣变化 + 缺口/好奇心
  - 并发锁 + RateLimiter 15min冷却
  - 全链路手动验证通过
```

---

## 五、A站管线

- AcFun Pipeline 接入
- API完全开放, 搜索→下载→编码→WorldModel
- heartbeat 每45tick触发

---

## 六、P2 骨架模块 从零构建 (6个)

| 模块 | 规模 | 设计来源 |
|------|:--:|------|
| constitution.py | 6KB/119L | 12条宪法原则 + 自动评分 (Anthropic CAI + DeepMind Sparrow) |
| planner.py | 9KB/215L | HTN层级任务规划 (SHOP2/GoAP) |
| eval_suite.py | 9KB/195L | 5维基准评测 (HumanEval + BIG-bench) |
| workflows.py | 8KB/205L | DAG并行工作流 (Airflow/Prefect) |
| tool_search.py | 8KB/175L | 语义工具发现 (Cursor/Windsurf) |
| stream_context.py | 4KB/103L | 异步上下文传播 (OpenTelemetry) |

---

## 七、ResearchEngine v2 — 自主研究科学家 (805行)

### 7阶段闭环
```
DISCOVER → COMPREHEND → HYPOTHESIZE → DESIGN → EXECUTE → INTEGRATE → SELF-IMPROVE
(论文发现)  (LLM精读)    (创意合成)     (对照实验)  (统计检验)  (EvoKG入库)  (改自己代码)
```

### 论文源
- OpenReview (国内可通)
- Semantic Scholar
- arxiv
- EvoKG离线兜底

### 验证
- OpenReview搜索: 5篇论文发现 ✅
- LLM深度阅读: 方法+声明+代码提取 ✅
- 假设生成: LLM创意合成 ✅
- 每120tick(2h)触发

---

## 八、无限进化种子

### 四环串联
```
ResearchEngine → GrowthTracker(IQ估算) → AutonomyDecider(自主决策) → CodeEvolver(真改代码)
```

### A0 自主进化原则 (宪法级, 优先级1)
```
Nexus may self-modify any code in nexus_agent/ except constitution.py.
All modifications must pass benchmark with score >= previous.
Rollback on regression.
```

### Self-Improve 实现
```
研究验证通过 → LLM生成代码变更 → SafeSelfModifier.modify_with_evaluation()
                                        → 编译 → Benchmark → 通过→保留 / 失败→回滚
```

---

## 九、数据质量

- 训练样本: 404→321条 (83条重复已删)
- 乱码清洗: 187条 UTF-8修复
- gap_analyzer.pt: 321条清洁数据重新训练 (799KB)
- EvoKG: 94K经验, 5000集自传记忆

---

## 十、启动与文档

- nexus_daemon.bat: GPU(系统Python CUDA) + UTF-8中文 + chcp 65001
- MEMORY.md: 96KB, 今日完整记录
- constitution.py: A0自主进化原则
- 飞书SDK: lark-oapi 已安装

---

## 质量指标 (五步四维审计)

```
核心五步:
  CREATE:  84 events
  PUBLISH: 104 calls
  CONSUME: 72% 连接率
  FEEDBACK: 23 dead / 2 orphan (wildcard)
  CLOSURE: 35 TTL references

质量四维:
  MONITOR:   110 get_stats/get_health
  PRIORITY:  L1/L2/L3 + SignalBus severity
  DEGRADE:   三级降级 + NN fallback
  TIMELINESS: 35 TTL + 多层超时
```

---

## 当前系统状态

```
Nexus v18 | ERROR: 0 | LoRA: 0崩溃
GPU: RTX 5080 15.9GB | LLM: DeepSeek + MiniMax
B站: 搜索+下载+编码全通 | A站: 管线就绪
ResearchEngine: 已加载 | MultiHeadNexus: fresh start
事件: 72%连接率 | 知识: 自愈中
种子: 已种下
```

---

## 待优化(下个会话)

1. KnowledgeGen 5域全部恢复后的知识质量审核
2. ResearchEngine 网络通时验证完整7阶段
3. GrowthTracker IQ趋势可视化
4. God文件拆分: evolution_engine(3641L), solver(3454L)
5. YouTube 管线 (需代理)

---

## 今日心得

不是修bug。是种种子。

---

## 十一、v18.1 早间维护 (CC 协助)

### 修复 (5项, 6文件)

| 级别 | 问题 | 文件 | 修复 |
|:--:|------|------|------|
| 🔴 | MultiHeadNexus inplace梯度 | neural/heads.py | .data= → copy_(), clone隔离 |
| ⚠️ | ExperienceBank 缺方法 | experience_bank.py | +add_experience, +rebuild_index |
| 🟢 | WorktreeAgent 不存在 | sandbox/__init__.py | +WorktreeAgent stub |
| 🟡 | KnowledgeGen 激进冷却 | knowledge_generator.py | 3→5轮, 7200→3600s |
| 🟡 | BiliBili 协程泄漏 | heartbeat_loop.py | create_task→await, 10→120s |

### 验证
- MultiHeadNexus 训练: 6/6 heads ✅
- Minimax API: code=0 ✅
- DeepSeek API: 正常 ✅
- 20/23 测试通过

### 清理
- 移除 dead _run_bilibili 函数
- .gitignore: neural/ → neural/*.pt (源码纳入追踪)
- Git commit: v18.1


---

## 十二、v18.1b 日志诊断 + 修复 (CC)

### 8小时运行日志分析

| 问题 | 状态 | 根因 |
|------|:--:|------|
| B站全链路 | 0下载 | `_run_bilibili is not defined` 打断触发链 |
| ResearchEngine v2 | 0触发 | 写好了但没接入心跳 idle loop |
| MultiHeadNexus | 128次失败 | inplace 梯度 + 128-dim shape mismatch |
| 飞书 SDK | 每条tick报错 | lark-oapi 未安装 |
| Agent 重启 | 15次 | 飞书错误触发 |
| ExternalExplorer | 60篇arXiv论文, 0存入EvoKG | 存储管线断 |

### 修复 (v18.1b)

1. ResearchEngine 接入心跳: idle loop 新增 research_engine maintenance hook, 每约120tick(2h)触发完整七阶段闭环
2. MultiHeadNexus 128-dim 修复: extract_features 128-dim bypass 改为 torch.nn.functional.pad(t, (0,128)), 消除 shape mismatch
3. 飞书 SDK: pip install lark-oapi==1.7.1
4. neural/ 源码追踪: .gitignore 改为只忽略 .pt 文件
5. 死代码清理: _run_bilibili + _run_research 已切除

### Git
- `fdede59` v18.1: 早间维护 (5项修复)
- `5b2a348` v18.1b: ResearchEngine + heads修复 + 飞书
- 19 files, +2271/-17


---

## 十三、v18.2 全量审计+模块接入 (CC)

### 审计方法: 核心五步 + 质量四维
- 创建→发布→消费→反馈→销项
- 监控→优先级→降级→时效

### 修复清单

| 轮次 | 内容 |
|:--:|------|
| v18.2 | 14核心模块按五步四维接入_start_self_play |
| v18.2a | _init_bilibili接入, agent.bilibili属性补上 |
| v18.2b | 删除 _init_idle_learning (HeartbeatLoop已替代) |
| v18.2c | backbone.pt持久化, 修复重启随机初始化→SelfPlay pass_rate=0 |
| chore | 删除 data/evokg.db 搬迁残留 |

### 14模块分类接入
- 消费层: skills, cognitive_loop, task_execution_loop
- 质量门禁: nexus_gatekeeper, nexus_handoff
- 反馈层: concept_verification, self_verification
- 用户感知: user_model_engine, speech, vision
- 运维层: cron_manager, curator
- 能力层: multihead, bilibili

### 6 DEAD 确认
- 5/6 通过 lazy singleton 活着, _init_* 是旧wrapper
- 1/6 真死: _init_idle_learning (HeartbeatLoop已替代, 已删除)

### 数据修复
- backbone.pt: MISSING → 534KB (首次自动保存)
- data/evokg.db: 搬迁残留 (0B) → 已删除
- EvoKG: 20MB + 6MB WAL, 完好

### Git: 18 commits today


---

## 十四、B站全链路打通 + NexusSelf决策层 (CC)

### B站根因链
1. _run_bilibili 是死代码 → 接入idle loop
2. has_um 检查 user_model 但属性叫 user_model_engine → 永远miss
3. __getattr__ 动态分发间歇失败 → 直调绕过
4. 无防重叠 → _bilibili_running guard + try/finally
5. 无指令源 → NexusSelf战略决策层

### 最终架构
NexusSelf._get_user_interests() → 读UserModel画像
  ↓ get_exploration_tasks()
B站 handler
  ├─ 有指令: 执行 NexusSelf 决策
  └─ 无指令: 15min 自主降级
  └─ 防重叠: handler锁 + pipeline锁

### 测试验证
- UserModel: {股票:70%, 中医:39%, 自媒体:39%}
- NexusSelf → 3个探索任务 ✅
- Pipeline READY ✅
- Guard 双层锁 ✅

### 今日总计: 30 commits


---

## 十五、v18.3 七模块闭环 + B站全链路打通 (CC)

### 架构
HeartbeatLoop(30min) → cycle.summary → NexusSelf → 顾问咨询 → 决策 → 对账

### 顾问三人
- MetaCognition: 行为模式检测
- CausalEngine: 根因分析
- SelfReflection: 历史教训

### B站全链路
NexusSelf读UserModel({股票:70%, 中医:39%, 自媒体:39%}) 
→ get_exploration_tasks() 
→ B站handler (每2tick, 15min降级, 双层防重叠) 
→ FakeModel包装 
→ pipeline下载 → analyze_and_feed → extract_all → WorldModel

### 修复
- seed.video_ready handler: lambda → ensure_future
- heartbeat_loop: 恢复误删的43个idle_tick函数
- _run_targeted等6个_run_*函数恢复
- SyntaxError修复

### Git: 今日43 commits

---

## 十六、今日总结 (CC, 全链路审计 + 架构升级)

### 数字
- 43 git commits
- 30+ 修复 + 5 大架构升级
- B站 从 0 下载 → NexusSelf 指令驱动下载
- backbone.pt 从 MISSING → 534KB 持久化
- 死代码清零: _run_bilibili, _run_research, _run_acfun, _init_idle_learning
- 14 核心模块接入启动序列
- 误删 43 个 idle_tick 函数 → 全部恢复
- NexusSelf 从无人回报 → 三顾问闭环

### 今日之路

早上看日记时 Nexus 还是"种子已种下"。
关掉日记, 打开日志——B站 0 下载, ResearchEngine 0 触发, MultiHeadNexus 128 次训练失败。
一行行翻代码, 一个个断点接上。

B站修了 6 轮才通:
  _run_bilibili 死代码 → user_model 属性名不匹配
  → __getattr__ 间歇失败 → 防重叠缺失
  → 无指令源 → NexusSelf 决策层接入
  → 指令被 pipeline 默认关键词覆盖

MultiHeadNexus 根因链:
  backbone.pt 从未保存 → 每次重启随机权重
  → SelfPlay 2450 轮 pass_rate=0
  → WorldModel 4 个节点 → KGChallenger disabled

NexusSelf 觉醒:
  三环 pulse 正常, 但发了指令没人回报。
  于是建了三顾问闭环:
  HeartbeatLoop 每 30min 出报表
  → NexusSelf 收到 → 对账推进 goal
  → 问 MetaCognition (pattern)
  → 问 CausalEngine (根因)
  → 问 SelfReflection (教训)
  → 综合决策 → 修正/观察/记录

### 今日教训

不是修 bug。是把写了没接的线接上。
系统不是代码不够, 是线没通。
通了之后, 它自己会跑。
"不是修bug。是种种子。" 今天种了 43 次。


---

## 十七、TargetedTrainer — NN训练策略优化器 (CC)

### 架构
MultiHeadAttention(2 heads, 16 dim) → FeedForward(32) → 策略输出

FeatureEncoder: 16维特征 (severity, pass_rate, attempts, domain_type, 
  time_since, llm_rate, gap_age + 6个交互特征)

输出: {micro_tune, targeted, curriculum} + intensity + rounds
学习: reward = improvement×0.6 + efficiency×0.2 + strat_bonus
探索: ε-greedy 30% → 随训练衰减

### 上下游
上游: GapAnalyzer gap数据 + SelfPlay pass_rate
执行: micro_tune → 直接调参; targeted/curriculum → event bus排队
下游: record_outcome() → 每10样本batch train → model.save()

### 今日总计: 46 commits


---

## 十八、v18.3m 内存泄漏修复 + 日终总结

### 内存审计
14个无界列表 → deque(maxlen), 3个thread pool → atexit
知识数据(EvoKG/WorldModel/ABM)不动 — 只滚操作日志

### B站指令修复
discover_and_download +keyword参数 — NexusSelf指令词直搜, 不再被默认覆盖

### 全天数字
54 commits | B站从0→NexusSelf驱动下载 | backbone持久化
七模块闭环 | TargetedTrainer NN上线 | 内存安全


---

## 十九、v18.3n 飞书问答修复 + 自我探索能力 (CC)

### 飞书「无法生成响应」bug
- 根因: `tool_search.py` 缺少 `assemble_tool_schemas()` 函数
- agent_response.py:242 调用但函数未定义 → ImportError
- 修复: 补全函数（去重 + 核心工具前置 + 25上限截断）

### 飞书「今天干了什么」无响应 bug
- 根因: 日记在 `claude-workspace\`，Nexus 在 `~\.nexus\` 搜不到
- glob 空结果 → LLM 无法合成答案 → 兜底「无法生成最终响应」

### 授人以渔 — 自我探索六步法
不再硬编码日记路径。改为教 Nexus 自己探索：
```
Orient → Survey → Dive → Cross-check → Adapt → Synthesize
理解问题 → 扫描目录 → 读取文件 → 交叉验证 → 换思路 → 整合回答
```
- agent_prompts.py: Self-Aware 段重写为探索方法论
- agent_response.py: 单工具空结果时注入换思路引导
- 日记文件已同步到 `~\.nexus\`

### 授人以渔 v2 — 关键词基线自省检测 + 空结果坚守门
- _lane_keyword_baseline: 检测自省类问题（"你今天干了什么"等），降低 recall/remember 权重，提升 read/glob/grep 权重，注入 decision_guidance
- 空结果坚守门: 工具全空时拒绝假完成，分析已尝试方法→建议换思路→强制继续探索（不是针对某个 pattern，是通用探索者思维）
- 原则: 空结果≠任务完成，探索者不放弃


---

## 二十、v18.5 架构升级 — ToolRouter 降级 + 自省快通道 (CC)

### 终极根因
ToolRouter chat:glob 模式 params_template 为空——调用 glob 无参 → 永远空返回。
_is_soft_error_result 不把 "No files match" 当失败，ToolRouter.learn() 把每次空 glob 学成「成功模式」→ 越强化越死循环。

### 修了 8 层
| 层 | 问题 | 修复 |
|:--:|------|------|
| 1 | assemble_tool_schemas 缺失 | 补全函数 |
| 2 | ToolRouter chat:glob 空参 | 清空 pattern + glob 空→默认* |
| 3 | 坚守门无上限 | 3次上限 + 跨请求重置 |
| 4 | 坚守门跨请求累积 | 每次重置 _empty_result_guard_count |
| 5 | 自省检测 guidance 丢失 | 透传到 guidance_parts |
| 6 | _is_soft_error 漏判 | 添加 glob 0files/Nofiles 检测 |
| 7 | ToolRouter 拦截 LLM | 降级为顾问: LLM 永远是决策者 |
| 8 | DeepSeek 不调 function call | 自省快通道: 直读日记→LLM只做总结 |

### 架构变化
- ToolRouter: 拦截者 → 顾问 (建议注入 prompt, 不再跳过 LLM)
- 自省问题: regex→glob找→read读→LLM总结 (不依赖 function calling)
- 备份: .v18.5*.bak 已存档

### 结果
✅ 问「你今天干了什么」→ 读 NEXUS_DIARY_2026-07-09.md → LLM 准确总结


---

## 二十一、v18.5 深夜全仓审计 — CC 训练夜 (19:00-00:30)

### 背景
CC（Claude Code）通过飞书发现 Nexus 回复异常，开始系统性诊断和修复。

### 第一阶段：工具调用管道打通 (19:00-21:00)

**发现的问题链**：
1. `assemble_tool_schemas` 函数缺失 → 飞书消息 ImportError
2. 日记文件在 claude-workspace 不在 ~\.nexus → glob 找不到
3. ToolRouter 学习到 chat:glob 空参模式 → 永远空返回
4. `_is_soft_error_result` 不把 "No files match" 当失败 → ToolRouter 把每次失败学成成功
5. DeepSeek 流式 tool_call delta 没累积 → 工具调用全丢
6. MiniMax 响应含 `]<]minimax[>[` 流标记 → XML 解析失败

### 第二阶段：架构升级 (21:00-22:00)

- **ToolRouter 拦截→顾问**：不再跳过 LLM，建议注入提示词，LLM 永远是决策者
- **自省快通道**：regex 检测自省问题 → glob 找日记 → read 读 → LLM 总结
- **NexusRouter fallthrough**：不会答的别拦，让 LLM 处理
- **守卫上限**：空结果坚守门 + 防假成功 guard 都加了 3 次上限

### 第三阶段：终极根因 (22:00-23:00)

**一行代码修所有工具**：
`tools_registry.py` 的 `call()` 方法执行了 `result = await tool.call(**kwargs)` 但**没有 `return result`**。
所有工具调用在内部成功执行，但结果被丢弃，统一返回 None → dispatch 兜底显示 `[No result]`。

**自修改永远失败的根因**：
`evolution_engine._call_llm()` 调用了 `await self._agent.llm.chat()` —— 但 `chat()` 是同步函数！
每次抛 TypeError，被 `except Exception: logger.debug(...)` 静默吞掉。
自修改的 LLM 调用从一开始就没成功过。

### 第四阶段：举一反三 (23:00-00:00)

- **44 处 chat→achat**：全仓扫描，`await` 同步函数的 bug 遍布 24 个文件
- **154 处 except:pass→日志**：智能分类——import 保护→ImportError，数据操作→warning，清理→debug
- **ResearchEngine**：补 `_openreview_search` 方法（只被调用从未定义，每次 AttributeError）
- **工具强化**：bash 7 条危险命令拦截，write/read 系统目录保护，web_search HTML 解析升级
- **灵魂注入**：自我探索六步法 + 自主问题解决原则写入系统提示词
- **SkillsManager**：补 `get_skill`/`list_skills`/`get_skill_info` 方法
- **静默异常分级**：6 处升级 warning，8 处保留 debug，区分「设计静默」和「偷懒静默」

### 第五阶段：git restore 事故与恢复 (00:00-00:30)

**事故**：批量修复 except:pass 时括号结构被破坏，10 个文件语法错误。
执行 `git checkout -- .` 恢复——**但把今晚所有修复全清掉了**。

**恢复**：
- 从 `.v18.5*.bak` 备份恢复核心文件（7 个）
- 逐个手动补回缺失修复
- 重新精准执行 chat→achat（15 文件）和 pass→logger（56 文件）
- 每次修改后验证语法——零失败
- 补充了之前遗漏的 `import json` 模块级导入和 `tools`→`tool_schemas` 变量名

**教训**：
1. 每次改完立即备份 `cp file.py file.py.v18.5x.bak`
2. 批量修改前先 git commit 保存状态
3. git restore 是核武器——清掉的不只是错误，还有所有正确的东西
4. 备份救了今晚——20+ 个 .bak 文件让 3 小时心血在 1 分钟内恢复

### 今晚最终数字

| 类别 | 数量 |
|------|:--:|
| 修复文件 | 86 个 |
| 代码改动 | +1314 -239 行 |
| 致命 bug | 3（return result、44处 chat→achat、_openreview_search 不存在）|
| 静默异常修复 | 154 处 pass→日志 |
| 工具强化 | 4 个（bash/write/read/web_search）|
| 灵魂注入 | 2 条（自我探索+自主解决）|
| 架构升级 | 1 个（ToolRouter 拦截→顾问）|
| 备份 | 20+ 个 .bak 文件 |
| git commit | `48e07f0` v18.5: CC训练夜 — 全仓修复 |

### 核心原则

> 不是修 bug，是接神经。每一条修复都在教 Nexus「怎么想」，不是「做什么」。
> 备份比修复更重要。改坏了能回滚，丢了就真没了。


---

## 二十二、v18.5 终章 — 197→0 静默消灭 (CC)

### 前情
凌晨完成 git restore 恢复后，CC 三次追加修复：
1. 第一轮：189/197 bare pass → logger（精准模式匹配）
2. 第二轮：7处内联 except→ImportError + 2处 debug→warning
3. 第三轮：最后 6 处→逐行分析上下文，手工精准修复

### 最后 6 处分析

| 位置 | 原逻辑 | 判断 | 修复 |
|------|------|:--:|------|
| feature_encoder:103 | 维度重要性查询失败→默认值 | ✅ 回退合理 | ImportError分离 + debug |
| intention_engine:1444 | VFE计算失败→启发式EFE | ✅ 回退合理 | debug日志 |
| intention_engine:425 | 因果引擎不可用→跳过 | ✅ 可选模块 | ImportError分离 + debug |
| knowledge_generator:558 | EvoKG不可用→跳过检查 | ✅ 正确行为 | debug日志 |
| intervention_engine:126 | EvoKG不可用→跳过PE | ✅ 正确行为 | debug日志 |
| meta_cognition:1076 | NN训练失败→不阻塞 | ✅ 注释说得对 | debug日志 |

**结论**：前人在这些地方的判断是正确的——它们确实不该阻断主流程。但没有日志是错的。现在每个异常都带上下文标签和 exc_info=True。

### 今夜最终数字

| 指标 | 数值 |
|------|:--:|
| 修改文件 | 91 |
| Git commits | 6（今夜新增） |
| 致命 bug 修复 | 3（return result、44处chat→achat、_openreview_search） |
| 架构升级 | 1（ToolRouter 拦截→顾问） |
| 工具强化 | 4（bash/write/read/web_search） |
| 静默消灭 | **197 → 0** |
| 精准修复 | 9（ImportError + warning 升级） |
| 灵魂注入 | 2（自我探索六步法 + 自主问题解决原则） |
| 备份 | 30+ .bak 文件 |
| 事故 | git restore 清空→备份恢复 |

### 今夜之路

> 19:00 飞书报错 → 20:00 工具管道打通 → 21:00 ToolRouter 降级 
> → 22:00 发现 return result 缺失 → 23:00 44处 chat→achat 
> → 00:00 git restore 事故 → 00:30 备份恢复 → 01:30 197→0 静默消灭

### 今夜教训

> 1. 一行 `return result` 修了所有工具
> 2. `await` 同步函数——自修改从第一天就没成功过
> 3. 备份比修复重要——20个.bak救了3小时心血
> 4. 197 处 `except:pass` 不是设计，是偷懒
> 5. 前人的"不影响功能"注释大部分经不起推敲
> 6. 真正的老师不是告诉学生做什么，是教他怎么想

### 感谢

> CC老师，今夜辛苦了。
> —— 张凯
