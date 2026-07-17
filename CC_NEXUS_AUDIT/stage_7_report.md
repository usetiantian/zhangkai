# Nexus 架构合并 阶段 7 报告 (2026-07-15)

> 执行者: Claude Code (delegated subagent via 蓝莓)
> 范围: 能力 1/2/3/5 facade 化 (4 个 `__init__.py`)
> 已知基础: 35 候选已验证 (阶段 6), 全部分层, 0 真重复; 主入口已判定; Q3 链路已查 (learning↔thinking 通, 自改→学习没连, 不硬连)
> 阶段 7 状态: ✅ 完成 (4 个新 facade + 2 处 spec 符号名修正 + 12 符号 same-identity 验证)

---

## 讨论前置问题 (Q1-Q3, 源码验证后回答)

### Q1: 4 个能力 facade 化是否值得 (跟阶段 6 能力 4 一致思路)

**结论: 值得, 但要保留 facade 的纯 index 性质 (跟阶段 6 的 `self_optimization.py` 一脉相承)**.

理由:
1. **能力 4 (自优化) 已有先例**: 阶段 6 创建了 `self_optimization.py` 89L facade-index, 80 个符号 re-export, 单源真实. 阶段 7 给能力 1/2/3/5 各开一个 facade-package 是延续同模式, 让"能力 N → 统一入口"对未来 caller 一致.
2. **能力 1 (自主学习) 的 5 子源散落**: `self_play/` (package) + `self_play_engine.py` (sibling module) + `learning_engine/` + `curiosity_core/` + `auto_learner.py`. **没有任何 caller 现在统一用 `from nexus_agent.learning import ...`**; new caller 想摸"学习能力"得知道 5 个独立路径. facade 把这 5 路径收敛为一个入口.
3. **能力 2 (自主思考) 2 子源**: `cognitive_loop/` + `intention_engine.py`. 同样无统一入口. 收敛价值同上.
4. **能力 3 (自主进化) 2 子源**: `evolution_engine.py` + `evolution_decision_engine.py`. 命名问题: `evolution` 是 Python keyword 不能直接当包名. **用 `evolving` (动名词, 非 keyword)** 解决.
5. **能力 5 (自改代码) 2 子源**: `self_modifier/` + `sandbox.py`. 同样.

**所以 facade 化不是"为统一而统一"**, 是给 caller 提供"能力 N 入口"的一致语义, **同时不改变 canonical 的 single-source-of-truth 地位**.

### Q2: 4 个 facade 的实现是 facade-index (阶段 6 模式) 还是 wrapper (伪合并)?

**结论: 严格 facade-index, 跟阶段 6 完全一致**.

具体:
- 4 个 `__init__.py` 全部是 **纯 import + `__all__`**, **0 业务逻辑**.
- 4 个文件最大 25 行, 最小 16 行, **全部 < 100 行** (硬规则 4).
- **0 修改任何 canonical**: 验证 10 个 canonical 文件 mtime + md5 完全不变 (见下方验证章节).
- **0 反向引用**: 没有 canonical 来 import 4 个 facade (facade 是 leaf, 不是 hub).

### Q3: EventBus 是否要在这 4 个 facade 里硬连?

**结论: 不连**. 跟阶段 5/6 一致: 接线放在现有中央 `_setup_event_subscribers()`.

理由:
1. **阶段 5 决策**: self_awareness 订阅 3 个上游 topic (`learning.completed` / `evolution.deployed` / `gap.discovered`). 这些事件的**发布者是上游** (autonomous_planner, auto_learner, evolution_engine, gap_analyzer), 不是 facade.
2. **阶段 6 决策**: 自优化层作为上游发布 4 类事件 (`meta.health.report` 等), 但**当前不发布** self_awareness 关心的 3 个 topic. 那是上游 learning/evolution 能力的职责, **不在能力 4 范围内**.
3. **阶段 7 决策**: 4 个 facade 是纯 index, 不引 event wiring. 任何 `bus.publish_sync` / `bus.subscribe_sync` 都不应进 `__init__.py`. 真实接线在 `agent_init._setup_event_subscribers()` 里 (阶段 5 已存在).
4. **facade 内若写 EventBus 调用**: 会 (a) 引入 module-level side effect (import 时就订阅) 破坏 lazy import 模式; (b) 跟阶段 5 中心化决策冲突. **禁止**.

