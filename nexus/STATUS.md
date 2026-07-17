# Nexus — 开发状态追踪

> 重启后看这里：做到哪了、哪个模块过了、哪个在修

## 铁律
- 不偷偷降级 → 缺依赖就报错，不 fallback
- 每次写模块 → 跑测试 → 记录结果
- 模块间通过 EventBus 通信，不直接 import

## 模块清单

| 模块 | 状态 | 测试 | 借鉴来源 | 依赖 |
|------|:--:|:--:|------|------|
| knowledge/graph_engine.py | ✅ | 全测通过 | graph-rag-agent设计模式 | 无 |
| knowledge/community.py | ✅ | 全测通过 | graph-rag-agent Leiden→Louvain | 无 |
| knowledge/orchestrator.py | ✅ | 全测通过 | graph-rag-agent Plan-Execute-Report | 无 |
| knowledge/rag_engine.py | ✅ | 全测通过 | NexusRAG检索管线 | 无 |
| recovery/engine.py | ✅ | 全测通过 | ClaudeCode七层恢复 | 无 |
| user/manager.py | ✅ | 全测通过 | ClaudeCode多租户隔离 | 无 |
| voice/pipeline.py | ⚠️ | 待实测 | 原Nexus模型文件 | whisper库 |
| models/loader.py | ⚠️ | 待实测 | LlamaFactory量化加载 | transformers+torch |
| original/* | ✅ 归档 | 全部通过 | 第一版自写 | — |

## 测试记录

| 测试文件 | 结果 | 日期 |
|------|:--:|------|
| test_graph_full.py (图+社区+编排+RAG) | 8/8 ✅ | 07-17 |
| test_integration_v2.py (图+RAG降级) | 7/7 ✅ | 07-17 |
| test_nexus_full.py (全模块综合) | 9/9 ✅ | 07-17 |
| original/tests/* (旧版全部) | 全部通过 | 07-17 |

## 研究库评估

| 项目 | 判断 | 原因 |
|------|:--:|------|
| graph-rag-agent | ❌ 不可用 | 依赖Neo4j服务器 |
| NexusRAG | ⚠️ 部分 | 设计模式可用，太重 |
| LlamaFactory | ✅ 可用 | LoRA训练管线 |
| ClaudeCode源码 | ✅ 全设计 | 纯设计参考 |
| GrokBuild源码 | ⚠️ 设计 | Rust不可用于Python |

## 当前进度
图引擎+社区检测+RAG+编排+恢复+用户 — 全部纯Python零依赖，集成测试通过。
语音和模型加载器已写，待实测（需要模型文件+whisper库确认安装）。
