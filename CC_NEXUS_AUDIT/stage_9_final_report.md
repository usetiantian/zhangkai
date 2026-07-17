# 阶段 9 最终报告：World Model Seed Injection

**日期**：2026-07-15  
**范围**：只新增 `C:\Users\87999\claude-workspace\seed_world_model.py`；未修改 Nexus 的任何 `.py` 逻辑，未触碰 `.git`。

## 1. 实际数据源盘点

本次在 `C:\Users\87999\.nexus` 目录实际读取并计数：

| source | 实际候选数量 | 读取位置 / 口径 |
|---|---:|---|
| `bilibili_seeds` | **56** | `data/bilibili_seeds.json`；56 条均有可用 `audio_seed.text`/文本 seed |
| `identity_weights` | **26,291** | `data/neural/nexus_identity.weights`，并通过 `living_core.identity.get_identity()._weights` 验证 |
| `curiosity` | **6,528** | `data/curiosity/unanswered_questions.jsonl` **4,719** + `research_tickets.jsonl` **1,809** |
| `conversations` | **4,900** | `conversations/*.jsonl`，139 个 JSONL 文件合计 |
| `experience` | **7,318** | `data/experience_bank.db` 的 `experiences`；排除 `type='test'` 和 `type LIKE 'test_%'` 后。原表总数为 7,322 |

补充：已知诊断口径中的 `experience_bank` “约 7,320”与实际表总数 7,322 一致；过滤测试项后本次脚本可用候选数为 7,318。

## 2. 实际执行

按任务要求从 Nexus 目录运行：

```text
cd C:\Users\87999\.nexus
python ..\claude-workspace\seed_world_model.py --source=bilibili_seeds
```

实际 stdout：

```text
[START] source=bilibili_seeds nodes_before=21 data_dir=C:\Users\87999\.nexus\data\world_model
[DONE] {"source": "bilibili_seeds", "before_nodes": 21, "added": 56, "after_nodes": 77, "methods": {"encoder": 56, "hash_fallback": 0}, "elapsed_sec": 0.41}
[LOG] C:\Users\87999\.nexus\data\world_model\seeding_log.json
```

`data/world_model/seeding_log.json` 的落盘结果同样记录：

- `before_nodes`: **21**
- `added`: **56**
- `after_nodes`: **77**
- `encoder`: **56**
- `hash_fallback`: **0**
- `elapsed_sec`: **0.41**

### 节点数对比

```text
执行前：21
本次新增：56
执行后：77
变化：+56（21 + 56 = 77）
```

本次没有触发每 100 节点一次的进度行，因为 bilibili source 只有 56 条；脚本对更大 source 仍会在每处理 100 条时打印 `[PROGRESS]`。

## 3. 实现核验

`seed_world_model.py` 共 **129 行**（满足 ≤150 行），并已通过：

```text
python -m py_compile seed_world_model.py  -> exit 0
```

实现要点：

1. 脚本启动时切换到 `Path.home() / ".nexus"`，并把该目录加入 `sys.path`，避免从 workspace 运行时的 Cygwin/Windows 路径问题。
2. 顶层导入 `nexus_agent.neural.encoders` 与 canonical `get_unified_space`；导入异常不吞掉，符合“import 报错立刻停下”。
3. 使用 `encoders.get_encoder_hub().encode(text, "text")` 生成 256 维向量；编码失败或向量无效时才使用确定性的 SHA-256 hash fallback。
4. 直接调用 `Unified256Space.add_node(..., dedup=False)` 注入 `data/world_model`，确保每条 source 记录都对应一个 seed 节点。
5. 支持全部要求的参数名：`auto`、`bilibili_seeds`、`identity_weights`、`curiosity`、`conversations`、`experience`，并支持可选 `--limit`。
6. `auto` 顺序为：`bilibili_seeds > identity_weights > curiosity > conversations > experience`。

## 4. 性价比结论

**当前阶段 `bilibili_seeds` 性价比最高。**

理由：

- 仅 **56** 条，文本已经存在，不需要从 184 个 MP4 再做音频/视频抽取。
- 本次实际运行仅 **0.41 秒**，一次性新增 **56** 个节点，且 56/56 使用 canonical encoder 成功。
- 数据是经过 Bilibili seed pipeline 整理后的结构化内容，包含标题、topic/audio 文本和 `seed_id` 元数据，来源可追踪。
- 与 21 个已有节点相比，新增量明确、可验证、风险最低。

其他 source 的取舍：

- `identity_weights` 数量最大，但 26,291 条会带来较高编码和在线聚类成本，而且身份规则与通用世界知识并不完全同质，建议后续分批、去重、限额注入。
- `curiosity` 约 6,528 条，适合后续构建“问题/研究线索”层，但应保留 ticket 状态等元数据，避免把未回答问题误当成事实。
- `conversations` 4,900 条，适合抽取用户偏好和交互经验；直接全量注入可能混入工具调用、短噪声和重复上下文。
- `experience` 过滤后 7,318 条，价值较高但规模大，且内容类型混杂；应先按 `type`/`significance` 分层，再批量导入。

## 5. 后续阶段建议

1. **先验证检索质量**：对新增的 Bilibili 节点执行 `search()`/`search_hybrid()`，抽样检查标题、主题和音频文本是否能被相近查询召回。
2. **分批注入大 source**：建议每批 100–500 条，记录 `before/after`、耗时、encoder/fallback 比例；不要一次性把 26,291 条身份权重全部灌入。
3. **保留来源元数据**：curiosity 需要保留 `status`、`phase`、`ticket_id`；experience 需要保留 `type`、`significance`；conversation 需要保留 `role`、文件名和 session 信息。
4. **先做 source-specific 去重**：尤其是 identity 与 conversation，避免相同文本因 label 不同产生大量近重复节点；去重策略应在外部 seeder 中实现，不改 Nexus canonical 代码。
5. **再评估 `auto`**：当前 `auto` 按性价比只选择第一个可用 source，即 Bilibili；如果要多源联训，应显式多次运行并分别保存日志，而不是默认一次性灌入所有大表。
6. **MP4 暂缓**：`bilibili_videos` 的 184 个 MP4 没有直接文本，先单独完成 seed extractor 与抽样质量验证，再接入 world model。

## 结论

阶段 9 的“真写 + 真跑”已完成：新增脚本真实可运行，Bilibili 56 条已经编码并持久化到 canonical Unified256Space，世界模型节点数从 **21** 增长到 **77**。