---
name: guofeng-manga
description: >
  把一本小说做成古风国漫动漫风格的漫剧成片。走本机 ComfyUI 的「导演台 11.0」
  工作流（MiniMax H3 音画同出），四步：小说 -> 剧本 -> 官方 H3 分镜 -> 视频。
  适用于用户说「我给你一本小说」「做成漫剧/动画短片」「古风国漫风格」「导演台出片」
  「小说转分镜」「AI剧情/AI分镜/AI精修」「批量出片」等请求。
  也用于修导演台 11.0 的 int8 文本编码器崩溃、把 UI 工作流转成 API prompt 无头出片。
argument-hint: "[小说文件路径] [--duration 秒] [--dry]"
---

# 古风国漫漫剧流水线

把小说交给用户，直接产出古风国漫动漫风格的 MP4 成片（带对白和音效）。

## 机器与依赖

- ComfyUI：`D:/ComfyUI_windows_portable/ComfyUI`，端口 8188，必须**开着**
- 导演台插件：`custom_nodes/ComfyUI-H3-Director`
- 导演台工作流：`user/default/workflows/导演台11.0.json`
- 显卡：RTX 5080 Laptop 16GB / 内存 63GB。**内存是瓶颈**，见下方「内存」

## 一条命令跑完

```bash
python tools/guofeng_manga.py all 小说.txt --duration 15
```

产物：`script.txt`（剧本）、`storyboard.txt`（官方 H3 分镜）、`segments.json`（分段）、
ComfyUI 输出目录下的 `漫剧_segN_*.mp4`。

单步也能跑：

```bash
python tools/guofeng_manga.py script     小说.txt --duration 15   # 小说 -> 剧本
python tools/guofeng_manga.py storyboard script.txt               # 剧本 -> 官方分镜
python tools/guofeng_manga.py segments   storyboard.txt           # 分镜 -> segments_json
python tools/guofeng_manga.py video      segments.json --dry      # 只看 prompt 不出片
```

## 四步各是什么

1. **AI剧情**：`POST /h3director/ai_prompt`，system prompt 取自插件前端
   `buildCreateStoryToScriptSys`（由 `tools/h3_js.mjs` 按依赖闭包抽出来）。
   输出格式：首行 `目标总时长：X秒`，然后逐场 `场次N、场次起止时间：a–b秒、
   场景与时间、出场人物、△动作、角色名：台词`。
2. **AI分镜**：system prompt 取自 `buildCreateOfficialStoryboardSys`。
   输出必须是官方 H3 三字段：
   `integrated_multimodal_description:` / `overall_soundscape:` / `non_diegetic_music:`，
   外加 `director_import_manifest:`（含 `source_total_duration_seconds`）。
   每个 Shot 用绝对时间 `At 00:00:03.000,`，[Shot 1] 不写 At。
3. **解析分段**：`tools/h3_segments.mjs` 调插件自己的 `prepareOfficialStoryboardOutput`
   + `parseOfficialScript`，过不了官方格式/时长守恒校验会直接报错，不会糊弄过去。
   30 秒分镜会自动切成 3 段（每段 ≤15 秒）。
4. **出片**：`tools/wf2api.py` 把导演台11.0 转成 API prompt，填 `segments_json`
   后 `POST /prompt`。

## 风格锚定（古风国漫）

风格写两遍，缺一不可：

- `global_prompt`（导演台节点参数）：
  `古风国漫动漫风格：赛璐璐动画上色，中国传统服饰与建筑，工笔描线配水墨晕染，柔和光影，电影感构图，人物五官精致统一，角色造型与服装跨镜头保持一致。`
- 每段 prompt 里也要有风格句（AI 分镜那步已经在每句 Shot 里带上了）。

改风格只改 `tools/guofeng_manga.py` 里的 `GUOFENG_STYLE` 常量。

## 对白规则

