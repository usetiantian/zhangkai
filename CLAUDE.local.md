# Working Memory

> This is your working memory. Auto-loaded every session via CLAUDE.local.md.
> ~1500 word limit. Only behavior-changing facts earn a place here.
> Last updated: YYYY-MM-DD

## Total Recall Settings

recall_suggestions: off  # off | low (set to "low" to enable nudges)

## Active Context

**Current Focus**: ComfyUI 视频流水线（换脸 ReActor / 修补 VOID / H3 角色替换）
**Key Deadline**: [none]
**Blockers**: [none]

## Project State

- ComfyUI 在 `D:\ComfyUI_windows_portable`，ComfyUI 0.45.2，RTX 5080 Laptop 16GB，63GB 内存
- 已配好三条线的工作流（均在 `user/default/workflows/`）：
  `视频换脸_ReActor.json`(13节点) / `视频修补.json`(VOID) / `H3角色替换_CharacterSwap_官方.json`(44节点)
- 关键模型已就位：inswapper_128.onnx(fp32) / big-lama.pt / buffalo_l / parsing_parsenet /
  GFPGANv1.4.pth / retinaface / NSFW检测器 / h3_character_swap_v1.5 / Anime-Motion-LoRA
- 漫剧线索：`custom_nodes/ComfyUI-H3-Director`（"H3漫剧导演台"）自带分镜时间轴+音色绑定+原生对口型+字幕烧录
- onnxruntime-gpu 通过 `site-packages/zz_ort_gpu.pth` 注入（指向 `claude-workspace/ortgpu_x/`）
  **ortgpu_x/ 不能删**，删了会静默退回 CPU（不报错，只是慢）

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

## Key Decisions in Effect

- 换脸走 ReActor + FaceBoost（社区 PR#321，先修后贴去方块）；漫剧主线改用
  H3 + Character-Swap LoRA（画风内换角色，无贴脸违和感）
- 视频去水印遮罩用 `SAM3_VideoTrack`+`SAM3_TrackToMask`（全片一致），
  不用逐帧 `SAM3_Detect`（框逐帧抖 → 闪）
- SAM3 检测提示词用短名词短语（"watermark logo and text"），长句会让检测逐帧飘

## People Context

- [none]

## Open Loops

- ReActor 的 NSFW 阈值 0.979→0.99 已改；"被判定帧保留原像素"那半截被 auto-mode 拦，
  需用户明确点名授权或自行粘贴 4 行

## Session Continuity

- 2026-11-15 完成：换脸/去水印/角色替换三条线；换脸从 21 分钟降到 5.6 分钟
- 错误复盘全文见 `.claude/learnings/comfyui_workflow_mistakes_2026-11-15.md`（17 条）
- 日记见 `CC_DIARY_2026-11-15.md`

---
*For detailed history, see memory/registers/*
*For daily logs, see memory/daily/*
