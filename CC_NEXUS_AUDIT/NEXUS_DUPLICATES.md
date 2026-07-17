# Nexus 模块唯一性审计 (2026-07-15)

> 扫描对象：`C:\Users\87999\.nexus`
> 审计者：Claude Code (delego subagent)
> 方法：对每组高怀疑重复，列出候选路径 / 行数 / mtime / **实际被谁 import** / 保留建议 / 合并方案
> 总文件数：644 个 .py；总代码量约 18 万行；下面挑出 10 组 **证据最确凿** 的重复模式
> 完整 import grep 来源：已在各组"import 证据"行列出实际引用计数

---

## 1. EventBus — 5 处重复 ✅ 已收敛到 nexus_agent/event_bus

| 候选 | 路径 | 行数 | 文件 mtime | import 计数 | 谁先有 |
|---|---|---|---|---|---|
| A | `kernel/event_bus.py` | 770 | 2026-07-07 01:11 | **3**（旧路径） | 旧（早期 BlueberryOS 框架） |
| B | `nexus_agent/event_bus.py` | 701 | 2026-07-09 16:42 | **86**（活跃） | 新 |
| C | `nexus_agent/closed_loop_engine.py` (emit_event) | 2219 | 2026-07-14 15:07 | 内嵌方法 | 同 B（早期版本） |
| D | `nexus_agent/event_emitter.py` | 161 | 2026-06-16 | **2**（自身薄封装） | 旧 wrapper |
| E | `nexus_agent/cognitive_loop/__init__.py` 内 EventBus | 3173 | 2026-07-14 06:20 | 模块内闭合 | 已被 B 取代 |

**import 证据**（grep "from nexus_agent.event_bus" vs "from kernel.event_bus"）：
- `from nexus_agent.event_bus import get_event_bus` 出现 **88 次**（含 4/8 缩进变体）
- `from kernel.event_bus import get_event_bus` 出现 **3 次**（均为老代码残留）
- `nexus_agent/event_emitter.py` 顶部自述："自 v5.5 起，底层委托给 nexus_agent.event_bus.EventBus（统一 pub/sub 骨干）" — 已经是 wrapper。

**推荐保留**：**B** `nexus_agent/event_bus.py`（被 86 处引用，运行时初始化日志明确 "Unified event bus initialized"）。
**删除/合并**：
- **A** `kernel/event_bus.py` → 整文件标记删除（替换 3 处 import 为 nexus_agent.event_bus）
- **C** `closed_loop_engine.py` 的 `emit_event/subscribe/drain_events` 方法 → 重构为委托给 `get_event_bus()`
- **D** `event_emitter.py` 保留为薄兼容层（API 兼容用途）
- **E** `cognitive_loop/__init__.py` 内的 EventBus 类 → 已死代码（实际运行靠 B）

**合并方案（按风险排序）**：
1. 删 `kernel/event_bus.py`，sed 改 3 个旧 import
2. `closed_loop_engine.py` 的私有 EventBus 方法改为 `self.event_bus = get_event_bus(); self.emit_event = self.event_bus.publish` 之类的委托
3. `cognitive_loop/__init__.py` 内的 EventBus 类移到 `nexus_agent/event_bus_compat.py`（仅兼容老调用）

---

## 2. LLM Client — 3 处实现，2 死 1 活 ✅ 已收敛

| 候选 | 路径 | 行数 | 文件 mtime | import 计数 | 谁先有 |
|---|---|---|---|---|---|
| A | `nexus_agent/llm_client.py` | 84 | 2026-07-10 00:17 | **8**（仍被引用） | 旧（thin wrapper） |
| B | `nexus_agent/nexus_llm.py` | 762 | 2026-07-14 11:27 | **3**（少数） | 新 |
| C | `body/llm/client.py` | 273 | 2026-07-07 01:11 | **0**（死代码） | 旧框架 |

