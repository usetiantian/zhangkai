# -*- coding: utf-8 -*-
"""NexusDense — 最小最强, 不模仿大厂 (v18.5n)

Why not MoE:
  MoE = 8 experts, top-2 routing = 75% params idle.
  For ONE user, ONE personal AI: every param should work every time.

Why not Llama's 32L:
  Deep = more sequential computation = slower for the same VRAM.
  Wide (16L x 2048dim) > Deep (32L x 1024dim) for single-user inference.

Design:
  - 16 layers, 2048 hidden dim, 16 GQA heads
  - Dense FFN (no experts), SwiGLU activation
  - All ~1.2B params active every token
  - BF16 training: ~5GB VRAM
  - Inference: ~2.5GB VRAM

The innovation:
  Not "cram more params into 16GB"
  But "every param actually earns its keep"
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Tuple, List

from .wm_v2_decoder import RotaryEmbedding, apply_rotary_pos_emb, RMSNorm, GroupedQueryAttention


class DenseSwiGLU(nn.Module):
    """Dense feed-forward with SwiGLU. No expert routing.

    SwiGLU: gate(x) * up(x) where gate = SiLU(x @ w1)
    Proven by PaLM/Llama: better than ReLU, equal to MoE for single-user.
    """

    def __init__(self, dim: int, hidden_dim: int):
        super().__init__()
        self.w1 = nn.Linear(dim, hidden_dim, bias=False)  # gate
        self.w2 = nn.Linear(dim, hidden_dim, bias=False)  # up
        self.w3 = nn.Linear(hidden_dim, dim, bias=False)  # down

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        gate = F.silu(self.w1(x))
        up = self.w2(x)
        return self.w3(gate * up)


class DenseDecoderLayer(nn.Module):
    """Single decoder layer: Self-GQA → Cross-GQA → DenseFFN.

    No MoE, no expert routing. Every param active.
    """

    def __init__(self, dim: int, heads_q: int, heads_kv: int, ff_dim: int,
                 cross_dim: int, max_seq: int, dropout: float = 0.0, layer_idx: int = 0):
        super().__init__()
        self.layer_idx = layer_idx
        head_dim = dim // heads_q

        # Self-attention
        self.self_attn = GroupedQueryAttention.__new__(GroupedQueryAttention)
        GroupedQueryAttention.__init__(self.self_attn, type('C', (), {
            'decoder_dim': dim, 'decoder_heads_q': heads_q, 'decoder_heads_kv': heads_kv,
            'decoder_max_seq': max_seq,
        })())
        self.self_norm = RMSNorm(dim)

        # Cross-attention (to encoder output)
        self.cross_q = nn.Linear(dim, dim, bias=False)
        self.cross_k = nn.Linear(cross_dim, heads_kv * head_dim, bias=False)
        self.cross_v = nn.Linear(cross_dim, heads_kv * head_dim, bias=False)
        self.cross_o = nn.Linear(dim, dim, bias=False)
        self.cross_norm = RMSNorm(dim)

        # Dense FFN (not MoE)
        self.ffn = DenseSwiGLU(dim, ff_dim)
        self.ffn_norm = RMSNorm(dim)

        self.head_dim = head_dim
        self.heads_q = heads_q
        self.heads_kv = heads_kv
        self.n_groups = heads_q // heads_kv

    def forward(self, x, encoder_output=None, kv_cache=None, mask=None):
        # Self-attention
        residual = x
        x_norm = self.self_norm(x)
        attn_out, new_kv = self.self_attn(x_norm, kv_cache=kv_cache, mask=mask)
        x = residual + attn_out

        # Cross-attention
        if encoder_output is not None:
            residual = x
            x_norm = self.cross_norm(x)
            B, T, D = x_norm.shape

            q = self.cross_q(x_norm).view(B, T, self.heads_q, self.head_dim).transpose(1, 2)
            kv_dim = self.heads_kv * self.head_dim
            k = self.cross_k(encoder_output).view(B, -1, self.heads_kv, self.head_dim).transpose(1, 2)
            v = self.cross_v(encoder_output).view(B, -1, self.heads_kv, self.head_dim).transpose(1, 2)
            k = k.repeat_interleave(self.n_groups, dim=1)
            v = v.repeat_interleave(self.n_groups, dim=1)

            cross_out = F.scaled_dot_product_attention(q, k, v, scale=1.0 / math.sqrt(self.head_dim))
            cross_out = cross_out.transpose(1, 2).contiguous().view(B, T, D)
            x = residual + self.cross_o(cross_out)

        # Dense FFN
        residual = x
        x = residual + self.ffn(self.ffn_norm(x))

        return x, new_kv


class DenseDecoder(nn.Module):
    """16-layer dense decoder. No MoE, every param active.

    ~1.2B params, ~2.5GB inference, ~5GB training VRAM.
    """

    def __init__(self, dim: int = 2048, layers: int = 16,
                 heads_q: int = 16, heads_kv: int = 4,
                 ff_dim: int = 8192, cross_dim: int = 256,
                 vocab_size: int = 65536, max_seq: int = 4096,
                 dropout: float = 0.0):
        super().__init__()
        self.dim = dim
        self.layers_count = layers

        self.tok_embed = nn.Embedding(vocab_size, dim)
        self.layers = nn.ModuleList([
            DenseDecoderLayer(dim, heads_q, heads_kv, ff_dim, cross_dim, max_seq, dropout, i)
            for i in range(layers)
        ])
        self.norm = RMSNorm(dim)
        self.lm_head = nn.Linear(dim, vocab_size, bias=False)
        self.lm_head.weight = self.tok_embed.weight  # Tie weights

        self.apply(self._init_weights)

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            residual_scale = 1.0 / math.sqrt(2.0 * self.layers_count)
            is_output = hasattr(module, 'weight') and module.weight.size(0) == self.dim
            std = 0.02 * residual_scale if is_output else 0.02
            nn.init.normal_(module.weight, mean=0.0, std=std)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(self, input_ids, encoder_output=None, kv_caches=None, mask=None,
                return_logits=True, use_checkpoint=False):
        x = self.tok_embed(input_ids)
        new_kv_caches = []

        for i, layer in enumerate(self.layers):
            kv_cache = kv_caches[i] if kv_caches else None
            if use_checkpoint and self.training:
                x, new_kv = torch.utils.checkpoint.checkpoint(
                    lambda _x: layer(_x, encoder_output, kv_cache, mask)[:2],
                    x, use_reentrant=True
                )
            else:
                x, new_kv = layer(x, encoder_output, kv_cache, mask)
            new_kv_caches.append(new_kv)

        x = self.norm(x)
        return {
            "hidden_states": x,
            "logits": self.lm_head(x) if return_logits else None,
            "new_kv_caches": new_kv_caches,
            "aux_loss": torch.tensor(0.0, device=x.device),  # No MoE = no aux loss
        }

    @torch.no_grad()
    def generate(self, input_ids, encoder_output, max_new_tokens=256,
                 temperature=0.7, top_p=0.9, top_k=50, eos_token_id=2):
        B, T = input_ids.shape
        generated = input_ids.clone()
        kv_caches = None

        for _ in range(max_new_tokens):
            current = generated[:, -1:] if kv_caches else generated
            out = self.forward(current, encoder_output, kv_caches, return_logits=True)
            kv_caches = out["new_kv_caches"]

            next_logits = out["logits"][:, -1, :] / temperature
            if top_k > 0:
                tk_vals, _ = torch.topk(next_logits, top_k, dim=-1)
                next_logits[next_logits < tk_vals[:, -1:]] = float('-inf')
            if top_p < 1.0:
                sorted_l, sorted_i = torch.sort(next_logits, descending=True)
                cum_p = torch.cumsum(F.softmax(sorted_l, dim=-1), dim=-1)
                remove = cum_p > top_p
                remove[:, 1:] = remove[:, :-1].clone()
                remove[:, 0] = False
                next_logits[remove.scatter(1, sorted_i, remove)] = float('-inf')

            probs = F.softmax(next_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            generated = torch.cat([generated, next_token], dim=1)
            if (next_token == eos_token_id).all(): break

        return generated
