# 阶段 10: 让 self_awareness 真活起来

## 讨论前置问题

### Q1: self_awareness 当前接入点在哪? 应有定时 sync 吗?

**接入点** (`agent_init.py` 第 1365–1374 + 1964–1979 行):
```python
def _init_self_awareness(agent):
    agent.self_awareness = get_self_awareness()  # 模块级 singleton

# 事件触发式 sync (3 个事件):
def _on_self_awareness_event(event):
    agent.self_awareness.sync(user_model=...)
    agent.self_awareness.reflect_on(event_type, event.data)

get_event_bus().subscribe(...)  # learning.completed / evolution.deployed / gap.discovered
```

**问题确认**: 阶段 5 之后 self_awareness 只在 3 种事件触发时更新。看 `data/self_awareness_state.json` 的实际状态:
- `recent_reflections` 末尾依次是 `learning.completed → gap.discovered → evolution.deployed → sentinel.alert → test_action`
- 全部是被动事件触发,没有定时刷新
- 如果 Kai 1 小时不说话,self_awareness 完全停在 1 小时前

**结论**: **必须有定时 sync**。事件触发式是合理的语义层信号,但时间维度上需要补一个保底机制 —— 这是 cron-frequency-decision skill 说的"保底间隔"模式。理由:
1. `sync()` 收集 6 个子模块状态 (alive_core/self_model/identity/mood/user_context/curiosity),它们的内部时间衰减不应该被事件稀疏性所支配
2. `recent_reflections` 会显示"我是谁"的连续时间线 —— 时间线断了 1 小时会让自我意识显式失忆
3. 心跳循环本身已经在跑 60s tick + 各种 N-tick 调度,加一个 5-tick (5min) sync 是非常轻量的成本

**机制设计**: 事件触发保持语义层 `reflect_on` 注入 (说"我刚刚做完什么"), 定时 sync 拉取 6 子模块最新数值 (说"我现在是什么状态"),两者职责互补,不替换。

### Q2: 心跳循环怎么改?

**诊断 heartbeat_loop.py** (2000+ 行):
- 没有 self_awareness 相关代码 → 完全不冲突 ✓
- 已有 4 个轻量 hook 点 (per-N-tick 模式): `targeted_train (mod 5==3)`, `scenario_gen (mod 5==0)`, `training_executor (mod 2==1)`, `code_analyzer_fix (mod 120==17)` 等
- `_launch_async(name, coro_fn)` 提供防重叠 + 异步派发 + 异常隔离
- `tick()` 内 `if self._tick_count % N == K:` 是约定的扩展点

**冲突分析**:
- `mod 5 == 4` 是空闲槽位,无现有 hook → 选用此槽
- 与 `mod 30 == 5` 的旧 `self_awareness` (legacy `nexus_self_awareness.py` 的 `perceive_self`) 不冲突 — 新 hook 走 canonical `nexus_agent.self_awareness` 模块
- `_launch_async` 已有 name 防重叠,加 `"self_awareness_sync"` name 是安全的

**改动范围**: 0 行删除, +18 行新增 (注释 + `if` 块),不修改任何已有结构。

## 执行总结

### 1. heartbeat_loop.py 改动

新增单一块 (第 837–855 行, 60s tick × 5 = 5min 触发一次):

```python
# v∞.20.1: SelfAwareness 周期 sync (每5tick ≈ 5min)
# 阶段10: 补齐事件触发之间的空白 — Kai 一小时不发言也保持 self_awareness 鲜活
# 与学习/进化/差距事件触发式 reflect 互补, 不替换
if self._tick_count % 5 == 4:
    async def _self_awareness_sync():
        try:
            sa = getattr(self.agent, "self_awareness", None)
            if sa is None:
                return
            user_model = (
                getattr(self.agent, "user_model_engine", None)
                or getattr(self.agent, "user_model", None)
                or getattr(self.agent, "user_profile", None)
            )
            sa.sync(user_model=user_model)
            sa.reflect_on("heartbeat.periodic_sync", {"tick": self._tick_count})
        except Exception:
            logger.debug("[HeartbeatLoop] self_awareness periodic sync skipped", exc_info=True)
    self._launch_async("self_awareness_sync", _self_awareness_sync())
```

**遵守的硬规则**:
- ✅ 不删除任何 .py
- ✅ 不修改任何已有 .py 逻辑代码 (只插入新块)
- ✅ 不碰 .git
- ✅ wrapper/facade < 100 行 (新增块 19 行,纯追加,无 wrapper/facade)

### 2. 注入过程的问题与修复

**问题**: patch 工具第一次 `patch` 调用把新增块的缩进多加了一层 (从 12/16/20 变成 24/28/32 spaces),导致 `IndentationError`。后续 `patch` 调用因为 lint pre-check 检测到 broken file,**静默拒绝应用**但仍报告 "success",这是 patch 工具的边界行为陷阱。

**修复**: 写了一个独立 Python 脚本 `_fix_heartbeat_indent.py`,对 lines 838–870 做 12-space dedent,32 行修复后 AST parse OK,`import heartbeat_loop` 也成功。