**import 证据**：
- `from nexus_agent.llm_client import get_llm_client` 出现 **5 次**（外层缩进）+ 3 次（更深缩进）
- `from nexus_agent.llm_client import llm_chat/NexusLLMClient` 出现 **3 次**
- `from nexus_agent.nexus_llm import NexusLLM` 出现 **3 次**
- `body/llm/client.py` **0 次 import**

**⚠️ 矛盾**：import 计数显示 `llm_client` (8) > `nexus_llm` (3)，但 `nexus_llm.py` 文件大 9 倍、mtime 新 4 天，且有运行日志 `[NexusLLM] 2个提供商就绪`。说明 `llm_client.py` 是 thin wrapper 委托给 nexus_llm。

**查 llm_client.py 验证（已读 84 行全文）**：是 facade，提供 `get_llm_client() → NexusLLM`，`llm_chat` 薄封装。**所以严格说不算重复**，是 API 适配层。

**推荐保留**：
- **A** `nexus_agent/llm_client.py` 84L 作 API 门面
- **B** `nexus_agent/nexus_llm.py` 762L 作核心实现（被 A 委托）

**删除/合并**：
- **C** `body/llm/client.py` → 整文件删除（0 import）

**结论**：仅 1 个真正重复（C）。A 和 B 是 facade/impl 合理分层，**不需合并**。

---

## 3. Evolution — 4 处实现 ✅ 仅 evolution_decision_engine 真正活

| 候选 | 路径 | 行数 | 文件 mtime | import 计数 | 谁先有 |
|---|---|---|---|---|---|
| A | `nexus_agent/evolution.py` | 1063 | 2026-07-10 00:29 | **0**（独立文件，未发现 import） | 旧 |
| B | `nexus_agent/evolution_engine.py` | 3738 | 2026-07-14 12:09 | **3** | 中间版本 |
| C | `nexus_agent/evolution_decision_engine.py` | 1333 | 2026-07-08 18:42 | **6**（最活跃） | 新调度层 |
| D | `closed_loop_engine.py` 中 `EvolutionEngine` 类 | 2219 | 2026-07-14 15:07 | 自身内嵌 | 已内嵌 |

**import 证据**：
- `from nexus_agent.closed_loop_engine import get_closed_loop_engine` **5+4=9 次**
- `from nexus_agent.evolution_decision_engine import ...` **3+2=5 次**
- `from nexus_agent.evolution_engine import get_source_evolution_engine` **3 次**
- `evolution.py` (1063L, 46KB) **0 次 import**（独立成壳）

**运行证据**：
- 日志 00:37:56 `[EvolutionDecisionEngine] #2040 — dispatching MEDIUM/improve target='execution_quality'` — C 是真调度器
- 日志 11:42:55 `[ClosedLoopEngine] 统一自主进化引擎 — 一套系统一条心` — D 包含"AGI Growth + Evolution"

**推荐保留**：
- **D** `closed_loop_engine.py` 内的统一入口（已聚合 7Agent + MetaCognition + AGI）
- **C** `evolution_decision_engine.py` 作为独立调度器（被 heartbeat_loop 调）

**删除/合并**：
- **A** `nexus_agent/evolution.py` (1063L / 46KB) → **整文件删除**（0 import + mtime 早 5 天 + 大量死代码风险）
- **B** `evolution_engine.py` (3738L / 184KB) → 检查它和 `closed_loop_engine.py` 内的 evolution 部分是否真的分工；如果是 source evolution（代码自改），保留；否则考虑整合

**合并方案**：
1. 先 grep `nexus_agent/evolution.py` 的全部符号定义，确认是否被任何字符串路径加载（maybe via importlib）
2. 若确认 0 引用 → 直接删 A
3. B vs D 的边界：建议保留 B 作为 "代码自修改"（沙箱修改 nexus 自己的代码），D 作为 "认知调度"（不改代码只改策略）