- 官方 H3 用 `<d>[Chinese]台词</d>` 标记，插件原样透传给 MiniMax H3
- 语速：慢 ≤2.5 字/秒、正常 ≤4 字/秒、快 ≤5.5 字/秒
- **每个 Shot 的台词字数（含标点）必须 ≤ 该 Shot 秒数 × 4**。5 秒镜头最多 20 字。
  超了 H3 念不完、口型错位。`tools/h3_js.mjs` 里的 `h3RebalanceShotDurations`
  能自动把超速镜头拉长、别的镜头压紧。
- 导演台的 AI 按钮**默认写对白**，不需要额外点「＋对白」。

## 硬约束（踩过的坑）

- **文本编码器必须用 nvfp4_awq**。
  `qwen3vl_32b_minimax_h3_int8_convrot.safetensors` 在 Blackwell 上会崩：
  `NoCapableBackendError: dequantize_int8_embedding: q: dtype torch.bfloat16 not in {torch.int8}`
  —— ComfyUI 0.45 把 int8 权重手动 cast 成 bf16，int8 kernel 拒收。
  用 `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`（15.7GB，比 int8 还省 10GB 内存）。
  bf16 版 51.5GB 会把内存吃光。
- **内存 63GB 是天花板**。int8 主模型 20.9GB + 文本编码器 25.8GB + 两个 VAE 5.5GB
  = 52GB+，再叠 ComfyUI 本身就会开始用页面文件，表现为「卡住但 GPU 只有 64W」。
  nvfp4 换掉 int8 之后是 15.7 + 20.9 + 5.5 = 42GB，能跑。
- **一次只跑几段**。12 段连跑必卡；先跑 2–3 段验证，再加量。
- `ResolutionSelector` 的 `multiple=32` 是对齐倍数，**不是越大越好**。
  32 已经够了；调大会拉高分辨率、放大比例失真，还会和 VAE 的 32 倍数错位。
- 二采（RelayVSR/RealESRGAN）很吃显存，等一段跑完、模型卸载后再做。

## 无头出片（不点界面）

```bash
python tools/wf2api.py "D:/.../导演台11.0.json" --dry      # 看转换结果
python tools/wf2api.py "D:/.../导演台11.0.json" --check    # 校验，不烧 GPU
```

`wf2api.py` 的 widget 对齐规则（踩过的坑，别改坏）：
- 控件槽位 = 节点 `inputs` 里带 `widget` 字段的条目顺序，不是 `INPUT_TYPES` 顺序
- seed 类控件多占一个「控制后动作」槽（后端 spec 里 `control_after_generate: true`）
- 连线覆盖控件值（前端就是这个顺序）
- 子图实例节点 `isVirtualNode=true`，不进 API prompt；只有内部节点进，id 是 `<实例id>:<内部id>`
- 子图接口(-10)：父图连线了就透传连线，没连线就取实例上的控件字面值
- 动态 combo 后端收扁平键（`format` + `format.quality`），不是一个 dict
- AUTOGROW 分组收扁平键（`images.image_1`、`values.a`）

## 想复用导演台前端的逻辑

`tools/h3_js.mjs` 会按依赖闭包从 `h3_studio.js` 抽纯函数，`h3_script_tools.js`
是无 DOM 的纯模块直接 import。改插件后不用改这里，抽出来就是最新的。

**注意**：写含反斜杠的代码要用编辑工具，不要用 shell heredoc —— heredoc 会把
反斜杠吃掉（`\n` 变真换行，`\w` 变 `w`）。

## 回滚

- 导演台11.0.json 备份：`导演台11.0.json.bak-cc-te-int8-20261117`（换 TE 前）、
  `导演台11.0.json.bak-cc-before-lowvram-20261117`（接 VRAM 节点前）、
  `导演台11.0.json.bak-cc-20261116`（原始）
- 插件 JS 备份：`h3_studio.js.bak-cc-20261116`（原始）、
  `h3_studio.js.bak-cc-before-rebalance-20261117`

## 漫剧生产（小说 -> 成片）

用户给了小说路径要做漫剧时，**先读这四份文件，它们是唯一事实源**：

