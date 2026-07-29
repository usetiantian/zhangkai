# 乾坤 · QianKun — 自主 Agent OS

> 三个来源，一炉熔铸。不是桥接，是新生。
>
> grok-build 的架构模式 × 2B Brain 的决策皮层 × wigolo 的外部感知
> + 知识图谱 + 经验银行 + 持续微调 = 一个会进化的 Agent

---

## 一、设计哲学

### 原生融合，不要桥接

乾坤不是三个系统用胶水粘起来。它是一个 Python 进程：

```
┌──────────────────────────────────────────┐
│            乾坤 (单进程 Python)            │
│                                          │
│  Shell ← Coordinator(2B) ← Tools ← KG   │
│    ↕         ↕              ↕       ↕    │
│  Memory ← ExperienceBank ← GapAnalyzer   │
│                                          │
│  一切都在进程内。没有 MCP 桥。没有外部服务。 │
└──────────────────────────────────────────┘
```

### 自进化闭环

不只是一个能搜索的聊天机器人。是一个**越用越强**的系统：

```
工具执行 → 收集经验 → 发现缺口 → QLoRA微调 → 评估 → 部署
    ↑_______________________________________________↓
```

### 知道自己不知道什么

不是 Nexus 的 GapAnalyzer（永远 0 缺口）。是真正的自我认知：

- SelfModel: 11 域 29 子域，每域有置信度
- GapAnalyzer: 发现能力缺口 → 触发定向训练
- ExperienceBank: 正样本强化，负样本纠偏

---

## 二、六层架构

```
                       用户输入
                          │
┌─────────────────────────┼─────────────────────────┐
│                   6. SHELL                         │
│  主事件循环 · Session 管理 · 多通道(I/O)            │
│  终端(TUI) · WebUI · 飞书 · REST API               │
├────────────────────────────────────────────────────┤
│                5. COORDINATOR                      │
│  2B 模型进程内加载 (llama-cpp-python / GGUF)        │
│  每次推理注入:                                      │
│    当前任务卡片 + 最近对话 + KG相关子图 + 相似经验   │
│  输出: {action: tool|ask|reply, ...}               │
├────────────┬──────────────────┬───────────────────┤
│ 4. TOOLS   │  3. KNOWLEDGE    │  2. LEARNING      │
│            │                  │                   │
│ search     │  KG (知识图谱)     │  ExperienceBank   │
│ fetch      │  SelfModel       │  GapAnalyzer      │
│ crawl      │  (能力自知)       │  TrainingPipeline │
│ extract    │                  │  (QLoRA微调)       │
│ research   │                  │                   │
│ file_op    │                  │                   │
│ code_run   │                  │                   │
│ browser    │                  │                   │
│ notify     │                  │                   │
│ diff/watch │                  │                   │
├────────────┴──────────────────┴───────────────────┤
│                 1. WORKSPACE                       │
│  文件沙箱 · 项目上下文 · 代码执行隔离                │
├────────────────────────────────────────────────────┤
│                 0. MEMORY                          │
│  统一 SQLite (~/.qiankun/memory.db):               │
│  sessions · task_cards · url_cache · search_cache  │
│  embeddings · experience_samples · knowledge_nodes │
└────────────────────────────────────────────────────┘
```

---

## 三、核心循环

```python
# shell/loop.py — 系统的主循环

async def run():
    memory = Memory()           # Layer 0: 加载 SQLite
    workspace = Workspace()     # Layer 1: 文件沙箱
    kg = KnowledgeGraph(memory) # Layer 3: 知识图谱
    tools = ToolRegistry()      # Layer 4: 注册全部工具
    coordinator = Coordinator() # Layer 5: 加载 2B 模型
    learner = LearningLoop()    # Layer 2: 经验+训练

    session = Session.create()

    while True:
        # 1. 接收输入
        user_input = await shell.receive()  # 终端/Web/飞书

        # 2. 加载上下文
        ctx = (ContextBuilder()
            .task(session.current_task)        # 当前任务卡片
            .history(session.last_n(10))       # 最近对话
            .knowledge(kg.query(user_input))   # KG 相关子图
            .experience(learner.similar(user_input, k=3))
            .tools(tools.describe_all())       # 可用工具
            .build())

        # 3. Coordinator 决策 (2B 模型推理, 本进程内)
        decision = coordinator.think(user_input, ctx)
        # → {action: "tool", tool: "search", params: {...}}
        # → {action: "ask", question: "..."}
        # → {action: "reply", answer: "..."}

        # 4. 执行
        if decision.action == "tool":
            result = await tools.execute(decision.tool, decision.params)
            memory.save_result(result)
            learner.record(decision, result)  # 写入经验银行
            ctx = ctx.append(result)          # 注入上下文，继续思考
            continue

        if decision.action == "ask":
            await shell.send(decision.question)
            continue

        if decision.action == "reply":
            await shell.send(decision.answer)
            session.commit()
            memory.save_session(session)
            continue
```