---

## 4. Self Model — 3 处实现 ✅ 已收敛到 nexus_self_model

| 候选 | 路径 | 行数 | 文件 mtime | import 计数 | 谁先有 |
|---|---|---|---|---|---|
| A | `nexus_agent/self_model/__init__.py` 142L + `engine.py` 523L + `health.py` 25L | 690 (合计) | 2026-06-16 01:34 | **1**（heartbeat_loop 的 _get_dynamic_keywords 内） | 旧包 |
| B | `nexus_agent/self_model_engine.py` | 84 | 2026-07-10 00:29 | **1** | 中间件 |
| C | `nexus_agent/nexus_self_model.py` | 453 | 2026-07-14 03:31 | **4**（最活跃） | 新主类 |

**import 证据**：
- `from nexus_agent.nexus_self_model import get_self_model` **4 次**
- `from nexus_agent.self_model_engine import SelfModelEngine` **1 次**
- `from nexus_agent.self_model.engine import SelfModelEngine` **1 次**（在 heartbeat_loop）

**运行证据**：
- data/self_model.json 持续刷新（含 capabilities: code_generation/hardware/code_modification/network）
- 日志无 `nexus_agent.self_model.engine` logger 输出 — A 包在运行路径上是装饰性的

**推荐保留**：
- **C** `nexus_self_model.py` 453L（被 4 处 import，是主类）

**删除/合并**：
- **A** `nexus_agent/self_model/` 整包（**仅 1 处弱引用**，且在 try/except 内）→ 删
- **B** `self_model_engine.py` 84L → 删（仅 1 处 import，且可能兼容 A 包）

**合并方案**：
1. A 包删除前先 grep `from nexus_agent.self_model` 全部 import（约 1-2 处），改写为 `from nexus_agent.nexus_self_model import get_self_model`
2. B 删除前确认 1 处 import 调用方（`heartbeat_loop._get_dynamic_keywords`）改为 C
3. 数据文件 `data/self_model.json` 由 C 维护，无需迁移

---

## 5. User Model — 4 处实现 ✅ nexus_user_profile 是入口，其他是引擎变体

| 候选 | 路径 | 行数 | 文件 mtime | import 计数 | 谁先有 |
|---|---|---|---|---|---|
| A | `nexus_agent/user_model/__init__.py` 96L + `engine.py` 374L + `health.py` 49L | 519 | 2026-06-16 01:34 | **3** | 旧包 |
| B | `nexus_agent/user_model_engine.py` | 319 | 2026-07-10 00:40 | **2** | 中间 |
| C | `nexus_agent/nexus_user_profile.py` | 133 | 2026-07-13 16:43 | **2** | 新（昨日更新） |
| D | `nexus_agent/user_identity/__init__.py` | 110 | 2026-06-16 01:34 | **2** | 旁支身份存储 |

**import 证据**：
- `from nexus_agent.user_model_engine import UserModelEngine` **2 次**
- `from nexus_agent.user_identity import get_user_store` **2 次**
- `from nexus_agent.nexus_user_profile import get_user_profile` **2 次**
- `from nexus_agent.user_model.engine import get_user_model_engine` **1 次**

**运行证据**：
- 启动日志 11:42:55 `用户上下文（信任+user_profile）已加载` → C 是入口
- data/user_model.json 极少量（13 条消息）

**推荐保留**：
- **C** `nexus_user_profile.py` 133L（最新 mtime，被启动流程加载）
- **D** `user_identity/` 包（独立 store 用途，2 处 import）

**删除/合并**：
- **A** `nexus_agent/user_model/` 整包（**3 处 import 但都是旧引用**）→ 待评估
- **B** `user_model_engine.py`（2 处 import，和 C 部分重叠）→ 可能保留为引擎实现

