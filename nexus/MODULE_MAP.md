# Nexus 模块地图 — 重启后看这个

## 启动顺序

```
1. STATUS.md         ← 做到哪了
2. ARCHITECTURE.md   ← 怎么设计的
3. 本文件             ← 每个模块干什么、在哪个文件、依赖什么
4. PROJECT_NEXUS.md  ← 立项背景(workspace根目录)
5. CLAUDE.md         ← 行为约束
```

## 模块索引

```
nexus/
├── main.py              → 主入口，Nexus类串联所有模块
│
├── core/                → 核心层
│   ├── event_bus.py     → 模块通信总线(发布/订阅，挂了不互相影响)
│   ├── identity_core.py → 身份核心(Constitution+六级优先级+意图分类)
│   └── speculative.py   → 投机执行(预览→确认生效→拒绝零影响)
│
├── knowledge/           → 知识层
│   ├── graph_engine.py  → 知识图谱(纯Python，节点+边+搜索+持久化)
│   ├── community.py     → 社区检测(Louvain算法，节点分组)
│   ├── rag_engine.py    → RAG引擎(文档摄入+分块+关键词搜索)
│   └── orchestrator.py  → 多Agent编排(Plan→Execute→Report)
│
├── memory/              → 迁移到 original/，新版本用知识层
│
├── learner/             → 学习层
│   ├── engine.py        → 自主学习(AutoLearner队列+DocumentIngester喂养)
│   ├── lora_trainer.py  → LoRA训练(PEFT加载+训练+保存adapter 33.5MB)
│   ├── aegis.py         → AEGIS四角色(消化/规划/进化/评审闸门)
│   └── compactor.py     → 五层压缩(snip/micro/auto/reactive/aegis)
│
├── recovery/engine.py   → 七层自愈(重试+降级+熔断+持久重试)
├── user/manager.py      → 多用户管理(创建+切换+隔离+LoRA)
├── skills/
│   ├── registry.py      → 技能注册中心(注册+匹配+执行+延迟加载)
│   └── sandbox.py       → 技能沙箱(进程隔离+超时+危险导入拦截+上架扫描)
├── bridge/feishu.py     → 飞书双向桥(发送+接收+消息处理器)
├── models/loader.py     → 模型加载(Qwen2-VL-2B真推理已验证, RTX5080)
├── voice/pipeline.py    → 语音管线(Whisper听+Piper说)
│
├── original/            → 第一版源码(归档)
├── tests/               → 测试文件
├── STATUS.md            → 开发状态追踪
├── ARCHITECTURE.md      → 架构总图
└── RESEARCH_NOTES.md    → 研究库评估
```

## 依赖关系(EventBus连接)

```
user.message ──→ identity_core  (意图分类)
             ──→ graph_engine   (记录用户实体)
             ──→ rag_engine     (追加短期记忆)

identity.decision ──→ orchestrator (执行调度)

module.dead ──→ recovery (降级通知)

error.occurred ──→ recovery.circuit_breaker (熔断)

document.ingested ──→ graph_engine (建关系边)

learning.needed ──→ auto_learner (加入学习队列)
```

## 关键数字

| 指标 | 值 |
|------|-----|
| 模块总数 | 20 |
| 测试总项数 | 39(全量) + 多项专项 = 60+ |
| 全量测试 | 39/39 ✅ |
| 压力测试 | 1000节点图+500文档RAG+30轮对话 ✅ |
| Qwen深度推理 | analyze/learn/search/chat 四类 ✅ |
| 语义RAG | 本地embedding模型 ✅ |
| 对话记忆 | 多轮上下文不遗忘 ✅ |
| 主动建议 | 行为模式→推荐下一步 ✅ |
| AEGIS进化 | 消化/规划/进化/评审闸门 ✅ |
| Constitution | 6种危险模式全拦截 ✅ |
| Qwen加载时间 | 11.2s |
| Qwen参数量 | 2.2B |
| LoRA adapter | 33.5MB |
| VRAM占用 | ~6GB |
| 压缩层数 | 5层 |
| AEGIS角色数 | 4(消化/规划/进化/评审) |
| EventBus连接 | 9条 |
| Constitution规则 | 10条 |
