# Nexus 休眠/冗余模块清单 (2026-07-15)

> 371个.py文件中, 以下是可以考虑清理的模块。
> 每项标注: 功能、替代者、建议操作。

---

## 可删除 (0消费者, 完全无用)

| # | 文件/目录 | 功能 | 替代者 | 建议 |
|---|----------|------|--------|------|
| 1 | `tui/` | 终端UI界面 | — | 🗑️ 删除 |
| 2 | `workspace_manager/` | 工作区管理(未接入) | `workspace_organizer.py` | 🗑️ 删除 |
| 3 | `nexus_cli/` (0文件) | 早期命令行外壳 | — | ✅ 已空, 删目录 |

---

## 可合并 (被替代, 保留旧接口)

| # | 文件/目录 | 功能 | 替代者 | 消费者 | 建议 |
|---|----------|------|--------|--------|------|
| 4 | `metacognition/` (2文件) | 旧元认知 | `meta_cognition/` (16消费者) | `self_optimization.py` | 🟡 改为wrapper, 转发给meta_cognition |
| 5 | `self_modifying/` (1文件) | 旧自修改 | `self_modifier/` (11消费者) | 仅自身引用 | 🗑️ 删除 |

---

## 保留不动 (有消费者, 虽然少)

| # | 文件/目录 | 功能 | 消费者数 | 状态 |
|---|----------|------|---------|:---:|
| 6 | `elastic/` (1文件) | 弹性参数配置 | 7间接 | ✅ 保留 |
| 7 | `evolving/` (1文件) | 进化facade | 2间接(flywheel,multi_agent) | ✅ 保留 |
| 8 | `file_discipline/` (2文件) | 文件规范引擎 | 1(nexus_fusion) | ✅ 保留 |
| 9 | `llm_parser/` (1文件) | LLM输出解析 | 12间接 | ✅ 保留 |
| 10 | `sandbox/` (1文件) | 沙箱隔离 | 8间接 | ✅ 保留 |
| 11 | `self_modifier/` (1文件) | SafeSelfModifier | 11间接 | ✅ 保留 |

---

## 骨架/模板 (有用但未完全填充)

| # | 文件/目录 | 功能 | 建议 |
|---|----------|------|------|
| 12 | `skills/` (1文件, 265L) | agentskills.io兼容技能系统 | 🟡 保留骨架, 后续填充 |
| 13 | `code_templates/` (1文件, 150L) | 结构化代码模板库 | 🟡 保留骨架, solidification_engine写入 |

---

## 已清空 (只剩目录)

| # | 目录 | 原始文件数 | 状态 |
|---|------|-----------|:---:|
| 14 | `body/` | ~70 | ✅ 已迁移到nexus_agent/和nexus_gateway/ |
| 15 | `nexus_cli/` | ~70 | ✅ 已清空 |

---

## 已删除 (今日操作)

| # | 文件 | 行数 | 原因 |
|---|------|------|------|
| 16 | `bilibili_pipeline_v2.py` | ~120 | 从未被import |
| 17 | `neural/world_model.py` | 425 | 四件套替代 |
| 18 | `neural/evokg_world_model.py` | 166 | 四件套替代 |
| 19 | `neural/evokg_world_model_compat.py` | ~50 | 四件套替代 |
| 20 | `neural/fused_arch_bridge.py` | 250 | PE循环死代码 |
| 21 | `world_model/training.py` | 20 | 孤儿, 调不存在函数 |
| 22 | `nexus_full_cycle.py` | 200 | 被LocalModel替代 |

---

## 汇总

| 状态 | 数量 | 节省 |
|------|------|------|
| 🗑️ 建议删除 | 5项 (tui, workspace_manager, nexus_cli, self_modifying, metacognition合并) | ~20文件 |
| ✅ 确认保留 | 11项 | — |
| ✅ 已删除 | 7文件 | ~1100行 |
| 🟡 骨架保留 | 2项 (skills, code_templates) | — |

**净效果**: 371个.py文件 → 可精简到~350个。体感不大, 因为这些休眠模块本来就未被加载, 不影响性能。