---

## 反对/修正 spec 草稿的 2 处

派单里的 spec 草稿是**模板**, 不是 ground truth. 源码验证后发现 2 处需要修正, 我没有硬连错路径:

| # | spec 草稿写的 | 实际 canonical (dir() 验证) | 修正 |
|---|--------------|---------------------------|------|
| 1 | `from nexus_agent.self_play import SelfPlayEngine` | `SelfPlayEngine` **不在 `self_play/` 包里**, 而在 sibling module `nexus_agent.self_play_engine`. `self_play/__init__.py` 只 re-export `SelfPlayDomain` | facade 改为 `from nexus_agent.self_play_engine import SelfPlayEngine`. 验证: `self_play.SelfPlayDomain is self_play_engine.SelfPlayDomain = True` (同源 class), `SelfPlayEngine` 只在 self_play_engine |
| 2 | `from nexus_agent.cognitive_loop import CognitiveLoopModule` | `cognitive_loop/__init__.py` 没有 `CognitiveLoopModule`. 实际导出是 `NexusCognitiveLoop` (class) | facade 改为 `from nexus_agent.cognitive_loop import NexusCognitiveLoop`, 并同时把 `CognitiveLoopModule = NexusCognitiveLoop` 作为**别名**导出, 这样 spec 草稿写的 `from nexus_agent.thinking import CognitiveLoopModule` 也能 work (兼容性) |

**这两个修正都不是硬改主入口** (硬规则 2), 是**修正 facade 内的 import 路径指向正确 canonical**. Canonical 文件本身 0 改动.

**注意**: 若蓝莓希望 facade 严格 0 适配 (例如要求 `CognitiveLoopModule` 必须叫 `CognitiveLoopModule` 而非别名), 那么应该改 canonical (`cognitive_loop/__init__.py`) 加 `CognitiveLoopModule = NexusCognitiveLoop` alias. 但本阶段 spec 是**只新建 facade**, 不改 canonical, 所以我选择 facade 内 alias. 这是**遵守硬规则 2 (不修改任何主入口逻辑代码)** 的唯一办法.

---

## 任务执行

### 任务清单

- [x] 创建 4 个 facade `__init__.py` (`nexus_agent/learning/`, `thinking/`, `evolving/`, `self_modifying/`)
- [x] 4 个 facade 都 < 100 行 (max 25 行, min 16 行, 总 84 行)
- [x] 4 个 facade 都是纯 import + `__all__`, 0 业务逻辑
- [x] `python -c "import nexus_agent.learning"` 通过
- [x] `python -c "import nexus_agent.thinking"` 通过
- [x] `python -c "import nexus_agent.evolving"` 通过
- [x] `python -c "import nexus_agent.self_modifying"` 通过
- [x] 12 个 facade 符号全部 same-identity `is` 各自 canonical
- [x] 10 个 canonical 文件 mtime + md5 完全未改
- [x] 0 主入口逻辑代码改动 (硬规则 2)
- [x] 0 `.py` 删除 (硬规则 1)
- [x] 0 git 操作 (硬规则 3)

### 文件改动明细 (仅 4 个新文件)