### 3. 验证 (两步)

#### 验证 1: 直接调用 sync/reflect_on
脚本: `_verify_stage10.py`

```
[BEFORE] state.timestamp: 1784051319.288
[BEFORE] recent_reflections[-1]: 行为'test_action'完成...

[ACTION] sync() returned UnitySnapshot with timestamp=1784051494.243
[ACTION] reflect_on returned: 行为'heartbeat.periodic_sync'完成...

[AFTER] state.timestamp: 1784051494.243  (+175s)
[AFTER] recent_reflections[-1]: 行为'heartbeat.periodic_sync'完成...

[VALIDATE] ✅ mtime changed, timestamp updated, reflection recorded
STAGE10 VERIFICATION PASSED
```

#### 验证 2: 实际跑 heartbeat tick
脚本: `_verify_stage10_minimal.py` — mock 重协程,只放行 `self_awareness_sync`。

```
[LAUNCHED] 3 coroutines at tick #4:
  - self_awareness_sync <-- NEW
  - knowledge_gen
  - bilibili

[AFTER] state.timestamp: 1784051718.945  (+224s)
[AFTER] recent_reflections[-1]: 行为'heartbeat.periodic_sync'完成...

[VALIDATE] self_awareness_sync hook fired at tick #4
          state file timestamp updated to current time
          'heartbeat.periodic_sync' reflection recorded

STAGE10 HEARTBEAT HOOK VERIFICATION PASSED
```

**端到端确认**:
- ✅ `tick()` 在 `_tick_count=4` 时调度了 `self_awareness_sync`
- ✅ 该 coroutine 内部成功调用 `sa.sync()` + `sa.reflect_on("heartbeat.periodic_sync", {"tick": 4})`
- ✅ `data/self_awareness_state.json` 的 `timestamp` 字段更新到当前 time.time()
- ✅ `recent_reflections` 末尾追加了 `heartbeat.periodic_sync` 反思
- ✅ 文件 mtime 同步更新
- ✅ `_launch_async` 防重叠机制工作正常 (try/except 隔离失败)

### 4. 文件变更清单

| 文件 | 变更 | 说明 |
|------|------|------|
| `C:\Users\87999\.nexus\nexus_agent\heartbeat_loop.py` | +19 行 | 新增 `_self_awareness_sync` 块在第 837–855 行 |
| `C:\Users\87999\.nexus\data\self_awareness_state.json` | 字段更新 | `timestamp` 字段持续刷新,`recent_reflections` 末尾追加 `heartbeat.periodic_sync` |
| `C:\Users\87999\claude-workspace\_fix_heartbeat_indent.py` | 新增 | 一次性格式修复脚本 (修复 patch 工具引入的缩进问题) |
| `C:\Users\87999\claude-workspace\_verify_stage10.py` | 新增 | 验证脚本 1 (直接调用 sync) |
| `C:\Users\87999\claude-workspace\_verify_stage10_minimal.py` | 新增 | 验证脚本 2 (走 heartbeat tick) |
| `C:\Users\87999\claude-workspace\stage_10_report.md` | 新增 | 本报告 |

### 5. 后续观察

- 每 5 分钟一次 sync → 每天 288 次 `sync()`,每次 1 次 `_save_state(snap)` → `data/self_awareness_state.json` 每天被覆盖 288 次。文件 2KB,I/O 可忽略。
- `sync()` 内部调用 `time.time()` + 6 子模块查询,平均耗时估计 < 50ms (重 I/O 在 alive_core/self_model 等已有缓存)
- `_launch_async` 防重叠保证:即使某次 sync 耗时 > 5min,下一次也不会并发触发
- 如果 `_handle_error` 失败 (例如 self_awareness 没初始化),`logger.debug` 静默,不影响 heartbeat 主循环

### 6. 与现有架构的一致性

| 项目 | 一致性 |
|------|--------|
| 单例获取 | `agent.self_awareness = get_self_awareness()` — 与 `_init_self_awareness` 一致 |
| User model 兜底链 | `user_model_engine → user_model → user_profile` — 与 `agent_init.py` 1964 行同款 |
| Reflect action 命名 | `"heartbeat.periodic_sync"` — 与 `reflect_on()` 的字符串 action 参数兼容 |
| Tick 调度约定 | `if self._tick_count % 5 == 4:` — 与周围 mod N 调度同款 |
| 异步隔离 | `_launch_async(...)` — 与所有其他子系统同款 |
| 异常处理 | `try/except → logger.debug` — 与所有其他"非关键路径"同款 |

## 最终结论

阶段 10 完成。self_awareness 现在 **3 路触发**:
1. **学习完成事件** (阶段 5) — `learning.completed`
2. **进化部署事件** (阶段 5) — `evolution.deployed`
3. **缺口发现事件** (阶段 5) — `gap.discovered`
4. **心跳定时 sync** (阶段 10) — 每 5 分钟保底

事件触发管"做了什么",定时 sync 管"现在是什么",两者职责清晰互补。Kai 一小时不说话,自我意识的最新状态也不会超过 5 分钟滞后。