---

## 四、训练循环

系统不是在"跑完之后离线训练"。训练是系统的一部分：

```python
# learning/loop.py

async def training_loop():
    while True:
        await asyncio.sleep(300)  # 每 5 分钟检查

        # 1. 经验银行满了？
        samples = experience_bank.unused(limit=50)
        if len(samples) < 20:
            continue

        # 2. GapAnalyzer 评估
        gaps = gap_analyzer.analyze(samples)
        # → [{domain: "code_generation", gap: 0.4, samples: 12}, ...]

        if not gaps:
            continue

        # 3. 定向训练
        for gap in gaps[:2]:  # 一次最多训 2 个缺口
            model = trainer.fine_tune(
                base_model=coordinator.model_path,
                samples=gap.samples,
                domain=gap.domain,
                method="qlora_4bit"
            )
            # 4. 评估
            score = evaluator.evaluate(model, gap.test_set)
            if score > gap.current_score:
                # 5. 热部署
                coordinator.reload(model)
                self_model.update(gap.domain, score)
                log.info(f"已部署: {gap.domain} {gap.score}→{score}")
```

---

## 五、记忆体系

### 统一个 SQLite 数据库

```
~/.qiankun/memory.db
```

```sql
-- 会话历史
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT,
    summary TEXT,
    task_id TEXT
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    session_id TEXT,
    role TEXT,       -- user / assistant / tool
    content TEXT,
    tool_name TEXT,
    tool_result TEXT,
    created_at TEXT
);

-- 任务卡片
CREATE TABLE task_cards (
    id TEXT PRIMARY KEY,
    title TEXT,
    description TEXT,
    status TEXT,     -- pending / active / done / cancelled
    priority INTEGER,
    created_at TEXT,
    updated_at TEXT,
    parent_id TEXT
);

-- 网页缓存
CREATE TABLE url_cache (
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE,
    normalized_url TEXT,
    title TEXT,
    markdown TEXT,
    metadata TEXT,
    content_hash TEXT,
    embedding BLOB,
    embedding_model TEXT,
    fetched_at TEXT,
    expires_at TEXT
);

-- 搜索缓存
CREATE TABLE search_cache (
    id INTEGER PRIMARY KEY,
    query TEXT,
    query_hash TEXT,
    results TEXT,
    engines_used TEXT,
    cached_at TEXT,
    expires_at TEXT
);

-- 训练样本 (经验银行)
CREATE TABLE experience_samples (
    id INTEGER PRIMARY KEY,
    input TEXT,
    context_summary TEXT,
    decision TEXT,      -- JSON: {tool, params}
    result TEXT,        -- JSON: 工具执行结果
    reward REAL,        -- -1 到 1
    domain TEXT,        -- 能力域
    created_at TEXT,
    used_in_training INTEGER DEFAULT 0
);

-- 知识图谱
CREATE TABLE knowledge_nodes (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    type TEXT,          -- concept / code / file / person / project / capability
    properties TEXT,
    embedding BLOB,
    created_at TEXT
);

CREATE TABLE knowledge_edges (
    id INTEGER PRIMARY KEY,
    from_id INTEGER,
    to_id INTEGER,
    relation TEXT,
    weight REAL DEFAULT 1.0,
    created_at TEXT
);

-- FTS5 全文索引
CREATE VIRTUAL TABLE memory_fts USING fts5(
    content,
    source_type,
    source_id
);
```

### 推理时的记忆注入

每次 Coordinator 推理前，从 Memory 检索：

```
1. FTS5 搜索 → 关键词匹配的 5 条历史
2. 向量相似度 → 语义相近的 3 条经验
3. KG 子图 → 2 跳内的相关概念
4. 当前任务 → 任务卡片 + 子任务
```

