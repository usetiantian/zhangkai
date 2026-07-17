# Nexus 工作日记 — 2026-07-14

## 今日主题：从濒死到自进化 — 29 commits

---

## 第一幕：四个致命 Bug

| Bug | 根因 | Commit |
|-----|------|--------|
| DeepSeek HTTP 400 | body.model 共享，切换 provider 不更新 | bef32fd |
| Tier2 100% 失败 | _fix_structural_issues 跨类 AttributeError | 533c649 |
| 响应静默丢弃 | task/seed NameError + except Exception | 3cbecf9 |
| 协程泄漏 | _handle_feishu 返回 coroutine 未 await | 02018fe |

---

## 第二幕：能力体系

- LocalModel 桥接 → Tier1 Qwen2-VL 本地推理可用
- chat_with_video/image/audio → 全模态理解
- DFA 流水线 → CEILING 时即时触发修复
- 双 prompt → Tier1 简洁 / Tier2 详细

---

## 第三幕：五模态训练

- FiveModalTrainer：分模态训练，代码 loss 0.84
- AutoTrainingScheduler：克隆训练，VRAM 自动释放
- 训练数据：Self-play(204) + 对话(141) + 日记(40) + B站(29)
- 最优步数：250-300

---

## 第四幕：精细化

- 动态域：40+主题，不再硬编码 3 个
- 世界模型修复：get_world_model() 替代不存在的 v2 API
- 种子三层去重：搜索多样性 + seed_id + 内容哈希
- 安全：清除敏感外部仓库 + 黑名单

---

## 数据全貌

```
World Model:  B站种子 → observe() → encoder_hub编码 → unified_space存储
训练数据:     Self-play + ChromaDB对话 + 日记 + B站种子
              ↓
              FiveModalTrainer → Qwen2-VL LoRA → disk
全部是 Nexus 自己产生的知识。
```

---

## CC今日教训

1. `except Exception: logger.debug()` — 定时炸弹
2. 深层嵌套改代码 → 反复破坏缩进
3. 文件清空后再也找不回 → 时刻 git commit
4. 方法不存在但"看起来应该存在" → 别猜，grep 验证

---

## 最终状态

```
✅ API:      DeepSeek 正常, MiniMax 间歇 529
✅ Tier1:    Qwen2-VL 本地推理, 零 API 成本
✅ 种子:     29条落盘, 去重率 90%
✅ 训练:     385 样本就绪, 自动触发待命
✅ 域:       动态 40+ 主题轮换
✅ 多模态:   图片/视频/音频/文本全通道
✅ 世界模型: get_world_model() 正确初始化
```

29 commits. 晚安。
