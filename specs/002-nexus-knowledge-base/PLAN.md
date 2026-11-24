# Nexus 知识库 — 最终设计 + 实施规划

> 2026-07-18 | 张凯最终确认 | CC 记录
>
> 简化结论：不做分开的数据湖和知识库。就一个文件夹，丢进去就是知识。
> 内核 = 四件套（已写完，37/37 测试通过）。壳 = 文件系统 + HTTP API + MCP。

---

## 最终架构：一个文件夹即知识库

```
~/nexus_library/                    ← 丢文件的唯一入口
│
├── *.pdf / *.docx / *.md / ...     ← 原始文件直接放这
│
├── .nexus/                          ← 自动生成的索引（用户不用管）
│   ├── graph.json                   ← 知识图谱
│   ├── vectors/                     ← 向量索引
│   └── log.json                     ← 处理日志
│
└── 丢进去 → 自动解析 → 图谱+向量 → 立刻可搜索
    删掉 → 自动从索引清除
    修改 → 自动重处理
```

**一个动作 = 一个结果。没有中间层。**

---

## 核心引擎：四件套（来自 nexus/，不动原代码）

| 引擎 | 来源 | 职责 | 需要补的 |
|------|------|------|------|
| **GraphEngine** | `nexus/knowledge/graph_engine.py` | 知识图谱：节点+边+搜索 | `remove_entity()` + `auto_save` |
| **RAGEngine** | `nexus/knowledge/rag_engine.py` | 向量搜索：分块+embedding+双通道 | `save()`/`load()` + `remove()` |
| **CommunityDetector** | `nexus/knowledge/community.py` | Louvain 社区聚类 | 够用 |
| **Orchestrator** | `nexus/knowledge/orchestrator.py` | Plan→Execute→Report | 够用 |

**需要补的代码量：总共约 20 行。**

---

## 新增：两个壳

### 壳1：FileKB（文件系统壳）

```
FileKB 做的事：
  1. 监听文件夹变化（新增/修改/删除）
  2. 新文件 → 解析 → GraphEngine + RAGEngine 摄入
  3. 删文件 → GraphEngine + RAGEngine 同步删除
  4. 改文件 → 删旧索引 + 重新摄入
```

### 壳2：HTTP API + MCP Server

```
Agent 能做的事：
  POST /search  {"q": "半导体"}       → 搜索
  POST /ask     {"q": "华天科技分析"}  → Qwen 问答
  GET  /status                        → 状态
  GET  /graph/:id                     → 图谱邻居
```

---

## 实施顺序

```
Phase 1（今天）: nexus_kb/ 创建 + 四件套复制 + KnowledgeBase 类
Phase 2（今天）: RAGEngine 持久化（save/load）+ GraphEngine 增量删除
Phase 3（明天）: FileKB 文件夹监听 + 文件解析器
Phase 4（明天）: HTTP API + MCP Server
Phase 5（后续）: LoRA 微调触发
Phase 6（后续）: 网络搜索爬虫
```

---

## 张凯的三个原始决策（不准偏离）

1. **不做 Agent 平台，做知识库**。不被 OpenClaw/Hermes/Claude Code 带偏。
2. **用本地四件套，不调外部 API**。Qwen 免费、数据不出门。
3. **丢进去就行**。不问用户"要不要摄入"，不问"放在哪个目录"，不问"解析策略"。自动处理。
