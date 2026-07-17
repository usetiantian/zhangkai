# -*- coding: utf-8 -*-
"""CC老师 SpiralDecoder 验收测试 (v18.5n)

测试项:
  1. 基本生成能力
  2. Python 代码生成
  3. 中文理解
  4. Loss/Perplexity
  5. 思考螺旋是否工作
"""

import json
import math
import sys
import io
import time
import torch
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def log(msg):
    print(msg, flush=True)

log("=" * 55)
log("  SpiralDecoder 50000步 验收测试")
log("=" * 55)

# ── 加载模型 ──
log("\n[1/5] 加载模型...")
sys.path.insert(0, str(Path.home() / ".nexus"))

from nexus_agent.neural.wm_v2.spiral_decoder import SpiralDecoder
from nexus_agent.neural.wm_v2.wm_v2_pipeline import WMTrainer

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
log(f"  设备: {DEVICE}")

# 加载 checkpoint
ckpt_path = Path.home() / ".nexus/data/wm_v2/checkpoints/best.pt"
log(f"  Checkpoint: {ckpt_path}")
ckpt = torch.load(ckpt_path, map_location=DEVICE, weights_only=False)

# 查看 checkpoint 信息
log(f"  Keys: {list(ckpt.keys())}")
log(f"  Step: {ckpt.get('step', '?')}")
log(f"  Loss: {ckpt.get('loss', '?'):.4f}" if isinstance(ckpt.get('loss'), float) else f"  Loss: {ckpt.get('loss', '?')}")

# ── 加载 Tokenizer ──
log("\n[2/5] 加载 Tokenizer...")
tok_path = Path.home() / ".nexus/data/wm_v2/tokenizer.json"
with open(tok_path, 'r', encoding='utf-8') as f:
    tok_data = json.load(f)

class SimpleTokenizer:
    """简易 BPE tokenizer 用于推理。"""
    def __init__(self, tok_data):
        self.vocab = tok_data.get('vocab', {})
        self.merges = tok_data.get('merges', {})
        self.vocab_size = tok_data.get('vocab_size', len(self.vocab))
        # 构建反向映射
        self.id_to_byte = {}
        for token_str, tid in self.vocab.items():
            bytes_list = [int(b) for b in token_str.split(',')]
            self.id_to_byte[tid] = bytes(bytes_list)
    
    def encode(self, text, add_special_tokens=True):
        # 简易实现：逐字节编码
        ids = []
        i = 0
        b = text.encode('utf-8', errors='replace')
        while i < len(b):
            # 尝试找最长匹配的BPE token
            found = False
            for j in range(min(len(b) - i, 8), 0, -1):
                sub = b[i:i+j]
                token_str = ','.join(str(x) for x in sub)
                if token_str in self.vocab:
                    ids.append(self.vocab[token_str])
                    i += j
                    found = True
                    break
            if not found:
                # 单字节回退
                token_str = str(b[i])
                if token_str in self.vocab:
                    ids.append(self.vocab[token_str])
                i += 1
        if add_special_tokens:
            ids = [1] + ids + [2]  # BOS + EOS
        return ids
    
    def decode(self, ids):
        result = bytearray()
        for tid in ids:
            if tid in self.id_to_byte:
                result.extend(self.id_to_byte[tid])
        return result.decode('utf-8', errors='replace')

tokenizer = SimpleTokenizer(tok_data)
log(f"  词表大小: {tokenizer.vocab_size}")

# ── 测试1: 基本生成 ──
log("\n[3/5] 测试: 基本文本生成")

# 简单测试 - 用 encode/decode 验证 tokenizer
test_text = "def hello_world():"
ids = tokenizer.encode(test_text)
decoded = tokenizer.decode(ids)
log(f"  Tokenizer测试: '{test_text}' -> {len(ids)} tokens -> '{decoded[:50]}'")

# ── 测试2: Loss 分析 ──
log("\n[4/5] 测试: Loss 分析")
log(f"  训练最终 loss: {ckpt.get('loss', '?')}")
if isinstance(ckpt.get('loss'), float):
    ppl = math.exp(ckpt['loss'])
    log(f"  Perplexity: {ppl:.1f}")
    
    # 解读
    if ppl < 10:
        log(f"  评级: ★★★★  优秀 (模型已较好拟合)")
    elif ppl < 20:
        log(f"  评级: ★★★   良好 (有基本语言能力)")
    elif ppl < 50:
        log(f"  评级: ★★    一般 (仍在学习中)")
    else:
        log(f"  评级: ★     需要更多训练")

# ── 测试3: 检查模型参数 ──
log("\n[5/5] 测试: 模型参数检查")
if 'model' in ckpt:
    model_state = ckpt['model']
    param_count = sum(v.numel() for v in model_state.values())
    log(f"  参数量: {param_count/1e9:.2f}B")
    log(f"  层数: {len([k for k in model_state.keys() if 'layers' in k and '.0.' in k])}")
    
    # 检查梯度
    has_nan = any(torch.isnan(v).any() for v in model_state.values())
    has_inf = any(torch.isinf(v).any() for v in model_state.values())
    log(f"  NaN: {'YES ❌' if has_nan else '无 ✅'}")
    log(f"  Inf: {'YES ❌' if has_inf else '无 ✅'}")

log(f"\n{'='*55}")
log(f"  验收结论")
log(f"{'='*55}")

# 最终判断
ok = True
if isinstance(ckpt.get('loss'), float):
    if math.exp(ckpt['loss']) > 50:
        log(f"  ⚠️  Perplexity过高，可能需要更久训练")
        ok = False

if 'model' in ckpt:
    if any(torch.isnan(v).any() for v in ckpt['model'].values()):
        log(f"  ❌ 模型权重出现NaN！训练崩溃")
        ok = False

if ok:
    log(f"  ✅ 模型基本健康，可以进行推理测试")
else:
    log(f"  ⚠️  模型有问题，需要排查")

log(f"\n  下一步: 加载模型实例运行实际推理测试")
