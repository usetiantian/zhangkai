# oh-story 脚本层（取自 zenstory-ai/oh-story-claudecode）

来源：AtomGit 镜像 `https://atomgit.com/gh_mirrors/oh/oh-story-claudecode`（上游 github.com/zenstory-ai/oh-story-claudecode）
许可：MIT（见上游 LICENSE）
取用日期：2026-11-24，只取脚本层与标尺层，**未安装 skill 本体、未跑 /story-setup**。

## 为什么只取这一层

- `web-novel` 与 oh-story 的 `story-long-write` 描述词高度重叠（"写一本小说"/"开新书"/"帮我写章"），装全量会二选一。
- oh-story 的「文风」参照值是硬编码行业区间；本目录原有的 `refs.py`/`style_check.py` 用的是**从目标书实测**的指纹，更准。
- 增量在**确定性检测器**和**平台化评分门**：本目录量「有没有 AI 腔病句」，原有工具量「像不像目标书」，互补。

## 脚本

```bash
# AI 腔句式检测（20+ 类：em-dash 泛滥/否定排比/不是X而是Y/工整并列/比喻密度/解释链密度…）
node check-ai-patterns.js --json --mode=long  <文件...>
#   --mode=auto|long|short   --fail-on=blocking|review_required|all
#   --list-review-classes    输出 review_required 的全部类别

# 模型退化检测（复读/截断/占位符/工程词漏进正文）
node check-degeneration.js --json <文件...>

# 标点规范化（只读检查用 --check）
node normalize-punctuation.js --check --mode=long <文件...>

# 章节索引（locator-path 必须在 source 目录下）
node build_chapter_index.js --source <原文.txt> --output <index.csv> --locator-path 原文/原文.txt
```

依赖：Node ≥18（本机 v24.18.0）。全部可脱离 Claude Code 独立运行，不依赖 `CLAUDE_PLUGIN_ROOT`。

## 参考标尺（references/）

| 文件 | 内容 |
|---|---|
| `quality-rubric.md` | 18 维审稿 rubric + S1-S4 严重度 + APPROVE/CONCERNS/REJECT 三门槛 |
| `fanqie.md` | 番茄量化门槛（首章 ≤300 字见对话、≤400 字入冲突、段长中位 22-26 字） |
| `stage1-golden-chapters.md` | 黄金三章 8 项体检表（单章字数/段长/单句成段率/对白占比/首冲突字位/钩子率） |
| `stage4-6-reversal-summary.md` | 短篇五维评分 + 付费卡点位置 |

## 已知误报（扫旧稿时必须先排除，否则数字失真）

1. **行号前缀**：正文导出稿形如 `77|78|79|80|站81|82|`，整行被当成一个超长段落 → `long-paragraph` 大量误报。
   （实测：渺渺仙途 `正文_txt/` 294 个 txt 中 204 个带行号，`_merged_backup/` 80 个全带。）
2. **章节结束标记**：`【第1章 完】`、`（卷十 第四章 完）` 会被判成 `truncated`（无句末标点）和 `meta-leak`（含"第X章"）。
   → 扫正文前先剥掉这些标记行，或只扫正文正文段。
3. `check-degeneration.js` 顶层 `blocking`/`advisory` 汇总字段不填充，**真实严重度看每条 finding 的 `severity`**。