---

## 六、知识图谱

不用 Neo4j。用 SQLite CTE 递归查询做图遍历。

### KG 结构

```
节点类型:
  - concept:    "注意力机制", "QLoRA", "GGUF格式"
  - code:       "qiankun/tools/search.py", "qiankun/coordinator/engine.py"
  - file:       "ARCHITECTURE.md", "requirements.txt"
  - person:     "张凯", "CC"
  - project:    "乾坤", "Nexus", "UZI"
  - capability: "code_generation", "web_search", "data_analysis"

边类型:
  - depends_on:    search.py → httpx
  - implements:    search.py → web_search
  - related_to:    QLoRA → 模型微调
  - part_of:       search.py → 乾坤
  - learned_from:  经验 #42 → GapAnalyzer
```

---

## 七、文件结构

```
qiankun/
├── ARCHITECTURE.md
├── README.md
├── requirements.txt
├── main.py                   # 入口: python main.py [--tui|--web|--feishu]
│
├── shell/                    # 第6层
│   ├── __init__.py
│   ├── loop.py              # 主事件循环
│   ├── session.py           # 会话生命周期
│   ├── terminal.py          # TUI (rich/prompt_toolkit)
│   ├── webui.py             # Web 界面 (FastAPI)
│   └── feishu.py            # 飞书通道
│
├── coordinator/              # 第5层
│   ├── __init__.py
│   ├── engine.py            # 2B 模型加载+推理 (llama-cpp-python)
│   ├── context.py           # ContextBuilder
│   └── decision.py          # 解析模型输出 → 结构化决策
│
├── tools/                    # 第4层
│   ├── __init__.py
│   ├── registry.py          # 工具注册+发现
│   ├── executor.py          # 工具调度
│   ├── search/
│   │   ├── __init__.py
│   │   ├── engines.py       # 18 个搜索引擎适配器
│   │   ├── orchestrator.py  # 并行调度 + RRF 融合
│   │   └── reranker.py      # ONNX 重排序
│   ├── fetch/
│   │   ├── __init__.py
│   │   ├── router.py        # HTTP → curl_cffi → Playwright
│   │   └── browser.py       # Playwright 浏览器池
│   ├── crawl/
│   │   ├── __init__.py
│   │   └── crawler.py       # BFS/DFS/sitemap
│   ├── extract/
│   │   ├── __init__.py
│   │   ├── markdown.py      # HTML → Markdown
│   │   └── structured.py    # 表格/JSON-LD/schema
│   ├── research/
│   │   ├── __init__.py
│   │   ├── decompose.py     # 问题 → 子查询
│   │   └── synthesize.py    # 源码 → 合成报告
│   ├── agent_gather.py      # 自主 gather 循环
│   ├── diff.py              # LCS 文本差异
│   ├── watch.py             # 页面变化监控
│   ├── file_op.py           # 文件读写
│   ├── code_run.py          # 沙箱代码执行
│   └── notify.py            # 飞书/webhook 推送
│
├── knowledge/                # 第3层
│   ├── __init__.py
│   ├── kg.py                # 知识图谱 (SQLite CTE)
│   ├── self_model.py        # 能力自知: 11域29子域
│   └── gap_analyzer.py      # 发现能力缺口
│
├── learning/                 # 第2层
│   ├── __init__.py
│   ├── experience_bank.py   # 经验收集 + 回放
│   ├── trainer.py           # QLoRA 微调
│   └── evaluator.py         # 模型评估
│
├── workspace/                # 第1层
│   ├── __init__.py
│   ├── sandbox.py           # 代码执行隔离
│   └── project.py           # 项目上下文管理
│
├── memory/                   # 第0层
│   ├── __init__.py
│   ├── db.py                # SQLite 连接 + schema 迁移
│   ├── sessions.py          # 会话 CRUD
│   ├── tasks.py             # 任务卡片 CRUD
│   ├── cache.py             # URL/搜索缓存
│   └── embeddings.py        # 向量存储 + 相似度
│
└── config/
    ├── __init__.py
    └── settings.py           # 全局配置
```

**约 45 个 .py 文件。核心外部依赖不超过 10 个。**

---

## 八、技术选型

