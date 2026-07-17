# -*- coding: utf-8 -*-
"""CC老师 SpiralDecoder 50000步推理验收 (v18.5n)"""

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
log("  SpiralDecoder 50000步 推理验收")
log("=" * 55)

# ── 加载 ──
sys.path.insert(0, str(Path.home() / ".nexus"))

from nexus_agent.neural.wm_v2.spiral_decoder import SpiralDecoder
from nexus_agent.neural.wm_v2.wm_v2_tokenizer import BPETokenizer

DEVICE = "cpu"  # 用CPU免得抢训练GPU
log(f"\n设备: {DEVICE}")

# 加载 tokenizer
tok_path = Path.home() / ".nexus/data/wm_v2/tokenizer.json"
tokenizer = BPETokenizer.load(str(tok_path))
log(f"Tokenizer: {tokenizer.vocab_size} tokens")

# 创建模型 (与checkpoint一致的参数)
log("创建 SpiralDecoder...")
model = SpiralDecoder(
    dim=2048, heads_q=16, heads_kv=4, ff_dim=8192,
    cross_dim=256, vocab_size=65536, max_seq=4096
)
model.to(DEVICE)
model.eval()

# 加载权重
ckpt_path = Path.home() / ".nexus/data/wm_v2/checkpoints/best.pt"
ckpt = torch.load(ckpt_path, map_location=DEVICE, weights_only=False)
model.load_state_dict(ckpt['model'])
log(f"权重加载完成 (step={ckpt.get('step','?')}, loss={ckpt.get('loss','?'):.4f})")

# 统计参数
params = sum(p.numel() for p in model.parameters())
log(f"参数量: {params/1e9:.2f}B")
log(f"VRAM估计: {params*2/1e9:.1f}GB (FP16)")

# ── 推理测试 ──
log(f"\n{'='*55}")
log("  推理测试")
log("=" * 55)

tests = [
    ("Python代码", "def fibonacci(n):"),
    ("Python函数", "def quicksort(arr):"),
    ("英文补全", "The capital of France is"),
    ("中文测试", "Python是一种"),
]

for name, prompt in tests:
    log(f"\n[{name}] 输入: {prompt}")
    try:
        ids = tokenizer.encode(prompt)
        input_tensor = torch.tensor([ids], device=DEVICE)
        
        with torch.no_grad():
            out = model(input_tensor, return_logits=True, return_confidences=True)
        
        logits = out['logits']
        confidences = out.get('confidences', [])
        
        # 取top-5预测
        next_logits = logits[0, -1, :]
        top5_vals, top5_ids = torch.topk(next_logits, 5)
        
        predictions = []
        for val, tid in zip(top5_vals, top5_ids):
            token = tokenizer.decode([tid.item()])
            prob = torch.softmax(next_logits, dim=-1)[tid].item()
            predictions.append(f"{token!r} ({prob:.3f})")
        
        log(f"  Top-5: {', '.join(predictions)}")
        
        # 思考模式置信度
        mode_names = ['Understand', 'Reflect', 'Retrieve', 'Plan', 'Execute', 'Verify', 'Learn']
        if confidences:
            conf_str = ' -> '.join(f'{mode_names[i][:4]}:{confidences[i].item():.2f}' 
                                  for i in range(min(len(confidences), 7)))
            log(f"  螺旋置信度: {conf_str}")
        
        # Perplexity on this prompt
        target_ids = ids[1:] + [0]  # shift
        loss = torch.nn.functional.cross_entropy(
            logits[0, :len(target_ids), :], 
            torch.tensor(target_ids, device=DEVICE)
        )
        log(f"  Loss: {loss.item():.4f} (ppl={math.exp(loss.item()):.1f})")
        
    except Exception as e:
        log(f"  ❌ 失败: {e}")

# ── 尝试 generate ──
log(f"\n[生成测试]")
test_prompts = [
    "def hello():",
    "# 快速排序算法",
]

for prompt in test_prompts:
    log(f"\n  输入: {prompt}")
    try:
        ids = tokenizer.encode(prompt)
        input_tensor = torch.tensor([ids], device=DEVICE)
        
        with torch.no_grad():
            generated = model.generate(
                input_tensor, 
                max_new_tokens=20,
                temperature=0.3,
                top_p=0.9,
                top_k=30,
            )
        
        output = tokenizer.decode(generated[0].tolist())
        log(f"  输出: {output[:200]}")
    except Exception as e:
        log(f"  ❌ 失败: {e}")

log(f"\n{'='*55}")
log(f"  验收完成!")
log(f"{'='*55}")
