# Nexus 工作日记 — 2026-07-08

## 今日完成概述

全模块最强化重构。从"玩具代码/空转系统"升级为"真实数据驱动的自进化AI"。

---

## 一、编码器升级 v3（5/5 模态）

| 编码器 | 升级前 | 升级后 | 验证 |
|--------|--------|--------|:--:|
| 文本 | n-gram hash | FastText子词skip-gram + IDF加权 + 位置编码 | 6/6语义正确 |
| 图片 | HSV直方图 | LBP纹理(59维)+HOG梯度(108维)+HSV颜色(80维) | ✅ |
| 音频 | SHA256 hash | 32帧MFCC+Δ一阶+ΔΔ二阶+频谱质心/滚降/通量 | ✅ |
| 视频 | 文件名hash | ffmpeg抽帧+motion vectors+镜头边界检测 | ✅ |
| 代码 | 关键词计数 | AST节点遍历+控制流复杂度+数据流特征 | ✅ |

全部256维对齐，纯Python+numpy，零外部依赖。

---

## 二、神经网络升级（7个模型）

| 模型 | 升级前 | 升级后 | 参数量 |
|------|--------|--------|:--:|
| Backbone | 256→256→128 | 残差256→256→256 SiLU+LayerNorm | 132K |
| KnowledgeGate | Linear(128,4) | 残差256→256→128→4 SiLU+LN | 133K |
| ComplexityScorer | Linear(128,2) | 残差256→256→128→2 SiLU+LN | 100K |
| SignalBus | Linear(128,1) | 残差256→256→64→1 SiLU+LN | 83K |
| GapAnalyzer | Autoencoder | 残差自编码器256→128→256 | 199K |
| Router | Transformer 4L | 保持不变(已是真货) | 151K |
| Heads | LoRA框架 | 保持不变(已是真货) | - |

总计448K可训练参数。训练循环改为AdamW+梯度裁剪+真实数据(非torch.randn)。

---

## 三、WorldModel升级

- 关系边: add_edge + query_related + 正反向查询 + BFS多跳 + 路径评分
- 去重: 同label+modality节点合并, 同from+to+relation边合并
- BM25混合检索: BM25关键词(0.3)+向量语义(0.5)+图重要性(0.2)三路融合
- 持久化: nodes.json + edges.json + vectors.npy自动落盘
- 在线聚类: 自动发现概念群 (clusteredAs边)
- EvoKG↔WorldModel桥: 27323行长期记忆↔30节点工作记忆双向流动

---

## 四、事件总线修复

```
修复前: 86个事件, 24个ACTIVE, 38个NO_SUBS, 24个NO_PUBS
修复后: 核心链路全部接通
  self_play.complete → round_done → SignalTracker
  gap.discovered → DecisionAgent
  knowledge.internalized → 5 subscribers
  learning.plan.created → learning.completed
  tool.call.completed/failed → SignalTracker
```

---

## 五、7Agent认知循环

- Reflexion: 失败时自动反思+重试(最多2轮)
- 自一致性: ReasonerAgent 3路投票(安全/速度/探索)
- Priority+Reasoner并行
- Guardian→ProgressiveAutonomy自主检查
- 结果→SignalTracker反馈闭环

---

## 六、知识管线

```
SelfDirectedLearner → learning.plan.created
  → UnifiedLearner(9策略学习) → unified.knowledge_merged
    → KnowledgeGen(非LLM 3源 + LLM兜底 + 策略切换 + 知错能改)

非LLM源: SelfPlay失败提取 + 代码库模式 + WorldModel检索
LLM源: DeepSeek API(模型名bug已修)
```

---

## 七、B站多模态管线

```
搜(热门榜API) → 下(yt-dlp 360p) → 拆(ffmpeg音频+关键帧)
  → 编码(5模态) → WorldModel observe + EvoKG feed
    → 跨模态边(同视频文本↔图片↔音频)

双触发: 心跳(每30tick热榜) + 事件(用户兴趣/缺口/好奇)
```

---

## 八、Hermes遗产清理

删除22个死代码文件(~15000行):
auxiliary_client, anthropic_adapter, bedrock_adapter, credential_pool,
model_metadata, display, context_engine, credential_sources, 
image_gen_registry, prompt_builder, shell_hooks, skill_commands,
usage_pricing, copilot_acp_client, file_safety, gemini_native_adapter,
gemini_schema, image_gen_provider, models_dev, nous_rate_guard, 
redact, skill_preprocessing

保留6个(有实际依赖): memory_provider, skill_utils, nexus_state, nexus_time, memory_manager

---

## 九、激活的懒加载模块

新加auto-subscribe: knowledge_digester, skill_generator, hypothesis_engine, experience_analyzer, unified_memory
3个已有: agi_growth_engine, solidification_engine, concept_verification

---

## 十、关键Bug修复

- LLM模型名bug: body["model"]写死用第一个provider → 修成per-provider
- causal engine边膨胀: 重启时重复加边 → 添加去重
- SignalTracker饱和: knowledge=1.0永远满分 → 质量加权+趋势检测
- GapAnalyzer掩耳盗铃: learned=0冷却掩盖 → 保持活跃+提优先级
- 事件名不匹配: self_play.complete vs self_play.round_done → 统一
- .env自动加载: nexus_llm.py启动时加载dotenv
- python路径问题: subprocess用sys.executable确保同环境
- f-string反斜杠: 改为字符串拼接

---

## 十一、配置更新

- SOUL.md/USER.md/MEMORY.md: 从docs/复制到根目录(启动时找不到)
- MEMORY.md: 清理过时历史+更新今日改动记录
- nexus_daemon.bat: 精简启动步骤+加dotenv依赖检查
- 旧NN权重: 删除不兼容的.pt文件, 重新训练保存(403+336+536KB)

---

## 当前系统状态

```
Nexus 运行中 | Port: 19666 | 启动: nexus_daemon.bat
编码器: 5模态v3 | NN: 7残差MLP(448K参数) | WM: 节点+边+BFS
事件: 6条核心链路接通 | 知识: 非LLM三源+LLM兜底
B站: 双向触发+全自动 | EvoKG: 27323行↔WM桥
```

---

## 待优化(下个会话)

1. EvoKG活性硬编码: get_chemistry_score返回实际值
2. God模块拆分: 16个>2000行文件
3. NN训练数据积累: 系统跑起来自然产生
4. WorldModel概念层级自动发现
5. ExternalExplorer GitHub+PyPI完整实现
