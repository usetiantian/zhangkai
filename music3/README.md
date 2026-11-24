# music3 —— 一句话生成音乐

本地跑 ComfyUI v0.34.0 内置的 **MiniMax Music3**，不调云端 API、不花钱，模型全在你自己硬盘上。

ComfyUI 原生就带 `comfy/ldm/minimax_music/` 全套实现和官方工作流模板，
所以这里不需要写任何 custom node——只是把那套图包成命令行 + 网页 + 桌面应用。

> 📦 **要上架卖钱？** 看 [`上架清单.md`](上架清单.md)——里面有渠道对比、
> 模型 14 GB 怎么分发、license 合规要点、变现定价和成本模型。
> 许可证结论：**MiniMax-Music3 Community License 允许商用**，只要界面显著标注
> "MiniMax-Music3"（已做），年营收低于 2000 万美元无需额外授权。

## 三种用法

| | 入口 | 说明 |
|---|---|---|
| 🖥️ **桌面应用** | `release/music3.exe` 或 `启动.bat` | 环境体检 + 控制面板 + 自动开浏览器；可打包分发 |
| 🌐 **网页版** | `python server.py` | 浏览器界面，本机访问 |
| ⌨️ **命令行** | `python music3.py "..."` | 适合批处理和脚本化 |

## 文件

```
music3/
├── app.py             桌面应用入口（环境体检 + 控制面板）
├── doctor.py          环境检测（ComfyUI / 模型 / 显卡）
├── engine.py          ComfyUI 客户端 + MiniMax 文本助手（共用逻辑）
├── music3.py          命令行版
├── server.py          HTTP 服务（只监听 127.0.0.1）
├── server_lan.py      HTTP 服务（局域网/手机，见下）
├── static/index.html  网页界面
├── assets/            应用图标
├── release/           可分发包（exe + 许可证 + 使用说明）
├── music3.spec        PyInstaller 打包配置
└── 上架清单.md         分发/合规/变现清单
```

## 前置

先跑起 ComfyUI：`D:\ComfyUI_windows_portable\run_nvidia_gpu.bat`（默认 http://127.0.0.1:8188）

模型已就位（缺的话从 HuggingFace `Comfy-Org/MiniMax-Music3` 下）：

| 部件 | 路径 | 大小 |
|---|---|---|
| DiT | `models/diffusion_models/minimax_music3_dit_fp16.safetensors` | 4.9G |
| DiT 低显存版 | `models/diffusion_models/minimax_music3_dit_int8_convrot.safetensors` | 2.5G |
| 文本编码器 | `models/text_encoders/minimax_music3_text_encoder_pruned_int8_convrot.safetensors` | 9.2G |
| 音频 VAE | `models/vae/minimax_music3_dav.safetensors` | 217M |

---

## 桌面应用

```bash
启动.bat              # 或 python app.py
```

启动后弹出一个控制面板，做三件事：

1. **环境体检** —— ComfyUI 通不通、4 个模型齐不齐、显卡是什么、还差什么
2. **打开工作室** —— 自动在浏览器打开界面（地址也会写进 `%APPDATA%\music3\runtime.json`）
3. **ComfyUI 目录** —— 一键打开安装目录

模型没齐时，面板会直接给出下载仓库地址（**国内走 `hf-mirror.com`**，`huggingface.co` 直连通常不通）。

### 打包成 exe

```bash
打包.bat              # 或 python -m PyInstaller --noconfirm --clean music3.spec
```

产物 `dist/music3.exe`（约 12 MB）。`release/` 里是已经打好的分发包，
含 exe + 三份许可证 + 使用说明。

> ⚠️ 安装包只有 12 MB，**不含模型**（14.3 GB）——用户需自行下载。
> 这不是 bug，是刻意的：详见 `上架清单.md` §2。

---

## 网页版

```bash
python server.py            # 只监听本机
```

浏览器打开 **http://127.0.0.1:8899**

界面功能：

- **一句话描述** 输入框 + **AI 写编曲说明** / **AI 写歌词** 两个按钮
- **歌词框**（留空 = 纯器乐）
- **参数面板**：时长、步数、CFG、top-k、生成数量、变奏方式、种子、格式、音质、低显存模式
- **结果卡片**：播放器 + 种子标签 + 下载 + 一键复制种子
- 手机上布局自适应

### 批量生成 / 变奏对比

一次出多首，横着挑：

| 变奏方式 | 做法 | 适合 |
|---|---|---|
| 换种子 | 同 prompt，不同 seed（seed+7919 递推） | 同一首歌的多个版本，挑最顺耳的 |
| 换 CFG | 同 seed，CFG 走 1.4 / 1.6 / 1.8 / 2.0 阶梯 | 同一旋律，看哪档最贴描述 |

四个种子一次性提交给 ComfyUI 排队，生成完并排显示，**同 seed + 同 prompt 可复现**。

### AI 写词 / 写编曲说明

需要一个 MiniMax API Key，填在页面底部的输入框里。

