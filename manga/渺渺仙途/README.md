# 《渺渺仙途》AI 漫剧工程

- **原作**：`D:\node\阅读笔记\七猫免费小说\蓝莓原创\渺渺仙途`（蓝莓著，15 卷，数百章）
- **画风**：国产玄幻动漫（《遮天》《完美世界》《仙逆》那一挂：高饱和厚涂、锐利描边、体积光、轮廓光、灵气粒子）
- **出片**：本机 ComfyUI 导演台 11.0（MiniMax H3，音画同出）
- **画幅**：832×480 / 24fps（导演台 11.0 现有设置，16:9）

## 目录规范

```
manga/渺渺仙途/
├── README.md              本文件（进度表）
├── 00_素材/
│   ├── 定妆.txt           ★ 风格+人物+场景圣经，唯一事实源，改这里
│   ├── 定妆图/            角色三视图参考图（Qwen-Image 生成）
│   ├── 音色/              克隆出来的角色音色（Qwen3-TTS）
│   └── 小说原文/          清洗过的章节原文
├── 01_第01-10集/
│   ├── EP01_五灵根惊现/
│   │   ├── 01_分镜任务书.txt    带时间轴和台词预算的场次表
│   │   ├── 02_官方分镜.txt      H3 官方三字段分镜
│   │   ├── 03_段表.json         解析出的分段（含 refs / Ref2VA 提示词）
│   │   ├── 04_APIprompt.json    提交给 ComfyUI 的 API prompt
│   │   ├── 05_成片.mp4          ★ 成片
│   │   └── 06_抽帧/             成片抽帧，用于验收画风
│   └── EP02_...
├── 02_第11-20集/ ...
└── ...
```

## 制作流水线

一条命令（小说 → 成片）：

```bash
python tools/guofeng_manga.py all 章节.txt --duration 75 --context manga/渺渺仙途/00_素材/定妆.txt
```

拆开跑（推荐，可中途验收）：

```bash
# 1) 章节原文 -> 分镜任务书（带时间轴 + 台词预算）
python tools/guofeng_manga.py beat 章节.txt --duration 75 --context 00_素材/定妆.txt -o 01_分镜任务书.txt

# 2) 校验：时间轴连续吗？台词超速吗？（超速 = H3 念不完、口型错位）
python tools/manga_check.py 01_分镜任务书.txt

# 3) 分镜任务书 -> H3 官方三字段分镜
python tools/guofeng_manga.py storyboard 01_分镜任务书.txt -o 02_官方分镜.txt

# 4) 官方分镜 -> 段表（复用插件自己的解析器，30 秒分镜自动切 3 段）
node tools/h3_segments.mjs < in.json > 03_段表.json

# 5) 段表 -> Ref2VA 提示词 + 绑定角色定妆图
python tools/manga_postprocess.py 03_段表.json -o 03_段表_ref2va.json --ep "第X集 标题"

# 6) 组 API prompt 并出片
python tools/wf2api.py "D:/.../导演台11.0.json" --check      # 先校验，不烧 GPU
python tools/guofeng_manga.py video 03_段表_ref2va.json      # 提交并等成片

# 7) 合并整集
python tools/manga_merge.py <project_id> <段数> 目标目录
```

## 配套工具

| 工具 | 作用 |
|---|---|
| `tools/wf2api.py` | UI 工作流 → API prompt 通用转换器（7 个工作流全部 0 校验错误） |
| `tools/h3_js.mjs` | 按依赖闭包从导演台前端抽纯函数（避免自己重写分镜解析） |
| `tools/h3_prompts.mjs` | 取导演台的系统提示词 |
| `tools/h3_segments.mjs` | 官方分镜 → segments_json |
| `tools/guofeng_manga.py` | 小说 → 剧本 → 分镜 → 出片 主流程 |
| `tools/manga_check.py` | 分镜任务书校验（时间轴连续性 + 台词语速预算） |
| `tools/manga_postprocess.py` | Base 分镜 → Ref2VA 六字段 + 绑定角色定妆图 + 逐镜补风格句 |
| `tools/manga_charsheet.py` | Qwen-Image 生成角色三视图参考图 |
| `tools/manga_voices.py` | Qwen3-TTS 生成/克隆角色音色 |
| `tools/manga_merge.py` | 分段合并成整集 |

## 关键规则（都是踩过坑定下来的）

1. **文本编码器必须用 nvfp4_awq**（15.7GB）。int8_convrot 在 Blackwell 上必崩：
   `dequantize_int8_embedding: q: dtype torch.bfloat16 not in {torch.int8}`。
2. **台词预算**：每个 Shot 的汉字数（含标点）必须 ≤ 该 Shot 秒数 × 4。
   超了 H3 念不完、口型错位。`manga_check.py` 会拦。
3. **每段 ≤15 秒**：30 秒分镜会被插件自动切成 3 段（实测 9.9/9.9/10.2）。
4. **段内必须有画面**：不要写"他走进屋里"就完事，要写景别、运镜、光源、材质。
5. **人物必须带参考图**：只靠文字描述，角色长相必然漂。定妆图 + `<Subject N> ... <Picture N>` 绑定。
6. **不要写"暖黄复古色调/老电影质感"**：那是 80 年代国产动画的观感，H3 会照做。
7. **现代元素必须显式禁止**：H3 默认会给古装场景塞玻璃幕墙、电线杆。
8. **一次只跑 3-6 段**：内存 63GB 是天花板，段一多就开始翻页面文件。
9. **画幅**：导演台 11.0 现设 16:9 / 0.5MP（832×480）。要竖屏改 ResolutionSelector 的 aspect_ratio。

## 进度

| 集 | 章节 | 时长 | 状态 | 目录 |
|---|---|---|---|---|
| EP01 | 第01章 五灵根惊现 | 73.2s | ✅ 已出片（v4：玄幻国漫+定妆图+克隆音色） | `01_第01-10集/EP01_五灵根惊现/05_成片.mp4` |
| EP01-v1 | 同上 | 73.2s | 旧画风参考（像 80 年代国漫，留作对比） | `EP01_五灵根惊现/05_成片_v1_旧画风参考.mp4` |
| EP02 | 第02章 林家小院父亲长叹 | 75s | ⏳ 分镜/段表/Ref2VA 提示词已就绪，待渲染 | `01_第01-10集/EP02_父亲长叹/` |
| EP03+ | 第03章起 | — | 未开始 | — |

**EP01 v4 成片规格**：960×544 @24fps，h264 + AAC 立体声 32kHz，6 段共 73.2 秒。
人物一致性靠角色定妆图（refs + `<Subject N>/<Picture N>` 绑定），
声音靠 Qwen3-TTS 克隆音色（voice_refs + voice_modes=voice）。

## 出片位置

- ComfyUI 输出：`D:\ComfyUI_windows_portable\ComfyUI\output\video\h3director\<project_id>\`
- 归档成片：`manga/渺渺仙途/01_第01-10集/EP01_五灵根惊现/05_成片.mp4`
