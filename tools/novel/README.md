# 网文生产系统（通用，与具体书无关）

一套可套用到任何网文写作的系统。综合了本地 15 个开源写作项目的机制。

## 来源与借鉴

| 来源 | 借鉴的机制 | 落在哪 |
|---|---|---|
| NovelForge (hzhang092) | Planner / Characters / Writer / Reviewer / Fact Extractor / State Updater 六步流水线 | tools/novel/pipeline.py |
| MuMuAINovel | 风格分析生成 style guide、伏笔自动注入、一致性检查、重复检测、A/S/B/C/D 分级 | style_guide.py + review_chapter.py |
| Tonade 100万字工作台 | 大纲抽卡选版、拆知识库/角色卡/世界观、批量生成并每章回写 | ledger.py + pipeline.py 的 record 步 |
| 马良AI写作 | 剧情推演多分支、AI拆书多维提取 | pipeline.py 的 plan 步、refs.py |
| NovelBibleWiki / Worldweaver | 设定与世界观集中管理 | ledger.py 模板 |
| fanren-novel-stylometry | 文体指纹测量 | style_check.py |

## 开一本新书

    python tools/novel/ledger.py 《书名》 <书目录> --protagonist 主角名 --age 16 --origin 出身
    python tools/novel/style_guide.py <书目录> --ref 参考书.txt --ref2 参考书2.txt --name 书名
    python tools/novel/pipeline.py <书目录> --chapter 03 --source 章节.txt --title 标题

流水线产出（全部落盘，可审）：

    <书目录>/
      00_写作台账.md            人物/境界/地图/器物/反派/伏笔/爽点/卷纲/进度，每章回写
      风格指南.md               从参考书实测出的硬指标 + 排版规则 + 写法规则
      计划/第03章_场次计划.md   时间轴 + 每场一个动作 + 钩子
      计划/第03章_角色意图卡.md 要什么/知道什么/情绪/怎么开口/潜台词
      正文/第03章_标题.md
      审稿/第03章_审稿.md       指标 + 重复 + 一致性 + 评级

## 四个关键设计

1. **Characters 步是质量的根**。先定角色此刻要什么、知道什么、怎么开口、潜台词是什么，
   再写正文，对话自然有潜台词，不会变成一问一答的流水。
2. **Reviewer 是门禁**。S/A 才能进下一章，C 以下返工。
3. **风格指南不是抄书**，是从参考书实测指纹后按容差生成目标带；换一本标尺就换一套。
4. **中间产物全部落盘**，任何一步不满意就只重跑那一步。

## 单独可用的小工具

| 工具 | 作用 |
|---|---|
| tools/style_check.py <章.md> --preset 参考语料 | 文风指纹体检 |
| tools/style_check.py --corpus | 打印参考书实测指纹 |
| tools/review_chapter.py <章.md> --prev 前章.md | 单章审稿 + 评级 |
| tools/para_merge.py <章.md> --limit 58 | 把过碎的叙述段并成一段一个信息单元 |
| tools/novel/refs.py <参考书.txt> | 测任意一本参考书的指纹 |
