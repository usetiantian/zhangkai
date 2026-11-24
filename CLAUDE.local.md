# Working Memory

> This is your working memory. Auto-loaded every session via CLAUDE.local.md.
> ~1500 word limit. Only behavior-changing facts earn a place here.
> Last updated: 2026-11-16

## Total Recall Settings

recall_suggestions: off  # off | low (set to "low" to enable nudges)

## Active Context

**Current Focus**: 《渺渺仙途》AI 漫剧（古风仙侠国漫），EP01 已出片，正在按用户反馈重做画风与人物
**Key Deadline**: [none]
**Blockers**: [none]

### 漫剧制作（重启后直接接着干，全部状态都在磁盘上）

- 工程目录：`manga/渺渺仙途/`（`01_第01-10集/EP01_五灵根惊现/05_成片.mp4` 是已出的片子）
- **开工前必读四份**（唯一事实源，都在 `manga/渺渺仙途/00_素材/`）：
  `制作规范.md`（风格/人物/场景/道具/打斗/节奏硬约束）、`定妆.txt`、
  `造型阶段表.md`、`当前造型.json`
- 技能 `guofeng-manga` 里也有同一套工序和工具表
- 工具：`tools/guofeng_manga.py`（主流程 beat/storyboard/video/all）、
  `manga_check.py`（台词超速+时间轴校验）、`manga_postprocess.py`（Base→Ref2VA+绑定定妆图）、
  `manga_charsheet.py`（角色三视图）、`manga_costume.py`（换装不换脸）、
  `manga_voices.py`（克隆音色）、`manga_merge.py`（合并整集）、`wf2api.py`（工作流→API）

### 用户明确提过的硬要求（别退回老做法）

1. **国产玄幻动漫**（《遮天》《完美世界》《仙逆》挂）：高饱和厚涂、锐利描边、体积光、轮廓光。
   **禁止**平涂赛璐璐/暖黄复古/老电影质感/水墨晕染 —— 用户原话「你这漫剧像是80年代的」
2. **人物不能是小孩子** —— 用户原话「不要弄成小孩子啊」
3. **发型要古风仙侠** —— 用户原话「是现代的平头啊，不是古风仙侠吗」
4. **场景、道具、打斗都要好好写，场面要燃、劲爆**
5. **人物一致性 + 换装时机要考虑**（换装只在集与集之间，用旧图图生图，脸不变）
6. **成片要归档分类** —— 用户原话「单独建一个文件夹放起来，比如1-10集一个文件夹」
7. **这些要求要记下来** —— 用户原话「别我已重启你又要重头开始」→ 全部写进了上面四份文件

## Project State

- ComfyUI 在 `D:\ComfyUI_windows_portable`，ComfyUI 0.45.2，RTX 5080 Laptop 16GB，63GB 内存
- **导演台 11.0 = 现在的主线**：`custom_nodes/ComfyUI-H3-Director`（节点名 `H3DirectorStudio`，无后缀）
  有「AI剧情/AI分镜/AI精修」+ 顶部「API 设置」卡片（2026-11-16 从 7.0 移植回来）
- 7.0 副本（`ComfyUI-H3-Director-v7`，节点名全带 `_v7`）已改名 `.disabled` 停用；
  H3-Stage / 两个 latent-upscaler 也已禁用（2026-11-16 做过完整依赖审计）
- 导演台 LLM API = **DeepSeek 官方 `https://api.deepseek.com/v1`，模型 `deepseek-chat`**
  （`ComfyUI\user\ComfyUI-H3-Director\api_config.json`；7.0 与 11.0 共用这一份文件）
- 在用的工作流（`user/default/workflows/`）：
  `导演台11.0.json` / `视频换脸_ReActor.json` / `视频去水印_LaMa高质量.json` /
  `歌曲制作台_A_YuE2选曲谱.json` / `声音克隆.json` / `H3角色替换_CharacterSwap_官方.json`
- **VOID / Wan2.1VACE 的工作流已从磁盘消失**（`视频修补.json` 等），只剩官方蓝图
- 关键模型已就位：inswapper_128.onnx(fp32) / big-lama.pt / buffalo_l / parsing_parsenet /
  GFPGANv1.4.pth / retinaface / NSFW检测器 / h3_character_swap_v1.5 / Anime-Motion-LoRA
