# Nexus — 架构总图
#
# 设计原则：每个模块一个目录，一个接口，一个职责。
# 模块间通过 EventBus 通信，不直接 import。
# 断了一个模块不影响其他模块运行。

## 模块清单（10个核心模块）

### 1. core/ — 身份权重核心（大脑）
- identity_core.py      # 可训练的神经身份层
    └── 职责：我是谁、用户是谁、现在该做什么
    └── 输入：Constitution + SOUL + 记忆摘要 + 当前上下文
    └── 输出：调度决策（调哪个模块、怎么组合）
- scheduler.py           # 任务调度器
- constitution.py        # Constitution A0-A5 约束加载

### 2. models/ — 模型推理（大脑皮层）
- loader.py              # Qwen2-VL-2B/4B 本地加载
- infer.py               # 推理接口（统一文本/图片/代码输入）
- swap.py                # 模型热切换（2B↔4B）
    └── 状态：已有模型文件，已有加载代码

### 3. memory/ — 五层记忆（记忆系统）
- short_term.py          # 短期：当前会话窗口（内存）
- working.py             # 工作：任务状态+投机预览+技能栈
- long_term.py           # 长期：文件持久化 YAML frontmatter + Markdown
- summary.py             # 摘要：四级压缩的结构化摘要
- checkpoint.py          # 断点：resume恢复，关了重开不丢状态
    └── 状态：三层已有基础，需升级为五层

### 4. knowledge/ — 知识系统（四件套协作）
- evokg.py               # EvoKG：Neo4j 知识图谱
- experience_bank.py     # ExperienceBank：SQLite 经验存储
- chromadb_client.py     # ChromaDB：向量语义检索
    └── 状态：Nexus 已有代码，需文档化接口

### 5. skills/ — 技能商店
- registry.py            # 技能注册/发现/加载
- sandbox.py             # 技能执行沙箱
- marketplace.py         # Git-based 技能市场
- skill_protocol.py      # 技能标准接口（Zod schema + 权限 + execute）
    └── 状态：需开发，参考 Claude Code 插件系统 + Grok Build marketplace

### 6. voice/ — 语音交互
- stt.py                 # Whisper：语音→文字
- tts.py                 # Piper：文字→语音
- pipeline.py            # 语音管线编排
    └── 状态：Nexus 已有模型文件，需写加载代码

### 7. bridge/ — 通信桥
- feishu.py              # 飞书双向通信（接收+发送）
- llm_api.py             # 外部大模型 API 接口（Claude/DeepSeek/蒸馏）
    └── 状态：单向已通(push)，待双向 + 蒸馏

### 8. learner/ — 自主学习引擎
- auto_learner.py        # 发现不足→搜索→消化→微调
- news_scanner.py        # 每日新闻/论文/政策扫描
- distill.py             # 大模型对话蒸馏→本地 LoRA
- doc_ingest.py          # 个人资料喂养（PDF/Word/PPT/图片OCR）
    └── 状态：需开发

### 9. user/ — 多用户管理
- profile.py             # 用户档案（职业/偏好/风格）
- lora_manager.py        # LoRA adapter 加载/切换/训练
- isolation.py           # 多用户隔离（记忆/ChromaDB/认知层分离）
    └── 状态：需开发

### 10. recovery/ — 七层自愈
- circuit_breaker.py     # 熔断器（外部API调用保护）
- retry.py               # 指数退避重试
- fallback.py            # 模型降级（4B→2B/云端→本地）
- compaction.py          # 上下文压缩（防溢出）
- checkpoint_recovery.py # 崩溃恢复
    └── 状态：需开发

## 铁律一：零外部依赖（张凯确立 2026-07-17）

新 Nexus 是完全独立的系统。不依赖任何第三方服务：
- ❌ 不用 Neo4j → 纯 Python 实现图谱
- ❌ 不用 ChromaDB → numpy 向量索引
- ❌ 不用 LM Studio → transformers 直接加载
- ❌ 不用 Docker → 纯 Python 沙箱
- ✅ 只依赖：Python 标准库 + transformers + numpy + torch

## 通信规则（铁律）

```
✅ 模块间通信：统一走 EventBus 发事件
   event_bus.publish('memory.updated', {...})
   event_bus.subscribe('memory.updated', handler)

❌ 禁止跨模块直接 import
   # BAD:  from memory.short_term import get_context
   # GOOD: event_bus.publish('context.needed', {...})

✅ 每个模块一个公开接口文件 __init__.py
   外部只能 import 模块，不能 import 内部文件

✅ 模块挂了自己降级，不影响其他
   Qwen崩了 → fallback.py 切2B兜底 → 其他模块继续
```

## 启动流程

```
1. constitution.py 加载 A0-A5
2. identity_core.py 初始化身份权重
3. models/loader.py 加载 Qwen
4. memory/checkpoint.py 恢复上次状态
5. bridge/feishu.py 连接飞书
6. skills/registry.py 加载已安装技能
7. scheduler.py 启动定时任务
8. → 进入主循环，等待用户输入
```

## 禁止出现的情况（Nexus 的教训）

- ❌ 一个模块 import 另一个模块的内部文件
- ❌ 全局变量跨模块共享状态
- ❌ 模块启动顺序互相依赖（A 等 B，B 等 C，C 等 A）
- ❌ 一个模块挂了拖死全部
- ❌ 没有日志、没有状态、不知道断了哪根线

## 设计参考来源

### graph-rag-agent（已研究）
- 多智能体编排：Planner(规划)→Executor(执行)→Reporter(报告)
- 缓存管理：内存/磁盘/混合三种后端
- 社区检测：Leiden算法做知识聚类
- 采纳：Agent 基类设计 + 规划-执行-报告模式

### Claude Code 源码（已研究）
- 协调器：Research→Synthesis→Implementation→Verification
- 五层记忆：短期/工作/长期/摘要/Checkpoint
- 采纳：记忆分层 + 投机执行

### Grok Build（已研究）
- dream 蒸馏：时间+会话数双重门控
- 插件市场：Git-based 分发 + install_resolve
- 采纳：夜间记忆蒸馏 + 技能安装流程

### 立项书 PROJECT_NEXUS.md
- 完整产品定义和模块设计
- 所有决策的推导记录