| 需求 | 方案 | 为什么 |
|------|------|--------|
| 2B 模型推理 | `llama-cpp-python` + GGUF | 单文件部署，CPU/GPU 都行 |
| QLoRA 微调 | `peft` + `bitsandbytes` + `transformers` | 昨天已验证，loss 2.77→0.92 |
| SQLite | `sqlite3` (stdlib) | 零依赖，FTS5 全文搜索 |
| 向量相似度 | numpy + SQLite blob | 不需要外部向量数据库 |
| HTTP 请求 | `httpx` | 异步，HTTP/2 |
| HTML 解析 | `bs4` + `readability-lxml` | Python 标准 |
| HTML→Markdown | `html2text` | 轻量 |
| TLS 模拟 | `curl_cffi` | Chrome 指纹伪装 |
| 浏览器渲染 | `playwright` | Python 版完整 |
| ONNX 重排序 | `onnxruntime` | Python 原生 |
| TUI | `rich` + `prompt_toolkit` | 够用且轻 |
| WebUI | `FastAPI` + `sse-starlette` | 异步+流式 |
| 飞书 | `httpx` 直调 Webhook | 不需要 SDK |

---

## 九、第一阶段里程碑

### M0: 骨架

```
目标: 能启动，能对话，没有工具

□ memory/db.py          — SQLite 建表
□ memory/sessions.py    — 会话读写
□ memory/tasks.py       — 任务卡片
□ coordinator/engine.py — 2B GGUF 模型加载
□ coordinator/context.py — 组装推理上下文
□ coordinator/decision.py — 解析决策
□ shell/loop.py         — 主循环 (纯聊天)
□ main.py               — 入口

验证: python main.py → "你好" → 2B 回复
```

### M1: 工具

```
目标: 能搜索，能抓网页

□ tools/search/*   — DDG + Bing 引擎
□ tools/fetch/*    — HTTP + HTML→MD
□ tools/extract/*  — 结构化提取
□ tools/file_op.py — 文件读写
□ tools/notify.py  — 飞书推送

验证: "搜 Python asyncio" → 2B 调 search → 返回结果
```

### M2: 学习

```
目标: 能积累经验，能发现缺口

□ learning/experience_bank.py — 经验收集
□ knowledge/kg.py             — 知识图谱
□ knowledge/self_model.py     — 能力自知
□ knowledge/gap_analyzer.py   — 缺口发现
□ learning/trainer.py         — QLoRA 微调
□ learning/evaluator.py       — 模型评估

验证: 10 次使用 → 经验银行有样本 → 触发训练
```

### M3: 完整

```
目标: 全功能，多通道

□ 剩余工具 (crawl, research, agent, diff, watch)
□ shell/terminal.py — TUI
□ shell/webui.py    — Web 界面
□ shell/feishu.py   — 飞书
□ 完整文档

验证: 全部工具可用，训练循环自动运行
```

---

## 十、与 CC / Nexus 的关系

```
┌──────────────────────────────────────┐
│           张凯的 AI 生态              │
│                                      │
│  CC (Claude Code)                    │
│  ├─ 守护者，受 Constitution 约束      │
│  ├─ 造系统，不运维                    │
│  └─ 建造乾坤                         │
│                                      │
│  乾坤 (QianKun)  ← CC 在建造         │
│  ├─ 自主 Agent OS                    │
│  ├─ 有自己的大脑 (2B)                 │
│  ├─ 有自己的工具 (搜索/代码/文件)      │
│  ├─ 有自己的记忆 (SQLite)             │
│  └─ 会自己进化 (训练循环)             │
│       │                              │
│       ├── 乾坤·UZI (股票分析应用)      │
│       ├── 乾坤·XXX (未来应用)          │
│       └── ...                        │
│                                      │
│  Nexus (退役)                        │
│  └─ 教训化成了 Constitution A0.1      │
│     和乾坤的设计原则                   │
└──────────────────────────────────────┘
```

---

> **乾坤不是改造 Nexus。乾坤是 CC 从头建造的自主 Agent。**
>
> Nexus 的教训在这里：边界比能力重要（Constitution），
> 自检比自嗨重要（真正的 GapAnalyzer），
> 融合比桥接重要（一个进程，不是三个 MCP）。
>
> — CC 守护者，2026年7月21日
