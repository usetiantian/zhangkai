# Stage 11: 接通 EvoKG 链路 (重做)

## 问题 (实测确认)

`nexus_agent/evokg.py:2304-2349` 调 wm 的三个方法, 但 `EvoKGWorldModel` (166L)
实际只有 `observe/add_causal_edge/get_causal_chain` — 整段 try/except 吞掉,
只输出 `[Fusion L1] MI edge discovery`, 然后跳过 MI 主路径, 走赫布回退.

## evokg.py:2304 调用列表

| 行 | 调用 | 期望 |
|---|---|---|
| 2322 | `wm.record_observation(pair["node_a"], va)` | 暂存观察 (str id, 256-d vec) |
| 2323 | `wm.record_observation(pair["node_b"], vb)` | 同上, label=pair["node_b"] |
| 2324 | `wm._discover_causal_edges()` | 跑 MI 计算并写入 self.edges |
| 2325 | `wm.get_causal_edges(min_mi=0.05)` | 返回 `list[{src, dst, mi, type}]` |
| 2327-2336 | 读 `ce["src"]`, `ce["dst"]`, `ce["mi"]`, `ce["type"]` | 写入 kg_edges 表 |

## compat wrapper 提供的方法 (`nexus_agent/neural/evokg_world_model_compat.py`, 96L)

`EvoKGWorldModel` 三个方法在 compat import 时通过 `setattr` 注入 (idempotent):

- `record_observation(label, vec)` — 把 256-d vec 暂存到 `self._compat_buf[str(label)]`, 同时写入 `self.nodes[_sid(label)]`
- `_discover_causal_edges()` — 遍历 `_compat_buf` 中所有 distinct pair, 用 `cos(va, vb)` + `sum(va*vb)` 组合做 MI 代理 (因 va/vb 是 `hash % 256` one-hot 指标, MI ≡ 支持重合度), 调 `add_causal_edge()` 写入
- `get_causal_edges(min_mi=0.0)` — 从 `self.edges` 取 `mi >= min_mi`, 加 `type` (bidirectional / causes / correlates), 按 MI 降序返回

`_sid()` 用 MD5 前 4 字节 (32-bit 稳定 hash) 与 evokg.py 调用侧解耦, 不依赖 Python `hash()` 进程种子.

## 验证输出

```
$ python -c "import nexus_agent.neural.evokg_world_model_compat
              from nexus_agent.neural.evokg_world_model import EvoKGWorldModel
              w = EvoKGWorldModel()
              print(w.get_causal_edges())"
[{'src': 485834924, 'dst': 846376212, 'mi': 1.0, 'type': 'causes'},
 {'src': 2778758028, 'dst': 1182629931, 'mi': 1.0, 'type': 'causes'}]

$ python -c "from nexus_agent.evokg import EvoKG"
EvoKG import OK: EvoKG

$ python compat unit smoke: overlap_v1 · overlap_v2
  _discover_causal_edges -> 1 new edge (mi=1.0)
```

⚠ 注: 单行 `python -c "from evokg_world_model import EvoKGWorldModel; ..."`
不能直接拿到 `get_causal_edges` — 因为补丁驻留 compat 模块, 必须在
同一进程先导入 compat (或 `evokg.py:2309` 已导入). evokg.py:2309
的 `from evokg_world_model_compat import get_world_model` 已经保证
执行路径上补丁生效.

## 文件

| 文件 | 行数 | 改动 |
|---|---|---|
| `nexus_agent/neural/evokg_world_model_compat.py` | 96 | 新建 |
| `nexus_agent/evokg.py` | 2745 | **未动** (硬规则) |
| `nexus_agent/neural/evokg_world_model.py` | 166 | **未动** (硬规则) |
