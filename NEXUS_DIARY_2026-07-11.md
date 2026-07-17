# Nexus 工作日记 — 2026-07-11 (v18.5n)

## 今日主题：SmolLM2器官移植 + 多模态地基 + 螺旋速度陷阱

### 数字

- 50000步训练验收：loss=1.29, ppl=3.6 （但只学会预测BOS/EOS）
- SmolLM2-1.7B → SpiralDecoder 移植：84个权重矩阵
- 混合模型：2.66GB BF16, 1.02B参数
- 中文数据：本地4,688篇, 1,270万字 (36x vs 网络采集)
- COCO图片：18,326张 (2.8GB) ✅
- CLIP 150M + Whisper 242M 编码器 ✅
- pip误删CUDA torch事件 x1
- 多进程训练混乱 x2
- BPE分词瓶颈：SQLite方案待实施

---

## 一、50000步训练验收

```
SpiralDecoder best.pt (step=46620):
  Loss: 1.29, PPL: 3.6
  权重确已变化 (std 0.0015→0.0052)
  但推理时只预测BOS/EOS — 学会"闭嘴"
  根因: 341个.py文件, 数据太窄
```

## 二、SmolLM2器官移植

### 架构验证
```
SpiralDecoder vs SmolLM2-1.7B:
  形状完全兼容: Q/O/FFN/Norm ✅
  形状不兼容: K/V (heads数不同), tok_embed/lm_head (vocab不同)
```

### 移植策略
```
移植: Q/O/FFN/Norm ← SmolLM2 11T tokens预训练
保留: K/V/think_modes/cross_attn/tok_embed/lm_head ← 我们自己
格式: FP32→BF16
输出: hybrid_smollm2.pt (2.66GB)

诊断:
  随机初始化: PPL=66,557
  我们50K步:  PPL=448
  混合模型:   PPL=65,565 (词表不对齐, 需fine-tune)
```

## 三、中文数据大丰收 (36x增量)

```
来源                    篇数      字数
知识库 (D:\node\)      3,597    10.4M  ← AI/数理化/历史/哲学...
小说   (D:\node\)        393     1.0M  ← 凡人修仙传/仙逆/雪中...
七猫   (D:\node\)        700     1.2M  ← 网文素材/原创/写作练习

总计: 4,688篇 .py, 1,270万字
vs 网络采集: 127篇, 35.5万字 → 36倍！
nexus_agent/ 共5,029文件, 中文占93%
```

## 四、多模态地基

### 编码器 ✅
```
CLIP-ViT-B-16:     150M  (HF Mirror)
Whisper-small:     242M  (HF Mirror)
Speech TTS:        209M  (已有)
```

### 图片数据 ✅
```
COCO-CN: 18,326张, 22,218条中文描述 (2.8GB)
  人工翻译+母语标注, 高质量
  剩余15张下载失败 (无影响)
```

### 数据源对比
```
图片:
  COCO-CN:     ⭐⭐⭐⭐⭐  18K中文原生
  AI Challenger: ⭐⭐⭐⭐⭐  30万中文 (国内源, 待下)
  B站视频帧:    ⭐⭐⭐☆☆  已有, 零下载

音频:
  B站视频:      ⭐⭐⭐⭐☆  105个, 零下载
  AISHELL-1:   ⭐⭐⭐⭐⭐  17万条 (国内源)
```

## 五、螺旋速度陷阱（核心发现）

```
50K步训练 (昨天): WorldModelV2 Decoder → DEPTH=1, 12层 → 0.6秒/步 → 14小时
24K步训练 (今天): SpiralDecoder      → DEPTH=7, 84层 → 30秒/步 → 200小时

根因: 螺旋每遍跑12层, 7遍=84层, 是普通Transformer的7倍
教训: 螺旋没学会走之前不能让它跑 — 先用DEPTH=1训基础能力
```

### 训练启动血泪史
```
尝试1: launch_finetune.py → CPU训练 (忘了.to('cuda'))
尝试2: Python312重跑 → 多进程抢GPU (清理不干净)
尝试3: train_v2.py → BPE预分词1小时未完成 (O(n²)中文分词)
尝试4: train_v3.py → 跑起来了但30秒/步 (螺旋7遍)
```

## 六、训练瓶颈诊断

```
【BPE分词瓶颈】
  5029文件 × 2000字 × 1.2 token/char = 12M tokens
  BPE encode: O(n²)对中文慢, 每文件0.3秒 → 5029个需25分钟
  解决思路: 分完词存SQLite, 训练时直接读 ← 明天第一件事

【螺旋速度瓶颈】
  DEPTH=7 × 12层 = 84层 forward/backward
  每次forward 30秒, 24000步需200小时
  解决: 先DEPTH=1训中文, 螺旋后面专项训
```

## 七、CUDA Torch 误删事件

```
问题: pip uninstall torch -y (没确认)
后果: 丢失CUDA torch, 重装多次失败
根因: 两个Python环境混淆
  venv (torch 2.12.1+cpu)
  Python312 (torch 2.11.0+cu128) ← 训练用的
修复: 直接用Python312路径运行
教训: 删包前必须确认, 环境隔离要明确
```

## 八、CC老师今天犯的错

```
1. pip uninstall -y → 不该跳过确认
2. 用错Python环境 → 没先检查which python
3. 忘加.to('cuda') → 启动前没验证
4. 启动GPU训练前没杀CPU进程 → 资源抢占
5. 多进程残留没清理 → 反复重启越积越多
6. BPE预分词超时没预估 → 不了解中文BPE耗时
7. 螺旋DEPTH=7直接训 → 没算计算量
```

## 九、明天计划

```
P0: 改DEPTH=1, 先训中文基础能力 (7小时)
P1: BPE分词缓存SQLite (省掉每epoch 25分钟)
P2: 中文能力验证 (实际对话测试)
P3: 图片对齐 (CLIP + COCO-CN, 冻结骨架训cross-attn)
P4: 螺旋专项训练 (中文OK后再加DEPTH=7)
```

## 十、长远架构思考

```
世界模型三阶段:
  Phase 1: 基础语言 (DEPTH=1, 中英双语)    ← 当前
  Phase 2: 多模态对齐 (CLIP+Whisper+cross) ← 数据已就绪
  Phase 3: 螺旋激活 (DEPTH=7, 7层思考)     ← 专项训练

魔改思路:
  拿 Qwen2.5-0.5B 预训练模型
  注入 think_modes + mode_proj
  改 forward 为 7-pass 循环
  但计算量更大 (24层×7=168层)
  → 先DEPTH=1, 螺旋是锦上添花不是雪中送炭
```

---

### 全项目指标

- 1次模型移植 (SmolLM2→SpiralDecoder)
- 84个权重矩阵移植
- 4,688篇中文训练数据 (1,270万字)
- 18,326张COCO图片
- 3个编码器就绪 (CLIP+Whisper+Speech)
- 7次训练启动尝试
- N次pip事故
- 1个核心发现: 螺旋计算量=普通模型×7