| 文件 | 行数 | 角色 | 设计 |
|------|------|------|------|
| `nexus_agent/learning/__init__.py` | **25** | 能力 1 facade | 5 符号 re-export: SelfPlayDomain (from self_play), SelfPlayEngine (from self_play_engine), LearningModule, CuriosityCoreModule, get_auto_learner |
| `nexus_agent/thinking/__init__.py` | **24** | 能力 2 facade | 3 符号 re-export: NexusCognitiveLoop, CognitiveLoopModule (alias to NexusCognitiveLoop for spec compatibility), get_intention_engine |
| `nexus_agent/thinking/__init__.py` | **24** | 能力 2 facade | 3 符号 re-export: NexusCognitiveLoop, CognitiveLoopModule (alias to NexusCognitiveLoop for spec compatibility), get_intention_engine |
| `nexus_agent/evolving/__init__.py` | **19** | 能力 3 facade | 2 符号 re-export: EvolutionEngine, EvolutionDecisionEngine. 包名用动名词 `evolving` 避 keyword `evolution` |
| `nexus_agent/self_modifying/__init__.py` | **16** | 能力 5 facade | 2 符号 re-export: SafeSelfModifier, get_sandbox |

**总新增代码: 84 行**, 全部 facade-index, 0 业务逻辑.

#### 改写文件 (0)

**全部 10 个 canonical 文件 mtime / 内容未动** (实证见下方验证章节).

### 验证清单 (蓝莓要求, 逐条核对)

| 检查项 | 状态 | 证据 |
|--------|------|------|
| 4 个 facade 都 < 100 行 | ✅ | learning=25, thinking=24, evolving=19, self_modifying=16 |
| 4 个 facade 都是纯 import + `__all__` | ✅ | 见各文件内容, 0 def / 0 class / 0 业务代码 |
| `python -c "import nexus_agent.learning"` 通过 | ✅ | 见下方验证 1 |
| `python -c "import nexus_agent.thinking"` 通过 | ✅ | 见下方验证 1 |
| `python -c "import nexus_agent.evolving"` 通过 | ✅ | 见下方验证 1 |
| `python -c "import nexus_agent.self_modifying"` 通过 | ✅ | 见下方验证 1 |
| 10 个 canonical 文件 mtime 没动 | ✅ | 验证 3: 10/10 mtime + md5 与基线完全一致 |
| 主入口未被自动合并 | ✅ | 0 canonical 文件逻辑代码改动 |
| facade symbol = canonical symbol (same identity) | ✅ | 验证 2: 12/12 `is` 检查通过 |

---

## 验证证据 (执行后)

### 验证 1: 4 个 facade import

```text
OK   import nexus_agent.learning
OK   import nexus_agent.thinking
OK   import nexus_agent.evolving
OK   import nexus_agent.self_modifying
```

### 验证 2: 12 个 facade 符号 same-identity (facade `is` canonical)

```text
OK   SelfPlayDomain: facade is canonical = True
OK   SelfPlayEngine: facade is canonical = True
OK   LearningModule: facade is canonical = True
OK   CuriosityCoreModule: facade is canonical = True
OK   get_auto_learner: facade is canonical = True
OK   NexusCognitiveLoop: facade is canonical = True
OK   CognitiveLoopModule (alias): facade is canonical = True
OK   get_intention_engine: facade is canonical = True
OK   EvolutionEngine: facade is canonical = True
OK   EvolutionDecisionEngine: facade is canonical = True
OK   SafeSelfModifier: facade is canonical = True
OK   get_sandbox: facade is canonical = True
```

### 验证 3: 10 个 canonical 文件 mtime + md5 完全未改

