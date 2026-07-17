# -*- coding: utf-8 -*-
"""WorldModel Message Hub — 消息驱动的模块中枢 (v18.5n)

设计哲学:
  - 所有模块只发消息给 WM, 不直接调用 WM
  - WM 串行处理消息, 不嵌套, 不回调
  - 永不卡死 (前车之鉴: 回调链 await 死循环爆内存)

消息类型:
  wm.gap_found        → MetaCognition 发现能力缺口
  wm.code_ready       → SelfPlay 产出验证通过的代码
  wm.knowledge_added  → KnowledgeGen/EvoKG 新增知识
  wm.paper_studied    → ResearchEngine 精读完论文
  wm.curiosity_target → CuriosityEngine 建议探索方向
  wm.strategy_updated → StrategyAudit 策略权重调整
  wm.node_observed    → 外部数据注入 WM 节点
  wm.external_ready   → ExternalFetcher 凌晨下载完成

处理策略:
  1. 消息入队 (非阻塞, 微秒级)
  2. WM 定时批处理 (每秒取一批)
  3. 处理: 更新内部状态、更新索引、触发训练
  4. 满队: 合并同类消息, 超限丢弃最旧
"""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("nexus.wm")


@dataclass
class WMMessage:
    """A message sent from a Nexus module to WorldModel."""
    type: str           # e.g. "wm.gap_found"
    source: str         # module name
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    priority: int = 0   # 0=normal, 1=important, 2=critical