**合并方案**：
1. 先 cat A、B、C 三个文件的头部 docstring 判断功能边界
2. 如果 A/B 是 C 的历史分层，删 A 留 B+C；如果 A/B 提供 C 没的能力（如 personalization），保留为底层
3. 由于 data/user_model.json 实际由 C 写入，**建议最小集合：C（写） + B（读）** → 删 A

---

## 6. Knowledge Graph — 3+ 处实现 ✅ evokg 是唯一活

| 候选 | 路径 | 行数 | 文件 mtime | import 计数 | 谁先有 |
|---|---|---|---|---|---|
| A | `nexus_agent/knowledge_graph/__init__.py` 56L + `engine.py` 241L + `health.py` 13L | 310 | 2026-06-16 01:34 | **0**（独立包） | 旧 |
| B | `nexus_agent/evokg.py` | 2740 | 2026-07-14 (隐含) | **84**（含 `get_evokg`/`SubgraphType`/`RelationType`） | 主实现 |
| C | `nexus_agent/nexus_knowledge_*` | **0 文件**（不存在） | — | 0 | — |

**import 证据**：
- `from nexus_agent.evokg import get_evokg` 出现 **44+11+8+8+5+4+4+3+3+2 = 92+ 次**（最活跃）
- A 包 (knowledge_graph) **0 次 import**
- C 不存在 → 蓝莓怀疑清单基于历史，实际没创建过这个文件

**运行证据**：
- 启动日志 11:42:55 `meta_cognition 通过 evokg 恢复 1417 项目`
- data/knowledge_graph.json 只有 **2 节点**（不是 evokg 写入 — evokg 用 EvoKG 私有文件）
- evokg_world_model.py（neural 子模块）和 evokg.py 是同源（前者是 NN 后端）

**推荐保留**：
- **B** `evokg.py` 2740L（主知识图谱）
- `nexus_agent/neural/evokg_world_model.py` 166L（NN 后端，配套保留）

**删除/合并**：
- **A** `nexus_agent/knowledge_graph/` 整包 → **整文件删除**（0 import + 4 周未更新 + 自身只有 310L 的旧版骨架）

**合并方案**：直接删 A 包，无破坏面。

---

## 7. Meta Cognition — 3 处实现，**单文件 142 KB 巨型** ⚠️

| 候选 | 路径 | 行数 | 文件 mtime | import 计数 | 谁先有 |
|---|---|---|---|---|---|
| A | `nexus_agent/meta_cognition/__init__.py` | **3156** | 2026-07-14 06:20 | **16**（最活跃） | 新主模块 |
| B | `nexus_agent/metacognition/__init__.py` 108L + `engine.py` 506L | 614 | 2026-06-16 / 2026-07-12 | **0**（独立旧包） | 旧 |
| C | `nexus_agent/meta_governor.py` | 531 | 2026-06-16 01:34 | **0** | 旧调度层 |

**import 证据**：
- `from nexus_agent.meta_cognition import get_meta_cognition` **11+3+2 = 16 次**
- `from nexus_agent.metacognition import ...` **0 次**
- `from nexus_agent.meta_governor import ...` **0 次**

**运行证据**：
- 日志 11:42:55 `元认知系统初始化`
- 日志 00:36:04 `NexusMetaCognition === 元认知：知道自己 ===`
- 日志 00:36:05 `已知领域: 1179, 缺口: 0, 能力树: 3322 技能`

**⚠️ 严重发现**：`nexus_agent/meta_cognition/__init__.py` 长达 **3156 行 / 142 KB**（已读头 120 行确认是真正的 NexusMetaCognition 类 + MARS 双轨反思 + EvoKG 状态恢复）。这是个"包/单文件混杂"的反模式：**包名暗示有子模块，但实际所有逻辑都在 __init__.py**，不符合 Python 包约定。

**推荐保留**：
- **A** `meta_cognition/__init__.py`（实际是主模块，**应当重命名/重构**）

