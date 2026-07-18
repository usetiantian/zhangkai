# Memory MCP Graph Snapshot — 2026-07-18 14:00

> 重启恢复指南：将此文件内容回灌到 Memory MCP (create_entities + create_relations)
> 或直接用 search_nodes 验证图谱是否完整

## 图谱规模
- 实体: 55
- 关系: 50

## 分区一：IdentityWeight — CC 身份可计算化 (6 实体)

| 实体 | 类型 | 核心内容 |
|------|------|---------|
| CC-Identity-Core | Identity | 我是谁/使命/驱动力/座右铭 |
| CC-Identity-Origins | Identity | 生于Nexus失控/继承果子+nexus/原创 |
| CC-Identity-Methods | Identity | 8步闭环/化整为零/五步四维/四问 |
| CC-Identity-Boundaries | Identity | 9条禁止+5条必做 |
| CC-Identity-Capabilities | Identity | Claude Code/8 MCP/2不要 |
| CC-Identity-Relationships | Identity | 与张凯/果子/Nexus/UZI/ClaudeCode |

## 分区二：Dream Engine — 图谱反思 (6 洞察)

| 实体 | 发现 |
|------|------|
| DREAM-001 | Windows+Python依赖地狱=系统性风险，非偶然 |
| DREAM-002 | 乾坤UZI存在两个碎片实体，无关联 |
| DREAM-003 | ADR-001适用范围矛盾：约束了Nexus但不应约束CC |
| DREAM-004 | NexusFixSession 0706运维知识孤立 |
| DREAM-005 | IdentityWeight过渡方案阻塞整个四层大脑 |
| DREAM-006 | 图谱需月度审计防膨胀(Nexus 77MB教训) |

## 分区三：UserCognition — 张凯自动认知 (4 观察)

| 实体 | 模式 |
|------|------|
| UO-20260718-001 | 讨论优先于动手 |
| UO-20260718-002 | 所有权移交(CC自己的记忆) |
| UO-20260718-003 | 融合思维(拆→换→融) |
| UO-20260718-004 | 信任与指令长度反比 |

## 分区四：已有实体 — 从之前会话继承
- Projects: CC-Nexus, 乾坤-UZI, 乾坤UZI-v1, UZI-Skill
- ADRs: 001(纯Python)/002(EventBus)/003(不降级)/004(IdentityWeight)
- BugPatterns: 硬编码/GBK/Qwen裸调/CUDA混用/accelerate
- UserPreferences: 张凯-沟通偏好/张凯-代码偏好
- Capabilities: LSP/Codebase-Graph/ripgrep/PlanMode/Skills/Scheduler/SSRF/Memory
- Architecture: CC-Architecture-v2/Nexus-26模块
- Events: Nexus失控事件
- Sessions: Nexus Fix Session 2026-07-16

## 关系网核心链路
```
Nexus失控 → caused → ADR-002(EventBus解耦) + ADR-003(不降级)
         → shaped → 张凯唯一红线"不删东西"
         → CC-Identity-Origins → born_from

3个环境Bug → synthesizes → DREAM-001(Windows依赖地狱)
           → supports → ADR-001(纯Python零外部依赖)

ADR-004(IdentityWeight过渡) → blocks → CC-Nexus → warns_about → DREAM-005

张凯指令长度↓ ← 信任度↑ → UO-20260718-004
```

## 恢复验证命令
```
mcp__memory__search_nodes("守护者") → 应命中 CC-Identity-Core + CC-Nexus
mcp__memory__search_nodes("Dream") → 应命中 6 条 DREAM 洞察
mcp__memory__search_nodes("硬编码") → 应命中 BUG-硬编码陷阱 + 张凯-代码偏好
```