- `manga/<作品名>/00_素材/制作规范.md`  ← 风格/人物/场景/道具/打斗/节奏，全部硬约束
- `manga/<作品名>/00_素材/定妆.txt`      ← 风格句 + 人物外观 + 场景道具
- `manga/<作品名>/00_素材/造型阶段表.md` ← 什么时候换装
- `manga/<作品名>/00_素材/当前造型.json` ← 每集该用哪张定妆图

### 铁律（都是用户明确要求过的，别退回老做法）

1. **风格是国产玄幻动漫**（《遮天》《完美世界》《仙逆》那一挂）：高饱和厚涂、锐利描边、
   体积光、轮廓光、灵气粒子。**禁止**平涂赛璐璐、暖黄复古色调、老电影质感、水墨晕染——
   这些词一写，画面立刻变成 80 年代国产动画，用户明确骂过这一点。
2. **人物不能是小孩子**。成年角色一律成年体型（肩宽、身量、喉结、七到八头身），
   禁止 Q 版幼态。写进提示词并且写进 negative。
3. **发型必须古风仙侠**：高马尾束发/发髻/发冠，**禁止平头寸头板寸现代发型**。
4. **人物一致性靠三件套**：定妆图（refs + `<Subject N> ... <Picture N>`）锁身份，
   克隆音色（voice_refs + voice_modes）锁声音，造型阶段表锁服装。
5. **换装只能发生在集与集之间**，用旧定妆图做图生图换装，脸不能变。
6. **场景要写到材质/层次/光源/氛围/规模感**，道具要点名并写质感与磨损。
7. **打斗场面要燃**：动作分解 + 力量感 + 速度感 + 特效 + 镜头运动 + 声效，
   不要只写"两人激战"。
8. **台词预算 ≤ 秒数×4**（含标点），超了 H3 念不完、口型错位。
9. **每段 ≤15 秒**，一次只渲 3–6 段（63GB 内存是天花板）。
10. **每集渲完必须抽帧逐张验收**：脸、年龄、发型、衣服、场景有无现代元素、打斗燃不燃。

### 一集的工序

```bash
python tools/guofeng_manga.py beat 章节.txt --duration 75 --context 00_素材/定妆.txt -o 01_分镜任务书.txt
python tools/manga_check.py 01_分镜任务书.txt
python tools/guofeng_manga.py storyboard 01_分镜任务书.txt -o 02_官方分镜.txt
node tools/h3_segments.mjs < in.json > 03_段表.json
python tools/manga_postprocess.py 03_段表.json -o 03_段表_ref2va.json --ep "第X集 标题"
python tools/guofeng_manga.py video 03_段表_ref2va.json
python tools/manga_merge.py <project_id> <段数> 目标目录
```

### 配套工具

| 工具 | 作用 |
|---|---|
| `tools/guofeng_manga.py` | 主流程：beat / script / storyboard / segments / video / all |
| `tools/manga_check.py` | 时间轴连续性 + 台词语速预算校验 |
| `tools/manga_postprocess.py` | Base 分镜 → Ref2VA 六字段 + 绑定定妆图 + 逐镜补风格句 |
| `tools/manga_charsheet.py` | Qwen-Image 生成角色三视图参考图 |
| `tools/manga_costume.py` | 以旧定妆图为底图换装（脸不变） |
| `tools/manga_voices.py` | Qwen3-TTS 生成/克隆角色音色 |
| `tools/manga_merge.py` | 分段合并成整集 |
| `tools/wf2api.py` | UI 工作流 → API prompt 通用转换器 |
| `tools/h3_js.mjs` | 从导演台前端抽纯函数（避免自己重写分镜解析） |

### 目录规范

```
manga/<作品名>/
├── README.md              进度表
├── 00_素材/               定妆.txt / 定妆图/ / 音色/ / 小说原文/ / 制作规范.md / 造型阶段表.md / 当前造型.json
├── 01_第01-10集/EP01_标题/{01_分镜任务书.txt, 02_官方分镜.txt, 03_段表.json, 04_APIprompt.json, 05_成片.mp4, 06_抽帧/}
├── 02_第11-20集/ ...
```