**删除/合并**：
- **B** `metacognition/` 整包 → **删除**（0 import）
- **C** `meta_governor.py` → **删除**（0 import；如果是早期 MetaGovernor 设计，已被 A 内的 `_tick_count` 等替代）

**合并方案（高优先级）**：
1. 把 A 的 3156 行 __init__.py 拆成 `meta_cognition/{engine, capability_bank, principle_bank, evokg_recovery, ...}.py` 子模块
2. B、C 删
3. 公开 API（`NexusMetaCognition` 类、`get_meta_cognition` 函数）在 `meta_cognition/__init__.py` 重新导出
4. ⚠️ **这一项对维护性影响最大**：单一 142KB 文件改一行就需要 IDE 加载整个文件

---

## 8. Autonomous Planner — 2 处实现 ✅ 总入口 vs 子模块（分工清晰但仍冗余）

| 候选 | 路径 | 行数 | 文件 mtime | import 计数 | 谁先有 |
|---|---|---|---|---|---|
| A | `nexus_agent/autonomous_planner.py` | 966 | 2026-07-10 00:29 | **2**（active 总入口） | 新 |
| B | `nexus_agent/autonomous/`（子包） | {__init__.py 63L, bilibili_pipeline.py, dialogue_learner.py, video_learner.py, acfun_pipeline.py, seed_extractor.py, integration.py} | 2026-06-16 | **5+**（作为实现层） | 旧 |

**import 证据**：
- `from nexus_agent.autonomous_planner import AutonomousPlanner` **2 次**（active）
- `from nexus_agent.autonomous.bilibili_pipeline import ...` **5+ 次**（来自 A 和 heartbeat_loop）
- `from nexus_agent.autonomous.dialogue_learner import DialogueLearner` **2 次**

**运行证据**：
- 日志 00:36:04 `[AutonomousPlanner] Proactive check (idle=137s)` → A 是真运行的入口
- A 顶部 docstring: "NexusAgent - 主动思考 + 主动规划" — 应该是 orchestrator
- B 子包内容是 **bilibili/acfun 视频爬取 + 对话学习**（特定数据源），是 A 的 data source 而非 competitor

**⚠️ 结论**：**严格说不算重复** — A 是 planner（orchestrator），B 是 data pipeline（实现）。但**目录冲突命名**：`autonomous_planner.py` (单文件) vs `autonomous/` (子包) — 容易混淆。

**推荐保留**：
- **A** `autonomous_planner.py` 966L（运行入口）
- **B** `autonomous/` 子包（视频数据源实现）

**清理建议**：
1. 把 `autonomous/` 重命名为 `autonomous_sources/` 或 `data_pipelines/`，避免和 `autonomous_planner.py` 视觉冲突
2. 不删代码，只重命名

---

## 9. Self Reflection — 10 处散落实现 🟡 高度碎片化

| 候选 | 路径 | 行数 | 文件 mtime | import 计数 | 谁先有 |
|---|---|---|---|---|---|
| A | `nexus_agent/self_reflection/`（10 个子模块） | 1350 (合计) | 2026-06-16 + 7月7日 | **8**（细分 import） | 旧分散包 |
| B | `nexus_agent/reasoning_chain.py` | ~?? | 2026-07-? | **2** | 兄弟模块 |
| C | `nexus_agent/reflection.py` | **不存在** | — | 0 | — |
| D | `nexus_agent/reasoning.py` | **未查** | — | ? | 兄弟模块 |

**import 证据**：
- `from nexus_agent.self_reflection.state_analyzer import StateAnalyzer` **1 次**
- `from nexus_agent.self_reflection.shared_state import SharedState` **1 次**
- `from nexus_agent.self_reflection.meta_controller import get_meta_controller` **1 次**
- `from nexus_agent.self_reflection.historical_analyzer import HistoricalAnalyzer` **1 次**
- `from nexus_agent.self_reflection.decision_logger import get_decision_logger` **1 次**
- `from nexus_agent.self_reflection.cost_estimator import CostEstimator` **1 次**
- `from nexus_agent.self_reflection.correl_tracer import CorrelTracer` **1 次**
- `from nexus_agent.self_reflection import get_self_reflection` **1 次**（顶层）
- `from nexus_agent.reasoning_chain import get_chain_executor` **1+1=2 次**

