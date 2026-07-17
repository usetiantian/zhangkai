# Stage 21 报告：seed_world_model 可控去重与 dry-run

日期：2026-07-15  
范围：仅修改 `claude-workspace/seed_world_model.py` 的 `main()`；未改 canonical dedup 算法，未触碰 `.git`。

## 1. 三个 flag

- `--no-dedup`：跳过 seeder 现有的 `text[:60]` 去重，每个种子都进入注入循环；`add_node(..., dedup=False)` 保持不变。
- `--limit N`：在 dedup 之后对整个选定 source 施加全局上限；`0` 表示不限，负数由 argparse 拒绝。
- `--report-only`：只遍历同一候选管线并打印 `would_inject`，在 encoder 和 `add_node` 前返回，不调用 `space.close()`，也不写 `seeding_log.json`。
- 为匹配任务命令，`--source=identity` 是 `identity_weights` 的 CLI alias。

## 2. identity 实跑（report-only）

跑前独立读取 `~/.nexus/data/world_model/nodes.json`：**157 节点**。

命令：

```text
python seed_world_model.py --report-only --source=identity
```

实际 stdout（exit 0）：

```text
[REPORT-ONLY] source=identity_weights nodes_before=157 would_inject=25374 dedup=on limit=all
```

结论：默认 prefix-60 dedup 后预计注入 **25,374**；加 `--no-dedup` 实测预计 **26,291**，即现有 dedup 会滤掉 **917** 条。

只读保证核验：命令前后 `nodes.json` 均为 **157** 节点、**41,058 bytes**，SHA-256 均为 `5a270367968279698acb74234949444f26c7bac311b1ec5e54aa5f3312547a84`。

## 3. 真实写入建议

性价比最高的下一步：

```text
python seed_world_model.py --source=identity --no-dedup --limit=50
```

理由：`identity_weights` 是本阶段关心的数据源；`--no-dedup` 直接规避过激 prefix-60 过滤；`--limit=50` 限制单批编码、聚类和落盘成本，且沿用已有 50 条真写成功口径。每批结束核对 `truth_ok=true` 和 `disk_delta=50`，抽样检索质量后再扩大到 100–500；不建议一次写入全部 26,291 条。

## 4. 验证

- `python -c "import seed_world_model"`：exit 0（无 import 报错）。
- `python -m py_compile seed_world_model.py`：exit 0。
- `--report-only --source=identity --no-dedup --limit=50`：`would_inject=50`。