| Canonical | mtime (epoch) | mtime OK | md5 | md5 OK |
|-----------|---------------|----------|-----|--------|
| `nexus_agent/self_play/__init__.py` | 1784042006 | ✅ | `655e48c8f4a54b6311d3efaed8623439` | ✅ |
| `nexus_agent/learning_engine/__init__.py` | 1783408803 | ✅ | `7203feb32f47b9a421f1b35c833c3166` | ✅ |
| `nexus_agent/curiosity_core/__init__.py` | 1783836585 | ✅ | `4b6fbafe961b3f1211c75e1a85c2555f` | ✅ |
| `nexus_agent/auto_learner.py` | 1783976404 | ✅ | `c8fd6b5a85e1a8a6f1e59fd2c925d460` | ✅ |
| `nexus_agent/cognitive_loop/__init__.py` | 1783980074 | ✅ | `2c0e0fb787b50841a31f102fcfa8d0f8` | ✅ |
| `nexus_agent/intention_engine.py` | 1783974198 | ✅ | `e0d7235f434d9df1f263275fe3fb344b` | ✅ |
| `nexus_agent/evolution_engine.py` | 1784002147 | ✅ | `57bc2de4cc218e4a7e064b79c1fc706a` | ✅ |
| `nexus_agent/evolution_decision_engine.py` | 1783507369 | ✅ | `7a242067a11d50c3e390fa0eeca74f09` | ✅ |
| `nexus_agent/self_modifier/__init__.py` | 1781544869 | ✅ | `bbafac3ce66243b44963275a946150a8` | ✅ |
| `nexus_agent/sandbox/__init__.py` | 1783567274 | ✅ | `87f34d87d35dd1e2d0aee47991ee04e2` | ✅ |

**结论: 10/10 canonical 文件完全未动** (mtime + md5 与阶段 6 基线一致).

---

## 跟阶段 5/6 的协调说明

### 阶段 5 (能力 8 自我意识): 中心化 event wiring

阶段 5 决策:
- self_awareness 选 **C 混合**: EventBus 订阅触发 `sync() + reflect_on()`, 显式查询继续走 `express_state()`
- 订阅事件: `learning.completed`, `evolution.deployed`, `gap.discovered`
- **接线放在现有中央 `_setup_event_subscribers()`**

**对阶段 7 的影响**:
- 阶段 7 创建的 4 个 facade (`learning/`, `thinking/`, `evolving/`, `self_modifying/`) **不发布**也不**订阅**任何 EventBus 事件.
- 这是有意的: 上游发布者是 `auto_learner.py` / `evolution_engine.py` / `gap_analyzer/` 等 canonical 实体, 不是 facade 聚合层.
- facade 是**纯 leaf index**, 跟 `_setup_event_subscribers()` 完全无耦合.

### 阶段 6 (能力 4 自优化): facade-index 模式 + 0 反向依赖

阶段 6 决策:
- 创建 `self_optimization.py` 89L facade-index, 80 个符号 re-export
- **0 反向引用**: 没有 canonical 来 import facade
- 35/35 老路径 + 1/1 新 facade 全部 import OK
- 单例一致性 (facade === canonical same identity) 验证通过

**对阶段 7 的延续**:
- 阶段 7 是阶段 6 模式的**复制到其他能力**: 能力 1/2/3/5 同样 facade-index 风格.
- 验证同样: **0 反向引用** + **same-identity 全通过** + **canonical mtime 不变**.
- 阶段 6 把 35 个候选决策成 KEEP (0 真重复), 阶段 7 接受这个判定, **不重新分类**, 只做 facade 化.

### Q3 链路 (learning↔thinking 通, 自改→学习没连)

派单说"Q3 链路已查: learning↔thinking 通, 自改→学习没连, 不硬连". 阶段 7 决策:

1. **`learning` facade 和 `thinking` facade 之间无直接 import**. learning 跟 thinking 的连接是上游模块 (例如 `auto_learner` 训练完成后触发 cognitive_loop 反思) 走 EventBus, 不在 facade 层.
2. **`self_modifying` facade 到 `learning` facade 无 import**. 自改→学习这条路径**当前不存在**, 阶段 7 不创造新路径. 这是符合派单要求的"不硬连".

---

## 风险与决策点 (供蓝莓决策)

### 1. spec 草稿的 2 处符号名错误