**运行证据**：
- data/self_reflection_progress.json + self_reflection_5rounds.json 存在
- 日志无 self_reflection.* logger 输出 — 模块本体未被实时驱动

**⚠️ 严重发现**：
- A 包 10 个子模块，**__init__.py 仅 2 行**（基本空）
- 所有 10 个子模块被独立 import 到一个总入口（很可能是 self_reflection.py 或 meta_cognition）
- **每个子模块功能边界模糊**，可能是早期过度拆分

**推荐保留**：
- 合并 A 的 10 个子模块为单个 `self_reflection.py`（约 1350L，可接受）

**删除/合并**：
- 删 A 包目录（__init__.py 已有 import 兼容路径）
- 内部类重新组织：
  - StateAnalyzer + SharedState → 合并为 `ReflectionState` 类
  - CostEstimator + CorrelTracer + DecisionLogger → 合并为 `ReflectionMetrics` 类
  - HistoricalAnalyzer + MetaController + Reasoner → 合并为 `ReflectionEngine` 类
  - LLMInterface + Trigger → 拆为独立 helper

**合并方案**：
1. 先 cat A 包每个子模块头部 docstring，理解职责
2. 按"状态/指标/引擎/接口"四象限重组
3. 保留外部 API（每个 import 点的符号）
4. 这是个**纯重构无行为变化**的工作

---

## 10. Consciousness — 3 处实现 🟡 全部空壳或被绕过

| 候选 | 路径 | 行数 | 文件 mtime | import 计数 | 谁先有 |
|---|---|---|---|---|---|
| A | `nexus_agent/consciousness/__init__.py` 77L + `engine.py` 526L | 603 | 2026-07-12 / 7月14 | **0** | 设计文档级别 |
| B | `nexus_agent/living_core/{alive_core,psi,identity,methodology,integration}.py` | 759 | 2026-07-12 ~ 7月13 01:46 | **5**（散落 import） | 设计完整但未 wire |
| C | `nexus_agent/identity_core/{consciousness_loop,identity_sampler,identity_trainer,integration}.py` | 651 | 2026-07-12 22:02~22:05 | **2**（其中 1 次在 nexus_gateway/run.py 启动 bootstrap_identity） | 启动时引导 |
| D | `nexus_agent/identity.py` | 180 | 2026-06-16 | **?**（active 入口） | 真正生效 |

**import 证据**：
- `from nexus_agent.living_core.psi import PSI` **1 次**
- `from nexus_agent.living_core.methodology import get_methodology_router` **1 次**
- `from nexus_agent.living_core.identity import get_identity` **1 次**
- `from nexus_agent.living_core.alive_core import get_alive / AliveCore` **2 次**
- `from nexus_agent.identity_core.identity_trainer import get_identity_trainer` **1 次**
- `from nexus_agent.identity_core.integration import bootstrap_identity` **2 次**（nexus_gateway/run.py 启动路径）
- consciousness/ 包 **0 次 import**

**运行证据**：
- 日志 00:40:49 `[Identity] Loaded 26291 weights` — 来自 `nexus.identity` (D)，**不是** identity_core (C)
- 日志 00:40:49 `[Alive] Heartbeat started` — **找到了 living_core 的运行证据**！之前误判
- consciousness/engine.py 有 526L 但无 logger 输出 → **设计文档级别**

**⚠️ 修正之前判断**：
- `living_core/alive_core.py` **实际是活的**（被 heartbeat_loop 调用，启动时 "Heartbeat started" 日志）
- 但 `consciousness/engine.py` 和 `identity_core/*` 大量未 wire

