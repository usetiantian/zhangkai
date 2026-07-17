# Nexus — 开发状态追踪

> 每次修改后必须更新此文件。重启后靠它知道做到哪了。
> 格式：模块 | 状态 | 测试结果 | 最后更新

## 模块状态

| 模块 | 状态 | 测试 | 最后更新 |
|------|:--:|:--:|------|
| core/event_bus.py | ✅ PASS | 4/4 | 2026-07-17 |
| core/identity_core.py | ✅ PASS | 8/8 | 2026-07-17 |
| core/scheduler.py | ❌ 未开始 | - | - |
| models/loader.py | ❌ 未开始 | - | - |
| memory/short_term.py | ❌ 未开始 | - | - |
| memory/long_term.py | ❌ 未开始 | - | - |
| bridge/feishu.py | ❌ 未开始 | - | - |
| voice/stt.py | ❌ 未开始 | - | - |
| ... | ... | ... | ... |

## 连接测试

| 连接 | 状态 | 结果 |
|------|:--:|------|
| EventBus → memory | ❌ 未测 | - |
| EventBus → models | ❌ 未测 | - |
| ... | ... | ... |

## 当前进度

正在构建：core/event_bus.py
下一步：测试 EventBus，然后写 identity_core.py