- onnxruntime-gpu 通过 `site-packages/zz_ort_gpu.pth` 注入（指向 `claude-workspace/ortgpu_x/`）
  **ortgpu_x/ 不能删**，删了会静默退回 CPU（不报错，只是慢）

## 2026-11-17 新增（重要，别改坏）

- **导演台文本编码器必须用 `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`（15.7GB）**
  int8_convrot（25.8GB）在 Blackwell 上必崩：
  `NoCapableBackendError: dequantize_int8_embedding: q: dtype torch.bfloat16 not in {torch.int8}`
  —— ComfyUI 0.45 把 int8 权重手动 cast 成 bf16，int8 kernel 拒收（comfy_kitchen/tensor/int8.py）。
  bf16 版 51.5GB 会吃光内存。已改，备份 `导演台11.0.json.bak-cc-te-int8-20261117`
- 导演台11.0 的模型链已接 VRAM 节点：`MysticXXX LoRA → MiniMaxLowVRAMAttention(head_chunks=8)
  → MiniMaxChunkFeedForward(chunks=4, seq_threshold=4096) → PathchSageAttentionKJ`
- **无头出片工具链**（自己写的，规则见 `tools/wf2api.py` 顶部注释）：
  - `tools/wf2api.py` = UI 工作流 → API prompt（7 个工作流全部 0 校验错误）
  - `tools/h3_js.mjs` = 按依赖闭包从导演台前端抽纯函数（避免自己重写分镜解析）
  - `tools/h3_prompts.mjs` / `tools/h3_segments.mjs` = 取系统提示词 / 官方分镜→segments_json
  - `tools/guofeng_manga.py` = 小说→剧本→分镜→出片 一条命令（技能 `guofeng-manga`）
- 已实测：导演台11.0 走 API 出片 5 秒片段成功（960×544@24fps + AAC 对白，121 秒）

## Critical Preferences

- 中文交流；结论先行，给具体路径/命令/数字，不写空话
- 产出物自己看（抽帧/接触表/读指标），不能只看日志说成功

## ComfyUI 工作流操作规则（2026-11-15 踩坑后固化）

1. **文件控件值必须 `os.path.exists` 验证**，不许填占位文件名
2. **节点合法性只认后端 `object_info`**；前端静态 store 只是兜底渲染
   （`MarkdownNote` 后端没有 → 用 `AUSBOSS_NODES_WorkflowNote`）
3. **links 格式顶层和子图可能不同**：顶层 list / 子图 dict。改之前分别 `type(links[0])` 确认；
   append 必须与该数组已有元素同格式；校验器要兼容两种
4. **校验器铁律**：`*` 是通配类型；跳过带 `widget` 标记的输入；id 集合要含 -10/-20 和嵌套子图 UUID
5. **量化/社区转换版模型必须实测推理**（值域 + NaN 占比）。fp16 inswapper 在 CUDA 上输出全 NaN
   → 脸糊成半透明。官方只有 fp32 就用 fp32，别为省空间换量化版
6. 按名字找文件用 `find`/`grep`，**不要 `ls | head -N`**（字母序会截掉 w 开头的模型）
7. **多处联动改动要原子完成**：改一半被拦就整体回退，别留半成品（今天留过"比上游更弱"的代码）
8. `rm -rf` 单独执行、删前确认谁依赖它（今天差点删掉 ortgpu_x 让 GPU 失效）
9. 这个 shell 是 GBK，**不要 print 非 ASCII**；结果写文件再读
10. 超过 1 分钟的命令转后台 + `curl -C -` 续传（前台有 10 分钟工具超时）
11. 结论前先拿源码逐字段比对，**别凭印象说"这个过期了"**（今天说错过）
12. **"效果不好" ≠ "必然失败"**：先做对照实验把两者分开，别一头扎进提示词调优
13. **插件输出被拒时，去读插件自己的校验器**（在 node 里 stub 掉 app/api/document 直接跑原版函数），
    比猜提示词快得多。MiniMax-M3 内联 think 污染就是这个方法定位的
