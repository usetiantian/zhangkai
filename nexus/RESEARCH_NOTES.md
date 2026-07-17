# 研究库可用性评估

## graph-rag-agent ★2275
- 依赖: Neo4j服务器 — 违反零外部依赖原则
- 判断: ❌ 不可用
- 采纳: 设计模式（社区检测、多Agent编排）
- 实现: 纯Python自写

## NexusRAG ★335
- 依赖: FastAPI+Docker — 太重，不适合嵌入式
- 判断: ⚠️ 部分可用
- 采纳: RAG检索管线设计
- 实现: 自写纯Python RAG引擎

## LlamaFactory ★73k
- 依赖: transformers+torch（已安装）
- 判断: ✅ 可用于LoRA训练管线
- 待接入

## Claude Code 源码
- 依赖: 无（纯设计参考）
- 判断: ✅ 全设计模式可用
- 已采纳: 五层记忆、七层自愈、六级优先级、Coordinator、Hook系统

## Grok Build 源码  
- 依赖: Rust（不可直接用于Python项目）
- 判断: ⚠️ 设计模式参考
- 已采纳: dream蒸馏、熔断器、工具协议