class WMMessageHub:
    """Central message hub between all Nexus modules and WorldModel.

    Usage:
        hub = WMMessageHub(world_model, max_queue=1000, batch_size=50)

        # Modules send messages (fire-and-forget)
        hub.post("wm.gap_found", "meta_cognition",
                 {"domain": "math", "severity": 0.8})

        # WM processes them in batches
        await hub.process_batch()
    """

    def __init__(self, world_model=None, max_queue: int = 1000, batch_size: int = 50):
        self.wm = world_model
        self.max_queue = max_queue
        self.batch_size = batch_size
        self._queue: deque = deque(maxlen=max_queue)
        self._handlers: Dict[str, Callable] = {}
        self._stats = {
            "received": 0, "processed": 0, "dropped": 0,
            "merged": 0, "errors": 0,
        }
        self._last_batch = 0.0
        self._registered = False

        # Register default handlers
        self._register_defaults()

    # ═══════════════════════════════════════════════════════
    # Post (modules → WM, non-blocking)
    # ═══════════════════════════════════════════════════════

    def post(self, msg_type: str, source: str, data: Dict = None,
             priority: int = 0):
        """Post a message to the WorldModel. Non-blocking, fire-and-forget.

        Args:
            msg_type: message type (e.g. "wm.gap_found")
            source: sending module name
            data: payload dict
            priority: 0=normal, 1=important, 2=critical
        """
        msg = WMMessage(
            type=msg_type, source=source,
            data=data or {}, priority=priority,
        )

        # Merge: if same type+source exists in queue, update it
        merged = False
        for i in range(len(self._queue) - 1, -1, -1):
            existing = self._queue[i]
            if (existing.type == msg_type and existing.source == source and
                existing.priority <= priority):
                existing.data.update(data or {})
                existing.timestamp = time.time()
                existing.priority = max(existing.priority, priority)
                self._stats["merged"] += 1
                merged = True
                break

        if not merged:
            if len(self._queue) >= self.max_queue:
                self._queue.popleft()  # Drop oldest
                self._stats["dropped"] += 1
            self._queue.append(msg)

        self._stats["received"] += 1
        logger.debug("[WMHub] %s ← %s (queue=%d)", msg_type, source, len(self._queue))

    def post_async(self, msg_type: str, source: str,
                   data: Dict = None, priority: int = 0):
        """Thread-safe async post (can be called from any thread)."""
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(
                lambda: self.post(msg_type, source, data, priority)
            )
        except RuntimeError:
            self.post(msg_type, source, data, priority)

    # ═══════════════════════════════════════════════════════
    # Process (WM batch processing)
    # ═══════════════════════════════════════════════════════

    async def process_batch(self) -> Dict:
        """Process a batch of queued messages. Called periodically.

        Returns:
            {processed, errors, remaining}
        """
        if not self._queue:
            return {"processed": 0, "errors": 0, "remaining": 0}

        batch = []
        for _ in range(min(self.batch_size, len(self._queue))):
            batch.append(self._queue.popleft())

        # Sort by priority (critical first)
        batch.sort(key=lambda m: -m.priority)

        processed = 0
        errors = 0

        for msg in batch:
            try:
                handler = self._handlers.get(msg.type)
                if handler:
                    result = handler(msg)
                    if asyncio.iscoroutine(result):
                        await result
                    processed += 1
                else:
                    logger.debug("[WMHub] No handler for: %s", msg.type)
            except Exception as e:
                logger.warning("[WMHub] Handler error for %s: %s", msg.type, e)
                errors += 1

        self._stats["processed"] += processed
        self._stats["errors"] += errors
        self._last_batch = time.time()

        return {
            "processed": processed,
            "errors": errors,
            "remaining": len(self._queue),
        }

    # ═══════════════════════════════════════════════════════
    # Auto-subscribe to Nexus EventBus
    # ═══════════════════════════════════════════════════════

    def subscribe_to_eventbus(self):
        """Register to receive events from Nexus EventBus.

        Bridges Nexus's existing publish/subscribe system into the
        WorldModel message queue. Avoids the callback-chain deadlock.
        """
        if self._registered:
            return

        try:
            from nexus_agent.event_bus import get_event_bus
            bus = get_event_bus()

            # Map EventBus events → WM message types
            event_map = {
                "experience.added":     ("wm.code_ready", 0),
                "world_model.node_added": ("wm.node_observed", 0),
                "knowledge.completed":  ("wm.knowledge_added", 1),
                "research.finding.verified": ("wm.paper_studied", 1),
                "self_play.round_done": ("wm.code_ready", 0),
                "external.code_added":  ("wm.external_ready", 0),
                "gap.discovered":       ("wm.gap_found", 2),
            }

            for event_type, (wm_type, priority) in event_map.items():
                bus.subscribe(
                    event_type,
                    lambda e, t=wm_type, p=priority:
                        self.post(t, e.get("source", "event_bus"),
                                  e.data if hasattr(e, 'data') else {}, p),
                    async_mode=True,
                )

            self._registered = True
            logger.info("[WMHub] Subscribed to %d EventBus events", len(event_map))
        except Exception as e:
            logger.debug("[WMHub] EventBus unavailable: %s", e)

    # ═══════════════════════════════════════════════════════
    # Handlers
    # ═══════════════════════════════════════════════════════

    def _register_defaults(self):
        """Register default message handlers."""
        self._handlers.update({
            "wm.gap_found":        self._handle_gap_found,
            "wm.code_ready":       self._handle_code_ready,
            "wm.knowledge_added":  self._handle_knowledge_added,
            "wm.paper_studied":    self._handle_paper_studied,
            "wm.curiosity_target": self._handle_curiosity_target,
            "wm.strategy_updated": self._handle_strategy_updated,
            "wm.node_observed":    self._handle_node_observed,
            "wm.external_ready":   self._handle_external_ready,
        })

    async def _handle_gap_found(self, msg: WMMessage):
        """MetaCognition found a capability gap → mark for priority learning."""
        domain = msg.data.get("domain", "general")
        severity = msg.data.get("severity", 0.5)
        logger.info("[WMHub] Gap found: %s (%.2f)", domain, severity)
        if self.wm:
            # Index as high-priority learning target
            self.wm.index_documents(
                [f"LEARNING_PRIORITY: {domain} (severity={severity:.2f})"],
                [{"type": "gap", "domain": domain, "severity": severity}]
            )

    async def _handle_code_ready(self, msg: WMMessage):
        """SelfPlay produced verified code → add to training queue."""
        code = msg.data.get("solution", msg.data.get("code", ""))
        domain = msg.data.get("domain", "unknown")
        score = msg.data.get("score", msg.data.get("significance", 0.5))
        if code and len(code) > 50 and score > 0.6:
            if self.wm:
                self.wm.index_documents(
                    [code[:2000]],
                    [{"type": "code_sample", "domain": domain, "score": score}]
                )

    async def _handle_knowledge_added(self, msg: WMMessage):
        """KnowledgeGen/EvoKG added knowledge → update index."""
        content = msg.data.get("content", "")
        if content and len(content) > 20:
            if self.wm:
                self.wm.index_documents(
                    [content[:2000]],
                    [{"type": "knowledge", "source": msg.source}]
                )

    async def _handle_paper_studied(self, msg: WMMessage):
        """ResearchEngine finished studying a paper."""
        finding = msg.data.get("finding", "")
        confidence = msg.data.get("confidence", 0.5)
        if finding and confidence > 0.4:
            if self.wm:
                self.wm.index_documents(
                    [finding[:2000]],
                    [{"type": "research_finding", "confidence": confidence}]
                )

    async def _handle_curiosity_target(self, msg: WMMessage):
        """CuriosityEngine suggests exploration target."""
        target = msg.data.get("target", "")
        logger.info("[WMHub] Curiosity target: %s", target[:80])

    async def _handle_strategy_updated(self, msg: WMMessage):
        """StrategyAudit updated weights."""
        top = msg.data.get("top_strategies", [])
        if top:
            logger.info("[WMHub] Strategy updated: %s", top[0])

    async def _handle_node_observed(self, msg: WMMessage):
        """New WM node from external data."""
        modality = msg.data.get("modality", "text")
        label = msg.data.get("label", "")[:80]
        logger.debug("[WMHub] Node observed: [%s] %s", modality, label)

    async def _handle_external_ready(self, msg: WMMessage):
        """ExternalFetcher downloaded new data."""
        count = msg.data.get("count", 0)
        source_type = msg.data.get("source_type", "papers")
        logger.info("[WMHub] External data ready: %s x%d", source_type, count)

    # ═══════════════════════════════════════════════════════
    # Stats
    # ═══════════════════════════════════════════════════════

    def get_stats(self) -> Dict:
        return {
            **self._stats,
            "queue_size": len(self._queue),
            "handlers": len(self._handlers),
            "last_batch_age": time.time() - self._last_batch,
        }


# ═══════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════

_hub: Optional[WMMessageHub] = None


def get_wm_hub(world_model=None) -> WMMessageHub:
    global _hub
    if _hub is None and world_model is not None:
        _hub = WMMessageHub(world_model)
        _hub.subscribe_to_eventbus()
    elif _hub is not None and world_model is not None and _hub.wm is None:
        _hub.wm = world_model
    return _hub


# ═══════════════════════════════════════════════════════════
# Convenience: module-side post function
# ═══════════════════════════════════════════════════════════

def wm_post(msg_type: str, source: str, data: Dict = None, priority: int = 0):
    """Module-side convenience: post message to WorldModel.

    Usage from any Nexus module:
        from nexus_agent.neural.wm_v2.wm_hub import wm_post
        wm_post("wm.gap_found", "meta_cognition",
                {"domain": "math", "severity": 0.8})
    """
    hub = _hub
    if hub is None:
        hub = WMMessageHub()  # No WM yet, queue only
    hub.post(msg_type, source, data, priority)