> **国际站和国内站的 Key 不能互换**
> - 国际站 `platform.minimax.io` → Key 只能用在 `api.minimax.io`
> - 国内站 `platform.minimaxi.com` → Key 只能用在 `api.minimaxi.com`，且 `chatcompletion_v2` 还要带 **GroupId**（后台可见）
>
> 填完 Key 先点 **「🔌 测试 Key 连通性」**，它会依次试 6 个「站点×模型」组合，
> 明确告诉你哪个能用、每个为什么失败，别猜。

| 尝试顺序 | 站点 | 模型 | 需要 GroupId |
|---|---|---|---|
| 1 | 国际站 | `MiniMax-M3.1-Flash` | 否 |
| 2 | 国内站 | `MiniMax-M3.1-Flash` | 否 |
| 3 | 国际站 | `MiniMax-M3` | 否 |
| 4 | 国内站 | `MiniMax-M3` | 否 |
| 5 | 国际站 | `MiniMax-Text-01` | 否 |
| 6 | 国内站 | `MiniMax-Text-01` | **是** |

- Key 只存在**你自己浏览器的 localStorage**，随请求发给本机服务，**不写磁盘、不进日志**
- **AI 写编曲说明**：把一句话扩成详细声学描述（风格/BPM/调式/结构/乐器/人声/混音/场景）
- **AI 写歌词**：带 `[Verse] [Chorus]` 分段标记的中文歌词
- 失败时错误**常驻显示在页面上**，不是一闪而过的提示条

命令行版也支持：`--auto-lyrics`（读环境变量 `MINIMAX_API_KEY`）

### 局域网 / 手机访问

`server.py` **只绑 127.0.0.1**，局域网内其他设备访问不到。想让手机连同一 wifi 打开，
用单独的脚本（需要你在终端显式运行）：

```bash
python server_lan.py
```

它会监听所有网卡并打印局域网地址，例如 `http://192.168.1.23:8899`。
手机浏览器直接输这个地址即可。

> ⚠️ 这会把服务暴露给同网络的设备（能调用你的 ComfyUI、消耗 GPU 时间）。
> 只在可信网络里用，用完 Ctrl+C 关掉。

---

## 命令行版

```bash
# 纯器乐（不填歌词就是 instrumental）
python music3.py "深夜孤独的流行抒情歌，钢琴前奏，副歌要炸" -d 60

# 指定歌词
python music3.py "国风古筝，戏腔女声" --lyrics-file lyrics.txt -d 90

# 自动写歌词（需 MINIMAX_API_KEY）
python music3.py "甜美女声爵士" --auto-lyrics --lyric-hint "关于夏天的记忆"

# 显存不够，换 int8 版 DiT
python music3.py "史诗管弦" --lowvram
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `caption` | 必填 | 风格 / 情绪 / 乐器 / 场景，写得越具体越好 |
| `-d, --duration` | 60 | 最长秒数 0.04~360，模型可能提前结束 |
| `-s, --seed` | 随机 | 同 seed + 同 prompt 可复现 |
| `--steps` | 20 | 采样步数 |
| `--cfg` | 1.7 | 文本 CFG（1.5~2.0 稳定，越高越贴 prompt） |
| `--top-k` | 50 | 采样候选数 |
| `--format` / `--quality` | mp3 / 320k | 输出格式 |
| `--out` | ./out | 输出目录 |
| `--server` | 127.0.0.1:8188 | ComfyUI 地址 |

---

## 提示词写法

Music3 是**声学条件**模型，不是理解语义。写「信息」而不是「指令」：

- ❌ `写一首悲伤的情歌` → ✅ `慢速钢琴 ballad，低沉男声，小调，忧郁克制，轻微房间混响`
- ✅ 带上：BPM、调式、乐器、情绪、人声类型、混音质感、场景

想听某首参考的质感，就描述它的**制作特征**，别写歌名。

---

## 工作流原理

```
UNETLoader ─────────────────────────► MODEL ──┐
CLIPLoader ─► CLIP ─┐                            │
       caption      ├─► MiniMaxMusic3TextEncode ─┴─► CONDITIONING + seconds
       lyrics       │            │
       seed/dur/cfg │            └─► ConditioningZeroOut ──► negative
       ┌────────────┘
       └─ seconds ─► EmptyMiniMaxMusic3LatentAudio ─► LATENT ─┐
                       KSampler(model, pos, neg, latent, 20步, euler/simple, cfg=1)
                                  │
                                  ▼
                        VAEDecodeAudioTiled(1536/64) ─► AUDIO ─► SaveAudioAdvanced(mp3)
```

三个关键点：

1. **`KSampler` 的 cfg 固定 1** —— 真正的 CFG 在 `MiniMaxMusic3TextEncode` 内部已经做完了，外面再叠会崩。
2. **时长是动态的** —— `max_duration` 只是上限，编码器算出实际秒数，latent 长度跟着走。
3. **必须用 `SaveAudioAdvanced`** —— `SaveAudio` 已废弃（固定 FLAC）。
   它的格式是动态组合控件，API 里要**扁平化**成 `format` + `format.quality` 两个字段。