14. **删插件/删文件前做三段反查**：工作流→节点名→插件 + 全盘内容扫描 + 跨插件 import + 各自输出目录。
    节点名正则要兼容 `io.ComfyNode`（V3 架构）写法
15. **改插件目录用改名 `.disabled`**（ComfyUI 官方跳过机制，`nodes.py` 认 `.disabled` 后缀），
    可逆且不影响运行中的进程

## Key Decisions in Effect

- 换脸走 ReActor + FaceBoost（社区 PR#321，先修后贴去方块）；漫剧主线改用
  H3 + Character-Swap LoRA（画风内换角色，无贴脸违和感）
- 视频去水印遮罩用 `SAM3_VideoTrack`+`SAM3_TrackToMask`（全片一致），
  不用逐帧 `SAM3_Detect`（框逐帧抖 → 闪）
- SAM3 检测提示词用短名词短语（"watermark logo and text"），长句会让检测逐帧飘
- **H3 出声的唯一开关是 `<d>[Chinese]台词</d>`**。插件不处理它，原样透传给模型。
  想要台词必须在 **AI剧情阶段**就让模型写出来（系统提示词已改成「对白默认开启」，
  只有用户明确选「无对白无旁白」才禁止）；AI分镜阶段只搬运原文台词，不会自己编
- 导演台 LLM 用 `deepseek-chat` 不用 `deepseek-reasoner`：R1 的 reasoning_tokens 也占
  max_tokens 预算，长分镜会被截断
- **每个 Shot 的台词字数（含标点）必须 ≤ 该 Shot 秒数 × 4**，否则 H3 念不完、口型错位
- `ResolutionSelector` 的 `multiple=32` 是对齐倍数，不是越大越好；调大会比例失真并与 VAE 错位
- **一次只跑 2–3 段**，12 段连跑必卡（内存 63GB 是天花板）

## 小说写作（用户 2026-11-18 问「你会写小说吗」→ 会，已验证）

- **项目**：`D:
ode\阅读笔记\七猫免费小说\蓝莓原创\渺渺仙途`（蓝莓著，15 卷 100 万字）
  卷8/卷9 共 52 章待重写（`卷8卷9重写规格书_v1.md` + `卷8卷9派工简报.md` + 果子写的金标准
  `卷8_万道归一/正文_第02章_万道之源混沌深处.md`）
- **方法论全在本地**：`D:
ode\阅读笔记\七猫免费小说\方法论\`
  （00 写作桌面 10 文档 / 05 七猫爽文解剖 / 09 参考语料风格指纹 / 13 同流派 9 本）
  **《凡人修仙传》《仙逆》等 9 本全文学习样本在** `方法论/_学习样本/凡人修仙传同流派小说集_9本/`
  还有一个 Burrows' Delta 文体测量工具（`方法论/_开源下载器/__extracted_small/fanren-novel-stylometry/`）
- **我的工具**：`tools/style_check.py` —— 把方法论的硬指标变成验收门
  （句长/段长/短句率/对白率/**水词**/连续台词段/套路词/钩子类型/性别错乱 + 与金标准直比）
- **关键结论（用户指出后我才想通）**：
  1. **AI 味的量化指纹是「水词」**（闻言/心中一凛/连忙/眼中闪过）：仙逆 0-3、凡人 0-3、
     金标准 1，**原稿第03章 48**
  2. **「流水式对话」不是对话多**，是台词之间用填充语接、台词没潜台词
  3. 卷8/9 的真标尺是**金标准第02章**（句长 10.5/段长 11.5/台词均字 5.1），
     比仙逆（40.1）碎得多 —— 一句一个动作
- **已交付**：`_试写_待验收/卷8_第03章_试写_渺渺.txt`（4636 字，9/9 硬指标全过，水词 0）
  + `自检报告_卷8_第03章.md`。**未写入正文目录，等用户验收口味**
- **2026-11-18 晚：《拙火》返工教训（用户连续退回三次）**
  1. 第一次瞄错标尺：照《渺渺仙途》金标准写（句长 10/段长 11）→ 用户骂"每段就几个字"
     → **要学仙逆/凡人，就用他们的实测值，别用自己的**
  2. 第二次漏了**段落缩进 `　　` 和中文引号** —— heredoc 会吃掉全角空格、
     把 `“”` 转成 ASCII `"`。**含这些字符的代码/正文必须用编辑工具写，不能走 heredoc**
  3. 第三次：**对话不能短**。凡人台词均 37 字、仙逆 14–27，对话章的参照值 24.3。
     我写成"一坛。""两坛。"这种 → 段长/句长/台词均全部拉低
  - 工具：`tools/para_merge.py`（并段，**只并叙述段，不能并到对话后面**）、
    `tools/style_check.py` 的 `--preset 参考语料`（已按仙逆/凡人实测校准）