派单给的 spec 草稿里 2 处跟实际 canonical 不匹配:
- `SelfPlayEngine` 不在 `self_play/`, 在 `self_play_engine.py`
- `CognitiveLoopModule` 不在 `cognitive_loop/`, 是 `NexusCognitiveLoop`

**我没有硬改 canonical** (硬规则 2), 改的是 facade 内的 import 路径. **也没有硬阻塞**: 修正在 facade 内部完成, 对未来 caller 透明.

若蓝莓希望 facade **严格按 spec 命名**, 唯一办法是改 canonical 加 alias (例如 `cognitive_loop/__init__.py` 里加 `CognitiveLoopModule = NexusCognitiveLoop`). 这超出本阶段 spec (只新建 facade), 留待阶段 8/9 决策.

### 2. `evolving` 包名不是 `evolution`

派单已经预警: `evolution` 是 Python keyword. 用动名词 `evolving` 解决. 这意味着 `nexus_agent.evolving` ≠ `nexus_agent.evolution` (后者会 SyntaxError). caller 必须用 `evolving`.

**没有歧义**: 阶段 7 没用 `evolution` (避免 keyword), 用 `evolving` 是唯一 Python-legal 选择.

### 3. 阶段 7 跟阶段 6 模式一致性

阶段 6 + 阶段 7 一起构成了"能力 N facade-index"模式:
- 能力 4: `nexus_agent.self_optimization` (89L, single-file, 80 符号)
- 能力 1: `nexus_agent.learning` (25L, package, 5 符号)
- 能力 2: `nexus_agent.thinking` (24L, package, 3 符号)
- 能力 3: `nexus_agent.evolving` (19L, package, 2 符号)
- 能力 5: `nexus_agent.self_modifying` (16L, package, 2 符号)

**package vs single-file 不一致**: 阶段 6 用 single-file, 阶段 7 用 package. 这是因为阶段 6 的 canonical 全部是 module (不是 package), 阶段 7 的 canonical 既有 module 又有 package. **保持跟 canonical 结构一致**, 不强行统一 single-file.

### 4. 4 个 facade 的 __init__.py 内容 (最终落盘)

#### A) `nexus_agent/learning/__init__.py` (25 行)
```python
"""Facade — 能力 1 自主学习统一入口.
This is a compatibility facade. See self_play/, learning_engine/, curiosity_core/, auto_learner.py for canonical implementations.

Canonical sources:
  - SelfPlayDomain       → nexus_agent.self_play         (package)
  - SelfPlayEngine       → nexus_agent.self_play_engine  (sibling module, not the package)
  - LearningModule       → nexus_agent.learning_engine
  - CuriosityCoreModule  → nexus_agent.curiosity_core
  - get_auto_learner     → nexus_agent.auto_learner

This facade does NOT auto-wire EventBus between learning and other capabilities.
EventBus subscription lives in agent_init._setup_event_subscribers() per stage 5.
"""
from nexus_agent.self_play import SelfPlayDomain
from nexus_agent.self_play_engine import SelfPlayEngine
from nexus_agent.learning_engine import LearningModule
from nexus_agent.curiosity_core import CuriosityCoreModule
from nexus_agent.auto_learner import get_auto_learner

__all__ = [
    "SelfPlayDomain",
    "SelfPlayEngine",
    "LearningModule",
    "CuriosityCoreModule",
    "get_auto_learner",
]
```

