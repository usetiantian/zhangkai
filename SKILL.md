# 文件编辑规则

## 核心原则

1. **编辑前必读文件** — 用 `read` 读取完整内容，oldText 从 read 结果逐字复制
2. **优先 apply_patch** — 多文件/多处修改必须用 `apply_patch`，单文件单处改才用 `edit`
3. **oldText ≠ newText** — 构造完立即对比，相同就重来

## apply_patch 格式

```
*** Begin Patch
*** Update File: path/to/file.py
@@ 可选上下文行
-要被替换的行
+替换后的行
*** End Patch
```

- 支持 Add File / Update File / Delete File / Move to
- 有四级模糊匹配：精确→去尾空格→去全部空格→规范化标点
- workspaceOnly 默认 true（限制在工作区内）

## edit 工具

- oldText: 从 read 结果原文复制，含所有空格、缩进、换行
- newText: 替换后的文本
- 支持 edits 数组格式（一次调多处改）
- 有模糊匹配容错，但仍需尽量精确

## 禁止行为

- 不读文件就 edit
- oldText 和 newText 写一样
- 凭记忆构造 oldText（漏前缀、漏引号、漏缩进）