## 写新小说（用户 2026-11-18：「我让你学习的是按仙逆、凡人修仙传那些叙事的逻辑，按真人来写一本全新的小说」）

- **新书**：`D:
ode\阅读笔记\七猫免费小说\蓝莓原创\拙火\`（**和《渺渺仙途》同级**，凡人流修仙，第一卷·窑口）
  - `README.md` = 从《凡人修仙传》《仙逆》开篇提取的叙事装置对照表 + 铁律
  - `00_写作台账.md` = 主角/境界(含代价表)/地图/技能器物/女主/反派阴谋线/伏笔表/爽点公式/卷纲/进度
  - `正文/第01章_窑口.md`（2773）、`第02章_二十七件.md`（2404）
- **学的到底是什么**（不是句子/设定，是装置）：
  1. **不写状态写物件**（穷=霉味棉被+裂墙；被器重=两本书；我家=废窑耐火砖被抠去砌猪圈）
  2. **一切可数**（斤两件天、铜板）——十一斤柴、二十七件、三斤半釉、一坛腌菜
  3. **代价先于收益**——用娘的一坛腌菜换釉料，且瞒着娘
  4. **主角第一反应是退**——伸手拿瓶子，伸到一半停住
  5. **向往不能说**（说出来人家只会说他穷）
  6. **贵人平叙**（货郎放下瓶子就走，不预告不渲染）
  7. **配角有自己的账**（瘦子收购商，为难他是因为釉渣干净、有自己的算盘）
  8. **章尾可数的钩子**——"二十七件太少。烧三十六件，我按四42斤收。"
  9. **情绪挂物**——娘每天在碗沿用炭画一道痕
- **验收门**：`tools/style_check.py`（副本在 `蓝莓原创\工具\style_check.py`），本项目水词 0 / 套路词 0 / 连续台词最长 3 / 句长 9.9
- **参照书单章标尺（实测）**：凡人 3180、仙逆 3196 总字符中位
- **待办**：卷1 剩 28 章 + 卷2/卷3；单章字数提到 3000-3300；**等用户验口味**

## 写网文的系统（用户 2026-11-18：「你要形成你的系统，别下次写一个别的小说又忘记了」）

- **技能**：`web-novel`（.claude/skills/web-novel/SKILL.md），开任何新书自动带上
- **代码**：`tools/novel/`（与具体书无关）
  - `ledger.py` 生成空白写作台账（人物/境界/地图/器物/反派/伏笔/爽点/卷纲/进度）
  - `refs.py` 测任意参考书的文风指纹
  - `style_guide.py` 从参考书实测生成"风格指南.md"（硬指标+排版规则+写法规则）
  - `pipeline.py` 单章流水线：plan(场次计划) → cards(角色意图卡) → write(正文) →
    review(审稿评级) → record(回写台账)
- **配套**：`tools/style_check.py`（文风指纹）、`tools/review_chapter.py`（审稿+评级）、
  `tools/para_merge.py`（并碎段）
- **方法论来源**：本地 15 个开源写作项目的机制，已综合（见 `tools/novel/README.md` 的来源表）
  核心是 NovelForge 的六步流水线 + MuMuAI 的风格分析/重复检测/评级 +
  Tonade 的抽卡与回写 + 马良的剧情推演 + stylometry 的指纹测量
- **已用《拙火》实测跑通**：第03章 走完 plan→cards→write→review，Reviewer 如实判 C
- **别再犯**：① 瞄错标尺（用参考书实测值，不用自己的印象）② 段落一句一段
  ③ 对话写成"一坛。"这种 ④ heredoc 吃掉全角空格和中文引号

## 停止事项：不要用我写小说（用户 2026-11-18 明确说「你不适合写小说，就别弄了」）

- **用户的原话**：「就这样吧，你不适合写小说，我看了你现在写的内容，都昏头了。就这样吧，你别弄了。」
- **结论**：我写长篇中文网文（人物、对白、节奏、段落）能力不足，**不要再主动提议写正文**。
  分析、量化、工具、漫剧那条线（ComfyUI/导演台/分镜/审稿）是我能做的事，继续做那些。
- **我建的目录（用户可自行删除，我没动）**：
  - `蓝莓原创/拙火/`（整本都是我建的，包括 12 个版本草稿，可整个删）
  - `蓝莓原创/渺渺仙途/_试写_待验收/`（卷8 第03章试写+自检报告）
- **没动过的**：`渺渺仙途/总纲/05_正文/卷8_卷9` 正文 **0 个文件被改动**（已逐字节比对 pre_rewrite_bak 验证）
- **留下的有用资产**（`tools/`）：`wf2api.py`（工作流→API prompt）、`style_check.py`（文风指纹）、
  `review_chapter.py`（审稿评级）、`para_merge.py`、`tools/novel/`（文体模型/对白实验室/差距报告）。
  这些是**量化的尺子**，以后审别人的稿子能用；写稿子的部分不用了。

## People Context

- [none]

## Open Loops

- **h3-relay 与 ComfyUI-MiniMaxH3-Contex-Loop 重复注册 12 个同名节点**（MiniMaxH3Chain 系列等），
  谁后加载谁赢 → 同一节点重启前后可能不同实现。两个都有工作流在用，需先定位谁赢再决定
- ~~**AI分镜 没有自动重试**~~ → **已解决**：`tools/manga_storyboard.py` 接上插件的
  `repairPrompt`，并补了量化修复指令（告诉模型超了多少秒、Shot 数上限）；
  仍超时用 `tools/manga_retime.py` 确定性缩放时间轴 + `manga_manifest.py` 补 manifest
- 4 个已禁用插件（v7/H3-Stage/两个 upscaler）待下次重启确认无异常后，移出 `custom_nodes`
- ReActor 的 NSFW 三处改动其实已全部完成（阈值 0.99 + restore_blocked + nodes.py），
  待办里的"半改状态"是过时快照；当前交付工作流 `restore_with_main_after=False`，
  nodes.py 的最终修脸分支根本不会走
- **卷1 造型阶段 B–E 的定妆图还没生成**（阶段表见 `00_素材/造型阶段表.md`），
  第16章之后要用 `tools/manga_costume.py` 换装（denoise 必须 ≤0.55，否则模型把三视图当纹理铺）
- **漫剧画幅还是 16:9 / 832×480**。抖音/快手漫剧惯例是竖屏 9:16，
  改导演台11.0 的 ResolutionSelector 即可（同样像素预算，速度不变）——**等用户拍板**

## Session Continuity

- 2026-11-17 完成：导演台 int8 文本编码器崩溃修好（换 nvfp4_awq）；写 `tools/wf2api.py`
  把 7 个工作流全转成 API prompt（0 校验错误）；写 `tools/guofeng_manga.py` 小说→出片一条命令；
  建技能 `.claude/skills/guofeng-manga/SKILL.md`；实测导演台 API 出片成功（含对白）
- 2026-11-16 完成：导演台 AI 按钮从"100% 必失败"修到可用（切 DeepSeek + 剥 think + 容忍前言）；
  API 设置面板从 7.0 移植回 11.0；「＋对白/无对白」快捷按钮后按用户要求删除，改为默认写对白；
  禁用 4 个无用插件
- 2026-11-15 完成：换脸/去水印/角色替换三条线；换脸从 21 分钟降到 5.6 分钟
- 错误复盘全文见 `.claude/learnings/comfyui_workflow_mistakes_2026-11-15.md`（17 条）
- 日记见 `CC_DIARY_2026-11-17.md`（今天）/ `CC_DIARY_2026-11-16.md`（昨天）

---
*For detailed history, see memory/registers/*
*For daily logs, see memory/daily/*