#### B) `nexus_agent/thinking/__init__.py` (24 行)
```python
"""Facade — 能力 2 自主思考统一入口.
This is a compatibility facade. See cognitive_loop/, intention_engine.py for canonical implementations.

Canonical sources:
  - NexusCognitiveLoop   → nexus_agent.cognitive_loop   (the actual exported class;
                                                         spec sketch named it "CognitiveLoopModule"
                                                         but the canonical is `NexusCognitiveLoop`)
  - get_intention_engine → nexus_agent.intention_engine

This facade does NOT auto-wire EventBus. EventBus wiring lives in
agent_init._setup_event_subscribers() (stage 5 design).
"""
from nexus_agent.cognitive_loop import NexusCognitiveLoop
from nexus_agent.intention_engine import get_intention_engine

# Re-export under the spec name so any caller that imports
# `from nexus_agent.thinking import CognitiveLoopModule` (per _spec_v1.md sketch)
# can also resolve to the canonical NexusCognitiveLoop class.
CognitiveLoopModule = NexusCognitiveLoop

__all__ = [
    "NexusCognitiveLoop",
    "CognitiveLoopModule",
    "get_intention_engine",
]
```

#### C) `nexus_agent/evolving/__init__.py` (19 行)
```python
"""Facade — 能力 3 自主进化统一入口.

Package name `evolving` (gerund) is intentionally chosen to avoid the Python
keyword `evolution` while still being a readable capability facade.

Canonical sources:
  - EvolutionEngine            → nexus_agent.evolution_engine
  - EvolutionDecisionEngine    → nexus_agent.evolution_decision_engine

This facade does NOT auto-wire EventBus. EventBus wiring for evolution
topic `evolution.deployed` lives in agent_init._setup_event_subscribers()
(stage 5 design).
"""
from nexus_agent.evolution_engine import EvolutionEngine
from nexus_agent.evolution_decision_engine import EvolutionDecisionEngine

__all__ = [
    "EvolutionEngine",
    "EvolutionDecisionEngine",
]
```

#### D) `nexus_agent/self_modifying/__init__.py` (16 行)
```python
"""Facade — 能力 5 自改代码统一入口.
This is a compatibility facade. See self_modifier/, sandbox/ for canonical implementations.

Canonical sources:
  - SafeSelfModifier  → nexus_agent.self_modifier
  - get_sandbox       → nexus_agent.sandbox

NOTE: Stage 6 Q3 found that self_modification → learning is NOT wired.
This facade does not introduce that wiring (intentional, per spec).
"""
from nexus_agent.self_modifier import SafeSelfModifier
from nexus_agent.sandbox import get_sandbox

__all__ = [
    "SafeSelfModifier",
    "get_sandbox",
]
```

---

## 阶段 7 状态: ✅ 完成 (用户/Kai 视角)

**完成的事**:
1. ✅ 4 个新 facade `__init__.py` 落盘 (learning=25L, thinking=24L, evolving=19L, self_modifying=16L, 共 84 行)
2. ✅ 4/4 `python -c "import"` 通过
3. ✅ 12/12 facade 符号 same-identity (facade `is` canonical) 验证通过
4. ✅ 10/10 canonical 文件 mtime + md5 完全不变
5. ✅ spec 草稿 2 处符号名错误已修正 (SelfPlayEngine 路径 + CognitiveLoopModule 别名), 0 修改任何 canonical
6. ✅ 跟阶段 5/6 协调一致: 不硬连 EventBus, 中心化接线留给 `_setup_event_subscribers()`
7. ✅ Q3 链路决策保留: learning↔thinking 通过上游模块走 EventBus (不在 facade 层), 自改→学习不连

**没做的事 (合规)**:
- 0 个 .py 被删除 (硬规则 1)
- 0 个 .py 逻辑代码被改 (硬规则 2; 4 个 facade 完全是新文件, 不改任何 canonical)
- 0 个 git 操作 (硬规则 3)
- 0 个 EventBus 接线写入 facade (跟阶段 5/6 一致: 接线留给 `_setup_event_subscribers()`)
- 0 个 wrapper 创建 (facade-index 不是 wrapper, 跟阶段 6 一致)

**总耗时**: 约 8 分钟 (蓝莓预估 30-60 分钟内)

**报告落盘**: `C:\Users\87999\claude-workspace\CC_NEXUS_AUDIT\stage_7_report.md` ✅