**推荐保留**：
- **B** `living_core/alive_core.py` 186L（active，AliveCore 类被引用）
- **D** `nexus_agent/identity.py` 180L（active 身份加载）

**删除/合并**：
- **A** `consciousness/__init__.py` + `engine.py`（0 import）→ **整包删除**（除非用作 design doc）
- **C** `identity_core/integration.py` 仅在启动路径被 import 1 次 → 评估
- `living_core/{psi, identity, methodology, integration}.py` → 评估（5 次 import，但都分散）

**合并方案**：
1. A 包先冻结成 design doc（`docs/CONSCIOUSNESS_DESIGN.md`），删 .py
2. C 包和 D 整合：把 identity_core 的功能并入 nexus_agent/identity.py
3. B 包保留 alive_core.py，其他 4 个文件归并到 alive_core 内部（作为内部类）

---

## 总结：10 组重复审计的优先级

| 优先级 | 组 | 删除价值 | 风险 | 备注 |
|---|---|---|---|---|
| 🔴 高 | 1 EventBus | 1 文件 (770L) | 低 | 3 处 import 已清晰可改 |
| 🔴 高 | 6 Knowledge Graph | 1 包 (310L) | 零 | 0 import |
| 🔴 高 | 7 Meta Cognition | 2 文件 (1145L) | 低 | 0 import 但要小心 facade |
| 🟡 中 | 3 Evolution | 1 文件 (1063L) | 中 | 必须先 grep 全部符号 |
| 🟡 中 | 4 Self Model | 1 包 (690L) | 低 | 1 处弱引用 |
| 🟡 中 | 5 User Model | 1 包 (519L) | 中 | 3 处 import 需逐一改 |
| 🟡 中 | 9 Self Reflection | 1 包 → 1 文件 (1350L) | 中 | 10 个子模块 import 散落 |
| 🟢 低 | 2 LLM Client | 1 文件 (273L) | 零 | 0 import 直接删 |
| 🟢 低 | 8 Autonomous Planner | 0 行（仅重命名） | 零 | 目录冲突命名 |
| 🟢 低 | 10 Consciousness | 1 包 (603L) + 评估 | 低 | consciousness 0 import |

**总可清理行数估计**：约 **6700 行死代码 / 重构目标行**

---

## 触发蓝莓追问（任务 D）

1. ✅ **Nexus 今天成功启动**（PID=11848，2026-07-15 00:27 启动，00:41:32 仍在运行），但有真实错误：
   - `name 'time' is not defined` Traceback（feishu_channel 模块）
   - 4 次 `reply send failed`（Feishu 通道）
   - 多次 minimax HTTP 529 overloaded
   - **8 次 `all_strategies_failed`**（Kai 的"你扫描完成再汇报"指令因 CONFIG 缺失被 cooldown 3600s 阻塞）

2. ⚠️ **疑似死代码**：196 个 .py 文件 mtime < 2026-06-01，其中大部分是 `nexus_cli/*` 和 `skills/*`（hermes 模板）。最确凿的 11 个文件在本文档列出（每组都标了 0 import 证据）。

3. ❌ **world_model 节点数 vs 边数对不上 + 不存在 527 节点**：
   - nodes.json: **20 节点**（不是 527，也不是 32M 数据）
   - edges.json: **23 边**，**14/23 指向同一 cluster c000000** → cluster 算法退化
   - knowledge_graph.json: **2 节点 / 1 边**（完全没用）
   - wordvecs.json: 33.8 MB（预训练模型加载，不是自建数据）
   - 运行日志 `wm_nodes=25→26` 与 20 不一致 → 可能是 in-memory 计数 vs disk 计数不同步
   - **建议**：等蓝莓确认是否要立即修 cluster 算法 + 增建节点，或者暂时接受当前规模（20 节点做玩具 demo）