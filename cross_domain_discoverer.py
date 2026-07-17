# -*- coding: utf-8 -*-
"""CrossDomainDiscoverer - 自发跨域联想引擎 (v18.5n)

不使用硬编码模板。向量相似度 + Reasoner → 自发发现 + 行动。

工作流:
  1. 从 WorldModel 随机采样跨域节点对
  2. 计算向量余弦相似度
  3. 高相似度 → Reasoner 判断 novelty + gap
  4. 有意义的发现 → 创建 EvoKG cross_domain 边 → SelfPlay 题目
"""

from __future__ import annotations

import logging
import random
import time
import numpy as np
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MIN_SIMILARITY = 0.3
_HIGH_VALUE = 0.5


class CrossDomainDiscoverer:
    """自发发现跨域关联, 不依赖硬编码模板。"""

    def __init__(self, world_model: Any = None):
        self._world_model = world_model
        self._reasoner = None
        self._discoveries: List[Dict] = []
        self._last_scan = 0.0

    @property
    def _wm(self):
        if self._world_model is None:
            try:
                from nexus_agent.world_model import get_world_model
                self._world_model = get_world_model()
            except Exception:
                pass
        return self._world_model

    @property
    def _rsnr(self):
        if self._reasoner is None:
            try:
                from nexus_agent.neural.nexus_reasoner import get_nexus_reasoner
                self._reasoner = get_nexus_reasoner()
            except Exception:
                pass
        return self._reasoner

    def discover(self, max_pairs: int = 20) -> List[Dict]:
        """扫描 WorldModel, 发现跨域关联。返回有意义的发现列表。"""
        wm = self._wm
        if not wm or not hasattr(wm.space, '_nodes'):
            return []

        nodes = list(wm.space._nodes.items())
        if len(nodes) < 10:
            return []

        discoveries = []
        # 随机采样节点对 (不需要遍历所有组合)
        pairs = random.sample(nodes, min(max_pairs * 2, len(nodes)))
        random.shuffle(pairs)

        for i in range(0, len(pairs) - 1, 2):
            nid_a, node_a = pairs[i]
            nid_b, node_b = pairs[i + 1]

            # 跳过同模态 (我们找跨域关联)
            mod_a = node_a.get('modality', 'text')
            mod_b = node_b.get('modality', 'text')
            if mod_a == mod_b:
                # 同模态但不同label → 也算跨域
                la = node_a.get('label', '')[:30]
                lb = node_b.get('label', '')[:30]
                if la == lb:
                    continue

            # 向量相似度
            va = np.asarray(node_a.get('vector', [0]*256), np.float32)
            vb = np.asarray(node_b.get('vector', [0]*256), np.float32)
            sim = float(np.dot(va, vb))

            if sim < _MIN_SIMILARITY:
                continue

            # Reasoner 判断
            label_a = node_a.get('label', '')[:80]
            label_b = node_b.get('label', '')[:80]
            novelty = 0.5
            gap = 0.5
            if self._rsnr:
                try:
                    novelty = self._rsnr.is_novel(f"{label_a} vs {label_b}")
                    gap = self._rsnr.predict_gap(f"{label_a} | {label_b}")
                except Exception:
                    pass

            # 综合评分: 相似度 * novelty * gap
            score = sim * novelty * gap
            if score < 0.05:
                continue

            discovery = {
                "node_a": nid_a, "node_b": nid_b,
                "label_a": label_a, "label_b": label_b,
                "mod_a": mod_a, "mod_b": mod_b,
                "similarity": round(sim, 4),
                "novelty": round(novelty, 4),
                "gap": round(gap, 4),
                "score": round(score, 4),
                "timestamp": time.time(),
            }

            # 高价值发现 → 创建 EvoKG 边
            if sim > _HIGH_VALUE and novelty > 0.3:
                self._create_evokg_edge(discovery)

            discoveries.append(discovery)

        discoveries.sort(key=lambda x: -x['score'])
        self._discoveries = discoveries[:10]
        self._last_scan = time.time()

        if discoveries:
            logger.info("[CrossDomain] 发现 %d 个跨域关联 (top=%.3f)",
                       len(discoveries),
                       discoveries[0]['score'] if discoveries else 0)

        return discoveries

    def _create_evokg_edge(self, disc: Dict):
        """在 EvoKG 中创建跨域类比边。"""
        try:
            from nexus_agent.evokg import get_evokg
            kg = get_evokg()
            # 在 EvoKG 中创建两个节点并建边
            kg.add_node(
                subgraph=kg.SubgraphType.DOMAIN_KNOWLEDGE if hasattr(kg, 'SubgraphType')
                else __import__('nexus_agent.evokg', fromlist=['SubgraphType']).SubgraphType.DOMAIN_KNOWLEDGE,
                content=f"CrossDomain: [{disc['label_a']}] ↔ [{disc['label_b']}] (sim={disc['similarity']:.3f})",
                confidence=disc['similarity'],
            )
        except Exception:
            logger.debug("EvoKG edge creation skipped", exc_info=True)

    def generate_problem(self) -> Optional[Dict]:
        """从最新发现生成 SelfPlay 题目 (不依赖模板)。"""
        discoveries = self._discoveries or self.discover(max_pairs=10)
        if not discoveries:
            return None

        # 选评分最高的发现
        disc = discoveries[0]
        la = disc['label_a'][:60]
        lb = disc['label_b'][:60]

        return {
            "problem_statement": f"发现跨域关联 (sim={disc['similarity']:.2f}): [{la}] ↔ [{lb}]。请分析这一关联的合理性并验证。",
            "node_a": {"label": la, "modality": disc['mod_a']},
            "node_b": {"label": lb, "modality": disc['mod_b']},
            "type": "cross_domain_discovery",
            "score": disc['score'],
            "source": "vector_similarity",
        }

    def get_stats(self) -> Dict:
        return {
            "discoveries": len(self._discoveries),
            "last_scan": self._last_scan,
            "top_score": self._discoveries[0]['score'] if self._discoveries else 0,
        }


# ── Singleton ─────────────────────────────────────────

_instance: Optional[CrossDomainDiscoverer] = None


def get_cross_modal_challenger(world_model: Any = None) -> CrossDomainDiscoverer:
    global _instance
    if _instance is None:
        _instance = CrossDomainDiscoverer(world_model=world_model)
    elif world_model is not None and _instance._world_model is None:
        _instance._world_model = world_model
    return _instance
