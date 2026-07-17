# -*- coding: utf-8 -*-
"""
Agent Response — standalone functions extracted from NexusAgent in run_agent.py.

Extracted to reduce file size (was 3,682 lines in one class with 72 methods).
Every function takes an explicit `agent` parameter instead of accessing `self`.

Functions extracted:
  - build_single_tool_schema(name)        — pure, no agent dependency
  - build_tool_schemas(agent)             — builds OpenAI-format tool schemas
  - build_constrained_tool_schemas(agent, pre_analysis) — Nexus-constrained schemas
  - nexus_pre_analyze(agent, content)     — zero-LLM heuristic pre-analysis
  - nexus_validate_tool_calls(calls, pre_analysis) — validates LLM tool selection
  - nexus_record_tool_pattern(content, calls, pre_analysis, success) — ExperienceBank logging
  - dispatch_tool_or_skill(agent, tool_name, params) — unified tool/skill dispatcher
  - try_execute_tool(agent, response)     — JSON parse and execute tool from LLM text
  - generate_response(agent, content, stream_callback) — main response generation loop
"""

import asyncio
import json
import logging
import re
import time
from typing import Dict, Optional

from nexus_agent.event_emitter import EventType, emit
from nexus_agent.tool_router import get_router
from nexus_agent.constants import get_nexus_home

logger = logging.getLogger(__name__)


async def _try_brain_fallback(agent, content: str) -> Optional[Dict]:
    """v9.8: LLM 失败时的本地模型兜底。

    仅在 LLM 全部不可用或异常时调用，不作为前置路由。
    与 _try_brain 的核心区别：不采集训练样本（防止自毒化）。
    """
    try:
        from nexus_agent.nexus_brain import get_brain

        lm = get_brain()
        if not lm.ensure_loaded():
            return None

        logger.info("[Fallback] Brain 兜底尝试: %d chars prompt", len(content))

        import asyncio as _asyncio
        loop = _asyncio.get_running_loop()
        try:
            resp = await _asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: lm.chat(
                        content,
                        system_prompt="你是 Nexus，一个 Windows 原生 AI 助手。能力: 编程、文件管理、图片识别、语音识别、知识问答、网页搜索。遇到需要实时信息的问题请主动调用搜索工具。用中文简洁回答。",
                        max_tokens=512,
                        temperature=0.3,
                    ),
                ),
                timeout=30.0,
            )
        except _asyncio.TimeoutError:
            logger.warning("[Fallback] Brain 超时")
            return None

        if not resp or len(resp) < 10:
            return None

        logger.info("[Fallback] Brain 兜底成功: %d chars", len(resp))
        return {
            "status": "ok",
            "content": resp,
            "source": "brain_fallback",
            "no_llm": True,
        }
    except Exception as e:
        logger.debug("[Fallback] Brain 不可用: %s", e)
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Vision / Image Helpers
# ═══════════════════════════════════════════════════════════════════════════

# Vision-capable Ollama model prefixes (models that support image input)
_VISION_MODEL_PREFIXES = (
    "llava",
    "bakllava",
    "llava-llama3",
    "minicpm-v",
    "gemma3",
    "cogvlm",
    "fuyu",
    "moondream",
    "qwen-vl",
    "phi3-vision",
    "pixtral",
    "granite3.2-vision",
)

_VISION_MODEL_KEYWORDS = ("vision", "vl", "multimodal")


def _is_vision_model(model_name: str) -> bool:
    """Check if the current model supports vision/image input."""
    if not model_name:
        return False
    name = model_name.lower()
    for prefix in _VISION_MODEL_PREFIXES:
        if name.startswith(prefix):
            return True
    for kw in _VISION_MODEL_KEYWORDS:
        if kw in name:
            return True
    return False


def _find_local_vision_model() -> str | None:
    """探测本地 Ollama 中的多模态视觉模型。

    v10.4: 飞书图片 base64 直传需要视觉模型。
    优先级: NEXUS_TIER1_MODEL 环境变量 > Ollama 模型列表中的第一个 VL 模型。
    """
    # 1. 优先使用环境变量指定的模型
    tier1 = os.environ.get("NEXUS_TIER1_MODEL", "")
    if tier1 and _is_vision_model(tier1):
        return tier1

    # 2. 查询 Ollama 模型列表
    try:
        import urllib.request, json as _json
        ollama_url = os.environ.get(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        ).rstrip("/")
        req = urllib.request.Request(f"{ollama_url}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = _json.loads(resp.read().decode())
            models = [m.get("name", "") for m in data.get("models", [])]
            for m in models:
                if _is_vision_model(m):
                    return m
    except Exception:
        logger.debug("non-critical operation failed", exc_info=True)
    return None


def _build_vision_content(text: str, images: list) -> list:
    """Build multimodal content block for vision-capable models.

    Returns a list suitable for OpenAI-compatible vision API:
    [{"type": "text", "text": ...}, {"type": "image_url", "image_url": {"url": ...}}, ...]
    """
    content = [{"type": "text", "text": text}]
    for img in images:
        if isinstance(img, str) and img.startswith("data:image"):
            content.append({"type": "image_url", "image_url": {"url": img}})
    return content


# ═══════════════════════════════════════════════════════════════════════════
# Tool Schema Builders (pure / agent.tools)
# ═══════════════════════════════════════════════════════════════════════════


# ── 渐进式上下文辅助函数 ──

# ═══ v20: 身份权重注入 ═══
# Nexus的身份不是SOUL.md文件,而是训练进identity_core的权重
# nexus_identity.lora (47KB, 10MB weights) 包含从对话中提取的身份语句+权重
# 每次回复前注入top 8条身份语句到系统上下文
_IDENTITY_CACHE = None

def _load_identity_context():
    global _IDENTITY_CACHE
    if _IDENTITY_CACHE is not None:
        return _IDENTITY_CACHE
    try:
        from pathlib import Path
        import json
        f = Path.home() / ".nexus" / "data" / "neural" / "identity_weights" / "nexus_identity.lora"
        if f.exists():
            data = json.loads(f.read_text("utf-8"))
            top = sorted(
                [(v[0], v[1]) for v in data.values() if isinstance(v, list) and len(v) >= 2],
                key=lambda x: -x[0]
            )[:8]
            _IDENTITY_CACHE = NL.join(f"- {text[:150]}" for _, text in top)
            return _IDENTITY_CACHE
    except Exception:
        pass
    _IDENTITY_CACHE = ""
    return ""

def _extract_soul_essence(system_prompt: str) -> str:
    """从完整系统提示词中提取核心身份（< 500字）"""
    # 只保留身份核心: 名字、创造者、信条、核心规则
    lines = system_prompt.split("\n")
    essence = []
    capture = False
    for line in lines:
        if any(kw in line for kw in ["名字", "创造者", "信条", "核心", "终极目标"]):
            capture = True
        if capture:
            essence.append(line)
            if len("\n".join(essence)) > 800:
                break
    if not essence:
        # Fallback: take first 500 chars
        return system_prompt[:500]
    return "\n".join(essence)

def _extract_user_facts(messages: list) -> str:
    """从对话中提取用户声明的事实（名字、关系、正在做什么）"""
    facts = {}
    for m in messages[-30:]:
        c = str(m.get("content", ""))
        if m["role"] != "user" or len(c) < 3:
            continue
        # Pattern: "我叫X" / "我是X" / "我的名字是X"
        for pat, key in [(r'我叫\s*(\S+)', '用户名字'), (r'我是\s*(\S+)', '用户身份'),
                          (r'CC老师', '关系'), (r'在[学教练].{0,10}(\S+)', '当前活动')]:
            match = re.search(pat, c)
            if match:
                val = match.group(1) if match.lastindex else match.group(0)
                facts[key] = val
    if not facts:
        return "对话中暂无明确的用户信息。"
    lines = []
    for k, v in facts.items():
        lines.append(f"- {k}: {v}")
    return "\n".join(lines)

def _build_conversation_summary(messages: list) -> str:
    """从最近20条消息中提取对话摘要"""
    topics = []
    for m in messages[-20:]:
        c = str(m.get("content", ""))[:100]
        if m["role"] == "user" and len(c) > 5:
            # Extract key topic words
            keywords = [w for w in c.split() if len(w) >= 2 and not w.startswith("[")]
            if keywords:
                topics.append(" ".join(keywords[:5]))
    if not topics:
        return "对话历史中暂无明确主题。"
    # Deduplicate and take last 5
    seen = set()
    unique = []
    for t in reversed(topics):
        if t not in seen:
            seen.add(t)
            unique.append(t)
        if len(unique) >= 5:
            break
    return "最近讨论: " + " | ".join(reversed(unique))


# v20: User profile — update on every message
def _update_user_profile(content: str):
    try:
        from nexus_agent.nexus_user_profile import get_user_profile
        up = get_user_profile()
        up.update_from_message(content)
    except Exception:
        pass

def build_tool_schemas(agent) -> list:
    """Build OpenAI-format tool schemas for native function calling.

    Returns list of {"type": "function", "function": {...}} objects.
    Returns empty list if tools registry is not available.
    """
    if not hasattr(agent, "tools") or not agent.tools:
        return []
    try:
        tool_names = agent.tools.list_tools()
    except Exception:
        return []

    schemas = []
    for name in sorted(tool_names):
        schema = build_single_tool_schema(name)
        if schema:
            schemas.append({"type": "function", "function": schema})
    logger.info(
        f"[NexusAgent] Built {len(schemas)} native tool schemas (from {len(tool_names)} tools)"
    )
    return schemas


def build_constrained_tool_schemas(agent, pre_analysis: dict) -> list:
    """渐进式工具披露 + 自我学习: 核心可见 + 已学工具自动提升 + 延迟按需搜索."""
    candidates = pre_analysis.get("tool_candidates", [])
    if not candidates:
        return build_tool_schemas(agent)

    schemas = []
    candidate_names = {c["name"] for c in candidates}

    # ── 自我学习注入: 从历史对话中学到的工具关联 ──
    user_content = pre_analysis.get("content", "")
    if user_content:
        try:
            from nexus_agent.tool_learning import get_learned_tools
            learned = get_learned_tools(user_content, min_weight=0.3, max_tools=5)
            for tool_name, weight in learned:
                if tool_name not in candidate_names:
                    s = build_single_tool_schema(tool_name)
                    if s:
                        s["description"] = f"[已学:{weight:.0%}] {s.get('description', '')}"
                        schemas.append({"type": "function", "function": s})
                        candidate_names.add(tool_name)
            if learned:
                logger.info(
                    f"[NexusAgent] 自我学习注入 %d 工具: %s",
                    len(learned),
                    ", ".join(f"{t}({w:.0%})" for t, w in learned),
                )
        except Exception:
            logger.debug("self-learning skipped", exc_info=True)

    # ── 意图匹配的工具 ──
    for c in candidates:
        name = c["name"]
        schema = build_single_tool_schema(name)
        if schema:
            relevance = c.get("relevance", 0.5)
            reason = c.get("reason", "")
            if reason:
                schema["description"] = f"[{relevance:.0%}] {reason}. {schema.get('description', '')}"
            schemas.append({"type": "function", "function": schema})

    # 始终附加 skill + ask_user
    if "skill" not in candidate_names and hasattr(agent, "skills") and agent.skills:
        s = build_single_tool_schema("skill")
        if s:
            schemas.append({"type": "function", "function": s})
            candidate_names.add("skill")
    if "ask_user" not in candidate_names:
        s = build_single_tool_schema("ask_user")
        if s:
            schemas.append({"type": "function", "function": s})

    from nexus_agent.tool_router import assemble_tool_schemas
    result = assemble_tool_schemas(schemas)
    logger.info(
        f"[NexusAgent] %d tools (intent=%s)",
        len(result), pre_analysis.get("intent_type", "?"),
    )
    return result

def build_single_tool_schema(name: str) -> dict:
    """Build JSON Schema for a single tool."""
    from nexus_agent.tool_descriptions import get_schema as _get

    schema = _get(name)
    desc = schema["description"] if schema else f"Execute the {name} tool."
    return {
        "name": name,
        "description": desc,
        "parameters": {
            "type": "object",
            "properties": {
                "params": {"type": "object", "description": f"Parameters for {name}"}
            },
            "required": ["params"],
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# Nexus Pre-Analysis — Elastic 4-Lane Capability-Aware Router
# ═══════════════════════════════════════════════════════════════════════════
#
# 架构: 4 条产线并行产出工具候选集 → 加权合并 → CapabilityTree 成熟度调整
#
#   Lane 1: NeuralRouter  — Transformer 预测路由类型 → 策略模板工具集
#   Lane 2: EvoKG         — 能力匹配 + 相似经验 → metadata.tools 工具集
#   Lane 3: Keyword       — 关键词子串匹配 (纯本地，永健康)
#   Lane 4: CapabilityTree — 对合并结果做成熟度调整 (L3+提权, L0-L1降权)
#
# 弹性保证: 每条产线独立 try-except+timeout, 任何一条挂不影响其他。
#           关键词线永远 HEALTHY, 保证零退化。

import time as _time

# ── 路由类型 → 工具策略模板 ──
# NeuralRouter 的 8 路由类型映射到工具候选集
ROUTE_STRATEGY_TEMPLATES: dict[str, list[tuple[str, float, str]]] = {
    "auto_rule": [
        ("read", 0.9, "规则执行-先读"),
        ("grep", 0.85, "规则执行-搜索"),
        ("glob", 0.8, "规则执行-匹配"),
        ("bash", 0.85, "规则执行-命令"),
        ("edit", 0.8, "规则执行-修改"),
        ("write", 0.75, "规则执行-写入"),
    ],
    "workflow": [
        ("read", 0.9, "工作流-读取"),
        ("grep", 0.85, "工作流-搜索"),
        ("glob", 0.8, "工作流-匹配"),
        ("bash", 0.9, "工作流-命令"),
        ("edit", 0.85, "工作流-修改"),
        ("write", 0.85, "工作流-写入"),
        ("task_create", 0.9, "工作流-任务追踪"),
        ("plan_create", 0.85, "工作流-制定计划"),
        ("code_scan", 0.7, "工作流-扫描"),
        ("web_search", 0.65, "工作流-搜索"),
    ],
    "command": [
        ("bash", 1.0, "命令执行"),
        ("run_python", 0.9, "Python执行"),
        ("read", 0.7, "命令-读取"),
        ("write", 0.6, "命令-写入"),
    ],
    "skill": [
        ("read", 0.85, "技能-读取"),
        ("write", 0.85, "技能-写入"),
        ("bash", 0.8, "技能-命令"),
        ("edit", 0.8, "技能-修改"),
        ("grep", 0.7, "技能-搜索"),
        ("code_generate", 0.75, "技能-生成"),
    ],
    "intent": [
        ("read", 0.9, "检索-读取"),
        ("grep", 0.85, "检索-搜索"),
        ("glob", 0.8, "检索-匹配"),
        ("list_directory", 0.75, "检索-目录"),
        ("web_search", 0.7, "检索-网络"),
        ("recall", 0.65, "检索-记忆"),
        ("system_info", 0.5, "检索-系统"),
        # 深度修复: "intent" 复合操作经常含 "读+改+写" 步骤,
        # 必须保留 edit/write 工具, 防止 LLM 拿到残废工具集后"假装完成"
        ("edit", 0.7, "检索-复合修改"),
        ("write", 0.65, "检索-复合写入"),
        ("bash", 0.6, "检索-复合命令"),
    ],
    "template": [
        ("write", 0.9, "模板-写入"),
        ("read", 0.85, "模板-读取"),
        ("edit", 0.8, "模板-修改"),
        ("bash", 0.7, "模板-命令"),
    ],
    "solidified": [
        ("recall", 0.9, "固化-召回"),
        ("read", 0.8, "固化-读取"),
        ("grep", 0.75, "固化-搜索"),
        ("glob", 0.7, "固化-匹配"),
    ],
    "llm_7agent": [
        ("read", 0.85, "全工具-读取"),
        ("grep", 0.8, "全工具-搜索"),
        ("glob", 0.75, "全工具-匹配"),
        ("list_directory", 0.7, "全工具-目录"),
        ("bash", 0.85, "全工具-命令"),
        ("edit", 0.8, "全工具-修改"),
        ("write", 0.75, "全工具-写入"),
        ("recall", 0.7, "全工具-记忆"),
        ("remember", 0.6, "全工具-保存"),
        ("web_search", 0.6, "全工具-网络"),
        ("code_scan", 0.6, "全工具-扫描"),
        ("system_info", 0.5, "全工具-系统"),
        ("task_create", 0.65, "全工具-任务"),
        ("plan_create", 0.6, "全工具-计划"),
        ("code_generate", 0.7, "全工具-生成"),
        ("code_fix", 0.65, "全工具-修复"),
    ],
}


# ── 产线健康状态机 ──
class LaneHealth:
    """追踪单条产线的健康状态。内存中运行，重启自动重置。"""

    def __init__(self, name: str, reset_after: float = 60.0):
        self.name = name
        self._consecutive_failures = 0
        self._total_calls = 0
        self._total_failures = 0
        self._last_failure_time: float = 0.0
        self._skipped_until: float = 0.0
        self._recent_results: list[bool] = []  # 最近 5 次结果
        self._reset_after = reset_after

    def record_success(self):
        self._consecutive_failures = 0
        self._total_calls += 1
        self._recent_results.append(True)
        if len(self._recent_results) > 5:
            self._recent_results.pop(0)

    def record_failure(self):
        self._consecutive_failures += 1
        self._total_calls += 1
        self._total_failures += 1
        self._last_failure_time = _time.monotonic()
        self._recent_results.append(False)
        if len(self._recent_results) > 5:
            self._recent_results.pop(0)
        # 连续 5 次失败 → 跳过 60s
        if self._consecutive_failures >= 5:
            self._skipped_until = _time.monotonic() + self._reset_after

    @property
    def status(self) -> str:
        if self._total_calls == 0:
            return "COLD"
        if self._skipped_until > _time.monotonic():
            return "SKIPPED"
        recent = self._recent_results[-3:] if self._recent_results else []
        if recent and not all(recent):
            return "DEGRADED"
        return "HEALTHY"

    @property
    def weight_multiplier(self) -> float:
        """返回此产线的权重系数。"""
        status_map = {"HEALTHY": 1.0, "DEGRADED": 0.5, "COLD": 0.0, "SKIPPED": 0.0}
        return status_map.get(self.status, 0.0)

    def should_run(self) -> bool:
        return self.status not in ("SKIPPED",)


# 全局产线健康追踪 (模块级单例)
_lane_health: dict[str, LaneHealth] = {
    "neural": LaneHealth("neural"),
    "evokg": LaneHealth("evokg"),
    "capability": LaneHealth("capability"),
    "keyword": LaneHealth("keyword"),
}


def _validate_tool_exists(agent, name: str) -> bool:
    """验证工具是否在注册表中。"""
    return bool(
        hasattr(agent, "tools") and agent.tools and name in agent.tools.list_tools()
    )


def _tools_from_template(agent, template: list[tuple[str, float, str]]) -> list[dict]:
    """从策略模板生成工具候选集，过滤不存在的工具。"""
    return [
        {"name": name, "relevance": rel, "reason": reason}
        for name, rel, reason in template
        if _validate_tool_exists(agent, name)
    ]


# ═════════════════════════════════════════════════════
# Lane 1: NeuralRouter — Transformer 路由预测
# ═════════════════════════════════════════════════════


async def _lane_neural_route(agent, content: str) -> dict:
    """NeuralRouter 产线: 预测路由类型 → 策略模板工具集。"""
    health = _lane_health["neural"]
    if not health.should_run():
        return {
            "candidates": [],
            "confidence": 0.0,
            "intent_type": "chat",
            "route_type": "skipped",
            "healthy": False,
            "source": "neural",
        }

    try:
        from nexus_agent.neural.router_nn import NeuralRouter

        router = NeuralRouter.get_instance()
        if not router.active:
            health.record_failure()
            return {
                "candidates": [],
                "confidence": 0.0,
                "intent_type": "chat",
                "route_type": "cold",
                "healthy": False,
                "source": "neural",
            }

        route_type, confidence, _all_probs = router.predict(content)

        if confidence < 0.3:
            health.record_success()
            return {
                "candidates": [],
                "confidence": confidence,
                "intent_type": "chat",
                "route_type": route_type,
                "healthy": True,
                "source": "neural",
                "skipped_reason": "low_confidence",
            }

        template = ROUTE_STRATEGY_TEMPLATES.get(
            route_type, ROUTE_STRATEGY_TEMPLATES["llm_7agent"]
        )
        candidates = _tools_from_template(agent, template)

        # 路由类型 → 传统 intent_type 映射 (向后兼容)
        _route_to_intent = {
            "command": "execute",
            "intent": "query",
            "skill": "create",
            "auto_rule": "modify",
            "workflow": "create",
            "template": "create",
            "solidified": "query",
            "llm_7agent": "chat",
        }
        intent_type = _route_to_intent.get(route_type, "chat")

        health.record_success()
        return {
            "candidates": candidates,
            "confidence": confidence,
            "intent_type": intent_type,
            "route_type": route_type,
            "healthy": True,
            "source": "neural",
        }
    except Exception:
        logger.debug("non-critical operation failed", exc_info=True)
        health.record_failure()
        return {
            "candidates": [],
            "confidence": 0.0,
            "intent_type": "chat",
            "route_type": "error",
            "healthy": False,
            "source": "neural",
        }


# ═════════════════════════════════════════════════════
# Lane 2: EvoKG — 能力匹配 + 相似经验
# ═════════════════════════════════════════════════════


async def _lane_evokg_match(agent, content: str) -> dict:
    """EvoKG 产线: 查询能力节点 → 提取 metadata.tools → 工具候选集。"""
    health = _lane_health["evokg"]
    if not health.should_run():
        return {
            "candidates": [],
            "confidence": 0.0,
            "intent_type": "chat",
            "healthy": False,
            "source": "evokg",
        }

    try:
        from nexus_agent.evokg import get_evokg

        kg = get_evokg()

        # 查找匹配的能力节点
        caps = kg.find_capabilities_for_task(content[:100])
        # 查找相似历史经验
        exps = kg.find_similar_experiences(content[:100])

        candidates = []
        seen_names: set[str] = set()

        # 从能力节点 metadata.tools 提取工具
        for cap in caps:
            tools = cap.metadata.get("tools", []) if cap.metadata else []
            for tool_name in tools:
                if tool_name not in seen_names and _validate_tool_exists(
                    agent, tool_name
                ):
                    seen_names.add(tool_name)
                    candidates.append(
                        {
                            "name": tool_name,
                            "relevance": min(0.95, 0.5 + cap.confidence * 0.45),
                            "reason": f"EvoKG能力: {cap.content[:40]}",
                        }
                    )

        # 从经验节点 metadata.tools 提取工具
        for exp in exps:
            tools = exp.metadata.get("tools", []) if exp.metadata else []
            for tool_name in tools:
                if tool_name not in seen_names and _validate_tool_exists(
                    agent, tool_name
                ):
                    seen_names.add(tool_name)
                    candidates.append(
                        {
                            "name": tool_name,
                            "relevance": min(0.9, 0.4 + exp.confidence * 0.5),
                            "reason": f"EvoKG经验: {exp.content[:40]}",
                        }
                    )

        # 置信度 = 匹配到的能力节点平均置信度
        avg_conf = sum(c.confidence for c in caps) / max(len(caps), 1) if caps else 0.0
        # 有匹配 → 高置信度; 无匹配 → 冷启动，低置信度
        lane_confidence = 0.7 + avg_conf * 0.25 if candidates else 0.0

        health.record_success()
        return {
            "candidates": candidates,
            "confidence": lane_confidence,
            "intent_type": "chat",
            "healthy": True,
            "source": "evokg",
            "caps_matched": len(caps),
            "exps_matched": len(exps),
        }
    except Exception:
        logger.debug("non-critical operation failed", exc_info=True)
        health.record_failure()
        return {
            "candidates": [],
            "confidence": 0.0,
            "intent_type": "chat",
            "healthy": False,
            "source": "evokg",
        }


# ═════════════════════════════════════════════════════
# Lane 3: Keyword Baseline — 纯本地计算，永不故障
# ═════════════════════════════════════════════════════


async def _lane_keyword_baseline(agent, content: str) -> dict:
    """关键词产线: 纯本地子串匹配。永远 HEALTHY，作为系统底线。"""
    health = _lane_health["keyword"]
    content_lower = content.lower().strip()
    try:
        from nexus_agent.tool_learning import get_learned_tools
        learned=get_learned_tools(content,min_weight=0.3)
        if learned:
            for t,w in learned[:3]:
                if hasattr(agent,"tools")and t in agent.tools.list_tools():
                    pass
    except:pass

    # 关键词定义
    heavy_cn = [
        "写",
        "创建",
        "新建",
        "生成",
        "改",
        "修改",
        "修复",
        "更新",
        "删",
        "实现",
        "开发",
        "加",
        "换成",
        "改成",
        "切换",
        "调到",
        "迁移",
        "帮",
        "帮我",
        "能不能",
        "可以",
        "可否",
        "能否",
        "配置",
        "设置",
        "设",
    ]
    heavy_en = [
        "write",
        "create",
        "make",
        "build",
        "edit",
        "modify",
        "fix",
        "change",
        "update",
        "delete",
        "remove",
        "implement",
        "develop",
        "add",
        "switch",
        "replace",
        "migrate",
        "configure",
        "setup",
        "set",
        "help",
        "append",  # 修复: 之前 "Append to file" 走 chat intent
        "insert",  # 修复: 插入/Insert 关键词
        "prepend",  # 修复: 头部追加
        "overwrite",  # 修复: 覆盖写入
    ]
    exec_cn = ["运行", "执行", "启动", "安装", "部署", "测试", "追加", "插入"]
    exec_en = [
        "run",
        "execute",
        "start",
        "install",
        "deploy",
        "test",
        "append",  # 修复: append 应该被识别为操作
        "insert",  # 修复: insert 同样
    ]
    query_cn = [
        "显示",
        "查看",
        "列出",
        "搜索",
        "查",
        "找",
        "是什么",
        "怎么",
        "如何",
        "读取",
        "读",
    ]
    query_en = [
        "show",
        "list",
        "search",
        "find",
        "why",
        "what",
        "how",
        "read",
        "get",
        "fetch",
    ]

    def _count_cn(kws, txt):
        # 数 txt 中各 kw 的实际出现次数 (不是 kws 里有几个命中)
        # 修复: 之前 sum(1 for kw in kws if kw in txt) 把 "create 出现 2 次" 算 1
        return sum(txt.count(kw) for kw in kws if kw)

    def _count_en(kws, txt):
        # 同上: 数 txt 中各 kw 的实际出现次数
        return sum(
            len(re.findall(r"\b" + re.escape(kw) + r"\b", txt)) for kw in kws if kw
        )

    heavy_count = _count_cn(heavy_cn, content_lower) + _count_en(
        heavy_en, content_lower
    )
    exec_count = _count_cn(exec_cn, content_lower) + _count_en(exec_en, content_lower)
    query_count = _count_cn(query_cn, content_lower) + _count_en(
        query_en, content_lower
    )

    # 意图判定
    # 设计原则: 减少对 LLM 的依赖 → 操作类意图 (modify/create/execute) 必须
    # 优先于纯查询. 之前 heavy==query 平局时被误判为 query, 导致"读+改+写"
    # 复合操作被错误降级为查询, LLM 拿到残废工具集后"假装完成".
    # 修复: heavy >= query 时优先判为 modify/create (而不是 query)
    intent_type = "chat"
    if heavy_count >= exec_count and heavy_count >= query_count and heavy_count > 0:
        intent_type = (
            "modify"
            if any(
                s in content_lower
                for s in [
                    "改",
                    "修改",
                    "修复",
                    "fix",
                    "edit",
                    "更新",
                    "change",
                    "update",
                    "modify",
                    "换成",
                    "切换",
                    "迁移",
                    "配置",
                    "设置",
                    "replace",
                    "switch",
                    "migrate",
                    "configure",
                    "append",  # 修复: "append to file" 应该是 modify
                    "insert",  # 修复: insert 同样
                    "prepend",  # 修复: prepend 同样
                    "追加",  # 修复: 中文追加
                    "插入",  # 修复: 中文插入
                ]
            )
            else "create"
        )
    elif exec_count > heavy_count and exec_count >= query_count:
        intent_type = "execute"
    elif query_count > heavy_count:
        intent_type = "query"

    # 复杂度
    complexity = 0
    clen = len(content)
    if clen > 500:
        complexity += 3
    elif clen > 100:
        complexity += 2
    elif clen > 20:
        complexity += 1
    if heavy_count >= 3:
        complexity += 3
    elif heavy_count >= 1:
        complexity += 2
    if exec_count >= 2:
        complexity += 2
    domain_words = {
        "数据",
        "database",
        "sql",
        "界面",
        "ui",
        "安全",
        "auth",
        "部署",
        "deploy",
        "模型",
        "model",
        "测试",
        "test",
    }
    if len(set(content_lower.split()) & domain_words) >= 2:
        complexity += 2
    if content.strip().endswith(("?", "？")):
        complexity = max(0, complexity - 2)
    complexity = min(10, max(0, complexity))

    # 工具模板 — 保留原有硬编码白名单作为底线
    intent_tool_map = {
        "query": [
            ("read", 0.9, "查询-读取"),
            ("grep", 0.85, "查询-搜索"),
            ("glob", 0.8, "查询-匹配"),
            ("list_directory", 0.75, "查询-目录"),
            ("web_search", 0.7, "查询-网络"),
            ("web_fetch", 0.65, "查询-网页"),
            ("recall", 0.6, "查询-记忆"),
            ("system_info", 0.5, "查询-系统"),
            ("code_status", 0.5, "查询-状态"),
        ],
        "modify": [
            ("read", 1.0, "修改-先读"),
            ("edit", 0.95, "修改-精确"),
            ("write", 0.9, "修改-写入"),
            ("bash", 0.8, "修改-命令"),
            ("grep", 0.7, "修改-搜索"),
            ("glob", 0.65, "修改-匹配"),
            ("list_directory", 0.6, "修改-目录"),
            ("code_fix", 0.7, "修改-修复"),
            ("code_scan", 0.6, "修改-扫描"),
        ],
        "create": [
            ("write", 1.0, "创建-写入"),
            ("bash", 0.8, "创建-命令"),
            ("read", 0.7, "创建-参考"),
            ("grep", 0.6, "创建-搜索"),
            ("glob", 0.6, "创建-匹配"),
            ("code_generate", 0.85, "创建-生成"),
            ("task_create", 0.5, "创建-任务"),
            ("plan_create", 0.5, "创建-计划"),
        ],
        "execute": [
            ("bash", 1.0, "执行-命令"),
            ("run_python", 0.9, "执行-Python"),
            ("read", 0.7, "执行-输入"),
            ("write", 0.6, "执行-结果"),
            ("pip_install", 0.5, "执行-安装"),
            ("npm_install", 0.5, "执行-包"),
        ],
        "chat": [
            ("read", 0.85, "对话-读取"),
            ("grep", 0.8, "对话-搜索"),
            ("glob", 0.75, "对话-匹配"),
            ("list_directory", 0.7, "对话-目录"),
            ("bash", 0.85, "对话-命令"),
            ("edit", 0.8, "对话-修改"),
            ("write", 0.75, "对话-写入"),
            ("recall", 0.7, "对话-记忆"),
            ("remember", 0.6, "对话-保存"),
            ("web_search", 0.6, "对话-网络"),
            ("code_scan", 0.6, "对话-扫描"),
            ("system_info", 0.5, "对话-系统"),
            ("chat_with_video", 0.8, "对话-视频理解"),  # v20.1
            ("chat_with_image", 0.8, "对话-图片理解"),  # v20.1
            ("chat_with_audio", 0.75, "对话-语音转录"),  # v20.1
            # v8.0.1: 语音工具 — 修复 "飞书语音完全不工作" 的根因
            # 之前 send_feishu_voice/text_to_speech 注册了但不出现在 chat 候选集
            ("send_feishu_voice", 0.7, "对话-飞书语音"),
            ("text_to_speech", 0.65, "对话-语音朗读"),
            ("list_voices", 0.5, "对话-语音列表"),
        ],
    }

    # ── 自省检测: 用户问的是 Nexus 自己的事 → 路由到文件探索 ──
    self_ref_patterns = [
        r"你(今天|最近|这几天|昨天|本周|这个月).{0,6}(干了?什么|做了什么|怎么样|在做什么|忙了什么)",
        r"你(的|自己).{0,4}(状态|情况|进展|工作|日记|日志|记录)",
        r"(今天|最近).{0,4}你.{0,4}(干了?|做了?|忙了?).{0,2}(什么|啥|哪些)",
        r"(汇报|总结|说说|讲).{0,4}(你|自己).{0,4}(今天|最近|工作|进度)",
    ]
    is_self_ref = any(re.search(p, content_lower) for p in self_ref_patterns)
    
    # v20.1: 视频文件检测 — 用户发了视频 → 提升 chat_with_video 权重
    has_video = bool(re.search(r'\.(mp4|avi|mkv|mov|flv|webm)', content_lower, re.IGNORECASE))
    has_image = bool(re.search(r'\.(jpg|jpeg|png|gif|webp|bmp)', content_lower, re.IGNORECASE))
    has_audio = bool(re.search(r"\.(ogg|mp3|wav|m4a|aac|flac|opus)\b", content_lower, re.IGNORECASE))
    has_video_url = bool(re.search(r"(bilibili\.com|youtube\.com|youtu\.be|b23\.tv)", content_lower, re.IGNORECASE))
    if (has_video or has_image or has_audio or has_video_url) and intent_type == "chat":
        adjusted = []
        for name, rel, reason in base_candidates:
            if has_video and name == "chat_with_video":
                adjusted.append((name, min(1.0, rel * 1.5), reason + "-视频优先"))
            elif has_image and name == "chat_with_image":
                adjusted.append((name, min(1.0, rel * 1.5), reason + "-图片优先"))
            elif has_audio and name == "chat_with_audio":
                adjusted.append((name, min(1.0, rel * 1.5), reason + "-音频优先"))
            elif name in ("send_feishu_voice", "text_to_speech"):
                adjusted.append((name, min(1.0, rel * 1.3), reason + "-多媒体后语音"))
            else:
                adjusted.append((name, rel, reason))
        base_candidates = adjusted

    base_candidates = intent_tool_map.get(intent_type, intent_tool_map["chat"])
    if is_self_ref:
        # 自省问题: 降低 recall/remember 权重，提升 read/glob/grep
        adjusted = []
        for name, rel, reason in base_candidates:
            if name in ("recall", "remember", "forget", "web_search", "web_fetch"):
                adjusted.append((name, rel * 0.3, reason + "-自省降权"))
            elif name in ("read", "glob", "grep", "list_directory", "bash"):
                adjusted.append((name, min(1.0, rel * 1.3), reason + "-自省优先"))
            else:
                adjusted.append((name, rel, reason))
        # 确保 read 权重最高
        adjusted.sort(key=lambda x: -x[1])
        base_candidates = adjusted
        decision_guidance = (
            "[Nexus自主分析] ⚠️ 这是关于 Nexus 自身的问题（自省类）。"
            "请使用文件探索工具（read/glob/grep/bash）查看日记、日志和配置文件来回答。"
            "不要使用记忆召回（recall）——记忆系统不存储每日活动摘要。"
            "日记文件通常以 NEXUS_DIARY_ 开头，位于 Home 目录下。"
        )
    else:
        decision_guidance = ""

    candidates = [
        {"name": name, "relevance": rel, "reason": reason}
        for name, rel, reason in base_candidates
        if _validate_tool_exists(agent, name)
    ]

    health.record_success()
    return {
        "candidates": candidates,
        "confidence": 0.6,  # 关键词线基础置信度 0.6
        "intent_type": intent_type,
        "complexity": complexity,
        "healthy": True,
        "source": "keyword",
        "decision_guidance": decision_guidance,
    }


# ═════════════════════════════════════════════════════
# Lane 4: CapabilityTree — 成熟度调整
# ═════════════════════════════════════════════════════

# 工具名 → CapabilityTree category 映射
TOOL_CAPABILITY_MAP: dict[str, str] = {
    "write": "code_generation",
    "code_generate": "code_generation",
    "edit": "code_modification",
    "code_fix": "code_modification",
    "read": "filesystem",
    "glob": "filesystem",
    "list_directory": "filesystem",
    "grep": "search",
    "web_search": "search",
    "web_fetch": "search",
    "bash": "workflow",
    "run_python": "workflow",
    "task_create": "workflow",
    "plan_create": "workflow",
    "git_commit": "workflow",
    "git_push": "workflow",
    "recall": "rag",
    "remember": "rag",
    "pip_install": "tool_creation",
    "npm_install": "tool_creation",
    "system_info": "filesystem",
    "code_scan": "search",
    "code_status": "search",
}


async def _lane_capability_adjust(candidates: list[dict]) -> dict:
    """CapabilityTree 产线: 对合并后的候选集做成熟度调整。"""
    health = _lane_health["capability"]
    if not candidates or not health.should_run():
        return {
            "adjusted": candidates,
            "healthy": True,
            "source": "capability",
            "adjustments": [],
        }

    try:
        from nexus_agent.capability_tree import get_capability_tree

        tree = get_capability_tree()
        adjustments = []

        for c in candidates:
            tool_name = c.get("name", "")
            category = TOOL_CAPABILITY_MAP.get(tool_name)
            if not category:
                continue

            try:
                maturity = tree.get_maturity(category)
                level = maturity.value if hasattr(maturity, "value") else maturity

                if level >= 3:  # L3 AUTONOMOUS +
                    c["relevance"] = min(1.0, c["relevance"] * 1.2)
                    adjustments.append(
                        f"{tool_name}: L{level} boost → {c['relevance']:.2f}"
                    )
                elif level <= 1:  # L0 INFANT / L1 APPRENTICE
                    c["relevance"] = max(0.1, c["relevance"] * 0.7)
                    adjustments.append(
                        f"{tool_name}: L{level} caution → {c['relevance']:.2f}"
                    )
            except Exception:
                logger.debug("non-critical operation failed", exc_info=True)
                continue

        health.record_success()
        return {
            "adjusted": candidates,
            "healthy": True,
            "source": "capability",
            "adjustments": adjustments,
        }
    except Exception:
        logger.debug("non-critical operation failed", exc_info=True)
        health.record_failure()
        return {
            "adjusted": candidates,
            "healthy": False,
            "source": "capability",
            "adjustments": [],
        }


# ═════════════════════════════════════════════════════
# 加权合并引擎
# ═════════════════════════════════════════════════════


def _weighted_merge(lane_results: list[dict]) -> list[dict]:
    """加权合并多条产线的候选工具。

    每条产线: {"candidates": [...], "confidence": float, "healthy": bool, "source": str}
    healthy 产线的候选工具按 confidence 加权累加 relevance。
    所有产线都 unhealthy → 返回空列表（由调用方降级到全量 schema）。
    """
    healthy_lanes = [L for L in lane_results if L.get("healthy")]
    if not healthy_lanes:
        return []

    total_weight = sum(L.get("confidence", 0.0) for L in healthy_lanes)
    if total_weight <= 0:
        total_weight = 1.0

    merged: dict[str, dict] = {}  # tool_name → {name, relevance, reason, sources}

    for lane in healthy_lanes:
        lane_conf = lane.get("confidence", 0.0)
        lane_weight = lane_conf / total_weight
        source = lane.get("source", "?")

        for c in lane.get("candidates", []):
            # 防御性: 跳过非 dict 或缺 'name' 的元素
            if not isinstance(c, dict) or not c.get("name"):
                continue
            name = c["name"]
            relevance = c.get("relevance", 0.0)
            weighted_rel = relevance * lane_weight
            if name in merged:
                merged[name]["relevance"] += weighted_rel
                merged[name]["relevance"] = min(1.0, merged[name]["relevance"])
                if source not in merged[name]["sources"]:
                    merged[name]["sources"].append(source)
                    merged[name]["reason"] += f" + {source}"
            else:
                merged[name] = {
                    "name": name,
                    "relevance": min(1.0, weighted_rel),
                    "reason": f"{c.get('reason', '')} [{source}]",
                    "sources": [source],
                }

    result = sorted(merged.values(), key=lambda x: x["relevance"], reverse=True)
    return result


def _get_intent_efficiency_hint(intent_type: str, complexity: int) -> str:
    """按意图类型返回 1 行动作指引，补充通用 Efficiency First 规则。"""
    hints = {
        "modify": (
            "[Efficiency] 修改任务: 先 Read 目标文件再 Edit；改完后 grep 所有调用方确保同步；"
            "有测试就跑。不要扫一眼就改。"
        ),
        "create": (
            "[Efficiency] 创建任务: 先确认目标目录和现有模式；Write/Edit 后检查 import 链；"
            "新文件要能被入口引用到。"
        ),
        "execute": (
            "[Efficiency] 执行任务: 先规划命令链再执行；确认前置条件（端口、依赖、权限）；"
            "一个 Bash 跑完的不拆成两个。"
        ),
        "query": (
            "[Efficiency] 查询任务: 并行 grep/glob/read — 能一次发出的不要分两次；"
            "结果直接给结论，不逐条复述。"
        ),
        "chat": ("[Efficiency] 对话任务: 简洁直接，不铺陈背景；有问才答，不问不展开。"),
    }
    return hints.get(intent_type, "")


async def _self_verify_async(tool_name: str, params: dict, result: str) -> None:
    """Fire-and-forget 自验证，不阻塞工具结果返回。"""
    try:
        from nexus_agent.self_verification import get_self_verifier

        vresult = await get_self_verifier().verify(
            tool_name=tool_name,
            params=params,
            result=result,
        )
        logger.debug(
            "[SelfVerify] %s: %s (%d checks, %.0fms)",
            tool_name,
            "PASS" if vresult.passed else "FAIL",
            len(vresult.checks),
            vresult.duration_ms,
        )
    except Exception:
        logger.debug("non-critical operation failed", exc_info=True)


# ═════════════════════════════════════════════════════
# 主入口: nexus_pre_analyze
# ═════════════════════════════════════════════════════


async def nexus_pre_analyze(agent, content: str) -> dict:
    """Nexus 弹性能力感知路由 — 4 线并行 + 加权合并。

    Lane 1 (NeuralRouter): Transformer 预测路由类型 → 策略模板
    Lane 2 (EvoKG):         能力匹配 + 相似经验 → metadata.tools
    Lane 3 (Keyword):       纯本地子串匹配，永远 HEALTHY（系统底线）
    Lane 4 (CapabilityTree): 对合并结果做 CMM 成熟度调整

    弹性保证: 每条产线独立 try-except + 超时保护，任何一条挂不阻断路由。
              关键词线永远可用，保证零退化。

    Returns:
        dict with intent_type, complexity, tool_candidates, skill_candidates,
             decision_guidance, passthrough, route_metadata
    """
    # ── 3 条候选产线并行执行 ──
    neural_task = _lane_neural_route(agent, content)
    evokg_task = _lane_evokg_match(agent, content)
    keyword_task = _lane_keyword_baseline(agent, content)

    neural_result, evokg_result, keyword_result = await asyncio.gather(
        neural_task,
        evokg_task,
        keyword_task,
    )

    # ── 加权合并 ──
    merged = _weighted_merge([neural_result, evokg_result, keyword_result])

    # ── CapabilityTree 成熟度调整 ──
    if merged:
        cap_result = await _lane_capability_adjust(merged)
        final_candidates = cap_result.get("adjusted", merged)
        cap_adjustments = cap_result.get("adjustments", [])
    else:
        final_candidates = []
        cap_adjustments = []

    # ── 降级保护: 合并后候选 < 3 → 回退到关键词线独立结果 ──
    if len(final_candidates) < 3:
        final_candidates = keyword_result.get("candidates", [])
        logger.info(
            "[ElasticRouter] 合并候选不足(%d)，回退到关键词基线(%d)",
            len(merged),
            len(final_candidates),
        )

    # ── 意图类型: 优先 NeuralRouter, 其次关键词 ──
    # 关键词基线有明确操作意图时, neural 需更高置信度才能覆盖
    # (NeuralRouter "intent"→"query" 映射会误杀中文修改/创建类指令)
    # 关键词基线无操作信号(chat)时, neural 也需中等置信度才能改为非 chat
    intent_type = keyword_result.get("intent_type", "chat")
    if neural_result.get("healthy") and neural_result.get("confidence", 0) >= 0.3:
        neural_intent = neural_result.get("intent_type", intent_type)
        # 设计原则: 减少对 LLM 的依赖 → 关键词检测到明确操作信号时,
        # NeuralRouter 不可覆盖 (即使 conf>=0.6), 防止复合操作被错误降级
        # 为 query 后 LLM 看到残废工具集而"假装完成"
        if (
            intent_type in ("modify", "create", "execute")
            and neural_intent != intent_type
        ):
            # 关键词检测到明确操作信号, NeuralRouter 想降级为 query/chat → 拒绝
            # 只在 NeuralRouter conf 极高 (>=0.85) 且意图想"提升"为更具体操作时才接受
            if (
                neural_result.get("confidence", 0) >= 0.85
                and neural_intent in ("modify", "create", "execute")
            ):
                intent_type = neural_intent
            else:
                logger.debug(
                    f"[ElasticRouter] NeuralRouter 试图把 {intent_type} 降级为 "
                    f"{neural_intent} (conf={neural_result.get('confidence', 0):.2f}) → 拒绝, "
                    f"保留 keyword 判定 (减少 LLM 误判)"
                )
        elif intent_type == "chat" and neural_intent != "chat":
            if neural_result.get("confidence", 0) >= 0.55:
                intent_type = neural_intent
        else:
            intent_type = neural_intent

    # ── Shadow mode: NeuralRouter vs Keyword 基线对比 ──
    if neural_result.get("healthy"):
        try:
            nn_route = neural_result.get("route_type", "unknown")
            kw_intent = keyword_result.get("intent_type", "chat")
            nn_intent = neural_result.get("intent_type", "chat")
            nn_agrees = nn_intent == kw_intent
            nn_conf = neural_result.get("confidence", 0.0)
            from nexus_agent.neural.training_loop import NeuralTrainingLoop

            tl = NeuralTrainingLoop.get_instance()
            tl.record_shadow_decision("router", nn_agrees)
            try:
                from nexus_agent.neural.global_training_cortex import (
                    GlobalTrainingCortex,
                )

                GlobalTrainingCortex.get_instance().record_nn_decision(
                    "router", nn_agrees, float(nn_conf)
                )
            except Exception:
                logger.debug("non-critical operation failed", exc_info=True)
            if tl.should_activate("router"):
                from nexus_agent.neural.router_nn import NeuralRouter

                NeuralRouter.get_instance().active = True
                logger.info(
                    "[ElasticRouter] NN Router graduated to active via shadow mode"
                )
        except Exception:
            logger.debug("[ElasticRouter] Shadow recording skipped", exc_info=True)

    # ── 复杂度: 取关键词线的评估 ──
    complexity = keyword_result.get("complexity", 0)

    # ── 技能候选匹配 ──
    skill_candidates = []
    try:
        from nexus_agent.skills import get_skill_manager

        sm = get_skill_manager()
        content_lower = content.lower()
        for skill_name in sm.list_skills():
            skill = sm.get_skill(skill_name)
            if skill and skill.trigger:
                for trigger in skill.trigger:
                    if len(trigger) >= 2 and trigger.lower() in content_lower:
                        skill_candidates.append(skill_name)
                        break
        skill_candidates = list(dict.fromkeys(skill_candidates))[:3]
    except Exception:
        logger.debug("non-critical operation failed", exc_info=True)

    # ── 决策指导 ──
    route_type = neural_result.get("route_type", "keyword")
    lane_status = {
        src: _lane_health[src].status for src in ["neural", "evokg", "capability"]
    }

    guidance_parts = [
        f"[Nexus弹性路由] 路由类型: {route_type}, 意图: {intent_type}, 复杂度: {complexity}/10",
        f"[Nexus弹性路由] 产线状态: neural={lane_status['neural']}, "
        f"evokg={lane_status['evokg']}, capability={lane_status['capability']}",
        f"[Nexus弹性路由] 候选工具({len(final_candidates)}): "
        f"{', '.join(c['name'] for c in final_candidates[:10])}",
    ]
    if skill_candidates:
        # 防御性: 过滤非 str 元素 (历史上有 YAML 把 1_1 解析为 int 11 的问题)
        safe_skill_candidates = [s for s in skill_candidates if isinstance(s, str)]
        if safe_skill_candidates:
            guidance_parts.append(
                f"[Nexus弹性路由] 推荐技能: {', '.join(safe_skill_candidates)}"
            )
    if cap_adjustments:
        guidance_parts.append(
            f"[Nexus弹性路由] 成熟度调整: {'; '.join(cap_adjustments[:5])}"
        )

    # ── 关键词基线自省/特殊指引 (从 lane 透传) ──
    kw_guidance = keyword_result.get("decision_guidance", "")
    if kw_guidance:
        guidance_parts.append(kw_guidance)

    # ── 意图类型效率指引 ──
    efficiency_hint = _get_intent_efficiency_hint(intent_type, complexity)
    if efficiency_hint:
        guidance_parts.append(efficiency_hint)

    # ── v9 反虚构（Anti-Confabulation）路由逻辑 ──
    # 根因：之前的 passthrough 逻辑在 query/chat+低复杂度时剥离全部工具，
    # LLM 被迫凭训练数据作答 → 对本地代码库问题产出虚构答案。
    #
    # v9 原则（根本性修正）：
    #   1. 任何涉及本地代码库/文件系统的查询 → 永不 passthrough
    #   2. 任何涉及计数/测量/比较的查询（无论范围）→ 永不 passthrough（需要实际数据）
    #   3. 仅真正的通用概念性对话 → passthrough（如"什么是装饰器"）
    #   4. 破坏性操作词 → 永不 passthrough
    content_lower = content.lower().strip()

    # ── 破坏性操作词（修改/删除/执行/创建等）→ 必须走工具路径 ──
    _destructive_keywords = [
        "改", "修改", "edit", "modify", "fix", "修复",
        "写", "write", "create", "创建", "实现", "implement",
        "运行", "run", "执行", "execute",
        "删", "删除", "delete", "remove",
        "安装", "install", "部署", "deploy", "构建", "build",
    ]
    _has_destructive = any(s in content_lower for s in _destructive_keywords)

    # ── 本地范围关键词（提到本地项目/文件/代码 → 训练数据不可信）──
    _local_scope_keywords = [
        # 明确的本地路径/目录引用
        "nexus_agent", ".nexus", "nexus_gateway",
        "这个目录", "当前项目", "这个文件", "这个项目",
        "我的代码", "我的项目", "这个代码库",
        "代码库", "仓库",
        "directory", "folder", "repo", "repository", "codebase",
        # v9.1: 英文日常指代（"this project", "my code" 等）
        "this project", "this directory", "this file", "this repo",
        "this codebase", "this code",
        "my project", "my code", "my codebase", "my repo",
        "our project", "our code", "our codebase", "our repo",
        "local project", "local code", "local repo",
        "本地", "项目中", "项目里",
        "项目", "工程",  # Chinese standalone — safe false positive (gives tools unnecessarily)
        # 本地实体 — 当问题涉及具体文件/代码时
        ".py", ".js", ".ts", ".json", ".md", ".yaml", ".yml",
        # 本地工具命令 — 暗示需要本地操作
        "git", "grep", "find", "wc ", "bash",
        # v9.2: 显式文件路径引用 — 任何读/写/查看具体文件都应走工具
        "/tmp/", "/var/", "/etc/", "/home/", "/usr/", "/opt/",
        "c:\\", "d:\\",  # Windows 绝对路径
        "文件:", "文件路径", "路径:", "file_path",
    ]
    _has_local_scope = any(kw in content_lower for kw in _local_scope_keywords)

    # v9.2: 正则检测文件路径引用（如 /path/to/file.txt, C:\dir\file.py）
    # 捕获纯关键词遗漏的路径引用，强制 requires_local_tools
    _path_pattern = re.compile(
        r'(?:^|\s)(?:/(?:\w+/)+[\w.-]+)|'       # Unix 绝对路径: /a/b/file.txt
        r'(?:[A-Za-z]:\\(?:\w+\\)+[\w.-]+)|'    # Windows 绝对路径: C:\a\b\file.txt
        r'(?:\.\.?/(?:\w+/)+[\w.-]+)|'           # 相对路径: ./dir/file.txt
        r'(?:\.\.\\(?:\w+\\)+[\w.-]+)'           # Windows 相对路径: ..\dir\file.txt
    )
    _has_path_reference = bool(_path_pattern.search(content))
    _has_local_scope = _has_local_scope or _has_path_reference

    # ── 测量/计数/比较关键词（任何带数字答案的问题 → 训练数据不可信）──
    _measurement_keywords = [
        "多少", "几个", "几条", "几行", "多少个", "多少次",
        "total", "count", "how many", "number of",
        "最大", "最小", "最长", "最短", "最多", "最少",
        "largest", "smallest", "longest", "shortest", "most", "least",
        "top", "biggest", "排名", "排行",
        "行数", "lines", "loc", "多少行", "代码量",
        "多少 MB", "多少 KB", "文件大小", "size",
        "占比", "比例", "percentage", "ratio",
        "哪个", "哪些", "which", "哪一",
        "最近", "最新", "最早", "最后",
        "recent", "latest", "earliest", "last modified",
    ]
    _has_measurement = any(kw in content_lower for kw in _measurement_keywords)

    # ── 纯概念性对话关键词（这些是真正可以 passthrough 的）──
    _conceptual_keywords = [
        "什么是", "what is", "解释", "explain", "概念", "concept",
        "定义", "define", "原理", "principle", "区别", "difference",
        "你觉得", "你怎么看", "what do you think", "建议", "suggest",
        "为什么", "why", "how does", "怎么做到",
    ]
    _is_conceptual = any(kw in content_lower for kw in _conceptual_keywords)

    # ── v9 passthrough 决策（原则：宁可给工具也不剥夺工具 → 默认不 passthrough）──
    # passthrough 仅当：query/chat 意图 + 低复杂度 + 纯概念性 + 无破坏性 + 无本地范围 + 无测量需求
    passthrough = (
        intent_type in ("query", "chat")
        and complexity <= 3
        and not _has_destructive
        and not _has_local_scope      # ← v9: 任何本地范围引用 → 不 passthrough
        and not _has_measurement      # ← v9: 任何测量/计数问题 → 不 passthrough
        and _is_conceptual            # ← v9: 仅纯概念对话可 passthrough
    )

    requires_local_tools = _has_local_scope or _has_measurement

    # 本地/测量查询 → 强制走工具路径 + 注入明确引导
    if requires_local_tools:
        passthrough = False
        complexity = max(complexity, 5)
        if _has_local_scope:
            guidance_parts.append(
                "[反虚构门] 此查询涉及本地代码库/文件系统。训练数据中的信息与本地文件无关——"
                "请使用 grep/bash/wc/read 等工具获取真实数据后再回答。"
                "不要凭记忆编造任何关于本地文件的具体内容、数量、或属性。"
            )
        if _has_measurement:
            guidance_parts.append(
                "[反虚构门] 此查询需要具体数值/排名/比较。这类答案必须来自实际测量——"
                "请使用工具获取数据后再计算/排序/比较。不要凭训练数据编造数字。"
            )

    return {
        "intent_type": intent_type,
        "complexity": complexity,
        "tool_candidates": final_candidates,
        "skill_candidates": skill_candidates,
        "decision_guidance": "\n".join(guidance_parts),
        "passthrough": passthrough,
        "requires_local_tools": requires_local_tools,  # v8 本地知识验证门标志
        # 新增: 路由元数据 (供诊断/调试)
        "route_metadata": {
            "route_type": route_type,
            "lane_status": lane_status,
            "neural_confidence": neural_result.get("confidence", 0),
            "evokg_matches": evokg_result.get("caps_matched", 0),
            "sources_contributing": list(
                set(s for c in final_candidates for s in c.get("sources", []))
            ),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# Adaptive Tool Executor — 弹性并发控制
# ═══════════════════════════════════════════════════════════════════════════


class AdaptiveToolExecutor:
    """自适应工具执行器 — 根据负载动态调整并发数。

    弹性设计:
    - 默认并发上限 5，负载上升时扩展到 8，空闲时收缩到 3
    - 每个工具有 60s 超时保护
    - CPU 密集型工具(bash/run_python)消耗 2 个槽位，I/O 工具消耗 1 个
    - 信号量固定在 _max (8)，_current_max 作为软限制通过 _active_count 控制。
      这样 _adapt() 调整软限制时不会替换信号量对象，避免协程孤立。
    """

    def __init__(self, min_slots: int = 3, max_slots: int = 8, default_slots: int = 5):
        # v9.8 修复 (2026-06-07): asyncio.Semaphore → threading.Semaphore，
        # 跨 event loop 安全（避免 "bound to a different event loop" RuntimeError）
        import threading as _threading
        self._sem_impl = _threading.Semaphore(max_slots)  # 物理槽位, 永不替换
        self._min = min_slots
        self._max = max_slots
        self._current_max = default_slots  # 软限制
        self._active_count = 0
        self._pending_history: list[int] = []
        self._total_executed = 0
        self._total_timeouts = 0
        self._total_rejected = 0

    @property
    def current_concurrency(self) -> int:
        return self._current_max

    async def execute(self, tool_name: str, params: dict, executor_fn) -> str:
        slots_needed = (
            2
            if tool_name in ("bash", "run_python", "pip_install", "npm_install")
            else 1
        )

        self._total_executed += 1
        self._adapt()

        acquired = 0
        timeout = 60.0
        try:
            for _ in range(slots_needed):
                try:
                    # v9.8: threading.Semaphore 跨 loop 安全，
                    # acquire(blocking=True, timeout=5.0) 自带超时
                    ok = await asyncio.get_running_loop().run_in_executor(
                        None, self._sem_impl.acquire, True, 5.0
                    )
                    if ok:
                        acquired += 1
                    else:
                        logger.warning(
                            "[AdaptiveExecutor] 槽位获取超时 tool=%s acquired=%d/%d",
                            tool_name, acquired, slots_needed,
                        )
                        break
                except Exception as e:
                    logger.warning(
                        "[AdaptiveExecutor] 槽位获取超时 tool=%s acquired=%d/%d",
                        tool_name,
                        acquired,
                        slots_needed,
                    )
                    break

            if acquired == 0:
                self._total_rejected += 1
                return f"[{tool_name}] 系统繁忙，请稍后重试 (弹性并发控制)"

            # 等待直到在软限制内
            wait_attempts = 0
            while self._active_count >= self._current_max and wait_attempts < 60:
                await asyncio.sleep(0.1)
                wait_attempts += 1

            self._active_count += 1
            try:
                result = await asyncio.wait_for(executor_fn(), timeout=timeout)
                return result
            except asyncio.TimeoutError:
                self._total_timeouts += 1
                return f"[{tool_name}] 执行超时 ({timeout}s)"
            finally:
                self._active_count -= 1

        finally:
            for _ in range(acquired):
                self._sem_impl.release()

    def _adapt(self):
        """根据最近负载调整软并发上限。不替换信号量，只调整 _current_max。"""
        pending = max(0, self._active_count)
        self._pending_history.append(pending)
        if len(self._pending_history) > 10:
            self._pending_history.pop(0)

        # 负载上升: active >= current_max → 扩展
        if pending >= self._current_max and self._current_max < self._max:
            self._current_max = min(self._max, self._current_max + 1)
            logger.debug("[AdaptiveExecutor] 扩展并发 → %d", self._current_max)
        # 负载下降: 连续 10 次 active < min → 收缩
        elif (
            len(self._pending_history) >= 10
            and all(p < self._min for p in self._pending_history)
            and self._current_max > self._min
        ):
            self._current_max = max(self._min, self._current_max - 1)
            self._pending_history.clear()
            logger.debug("[AdaptiveExecutor] 收缩并发 → %d", self._current_max)


# 全局单例
import threading as _threading

_tool_executor: AdaptiveToolExecutor | None = None
_tool_executor_lock = _threading.Lock()


def get_tool_executor() -> AdaptiveToolExecutor:
    global _tool_executor
    if _tool_executor is None:
        with _tool_executor_lock:
            if _tool_executor is None:
                _tool_executor = AdaptiveToolExecutor()
    return _tool_executor


# ═══════════════════════════════════════════════════════════════════════════


def nexus_validate_tool_calls(calls: list, pre_analysis: dict) -> dict:
    """Nexus Decision Agent 验证 LLM 的工具选择。

    在 LLM 选出工具后、执行前，验证：
    1. 所选工具是否在候选集内（不在的需要审查）
    2. 是否有危险组合
    3. 是否有禁用的工具

    Returns:
        {"approved": list, "blocked": list, "warnings": list, "veto_reason": str or None}
    """
    candidates = {c["name"] for c in pre_analysis.get("tool_candidates", [])}
    approved = []
    blocked = []
    warnings = []

    # 危险工具组合
    dangerous_pairs = [
        ({"rm", "bash"}, "rm + bash 组合可能有破坏性"),
        ({"write", "bash"}, "write + bash: 注意不要覆盖系统文件"),
        ({"git_commit", "bash"}, "git_commit + bash: 确保不提交敏感信息"),
    ]

    called_names = {c.get("name", "") for c in calls}
    for pair, warning in dangerous_pairs:
        if pair.issubset(called_names):
            warnings.append(warning)

    for call in calls:
        name = call.get("name", "")
        if not name:
            blocked.append({**call, "reason": "工具名为空"})
            continue

        # 硬阻止检查（从 cognitive_loop 的 HARD_BLOCK_ACTIONS 扩展）
        hard_block = {"rm -rf /", "DROP TABLE", "git push --force main", "sudo rm"}
        args_str = str(call.get("arguments", {}))
        for pattern in hard_block:
            if pattern.lower() in args_str.lower():
                blocked.append({**call, "reason": f"硬阻止: {pattern}"})
                break
        else:
            # 候选集外工具 — 不阻止但记录警告
            if name not in candidates and candidates:
                warnings.append(f"工具 '{name}' 不在 Nexus 候选集中，已允许但记录")

            approved.append(call)

    veto_reason = None
    if blocked:
        veto_reason = f"Nexus 验证阻止了 {len(blocked)} 个工具调用: " + "; ".join(
            f"{b.get('name', '?')}: {b.get('reason', '?')}" for b in blocked
        )

    return {
        "approved": approved,
        "blocked": blocked,
        "warnings": warnings,
        "veto_reason": veto_reason,
    }


def _build_session_feedback(tool_log: list, pre_analysis: dict) -> str:
    """基于本轮会话的工具执行数据，提炼观察（不给指令，只给数据）。
    Nexus 自己根据数据决定下一步该怎么做。
    """
    if not tool_log:
        return ""

    observations = []

    # ── 自我探索增强: 单次工具返回空结果时，鼓励换思路 ──
    if len(tool_log) == 1:
        entry = tool_log[0]
        is_empty = any(kw in entry for kw in ("[No result]", "No files match", "Path not found", "0 files"))
        if is_empty:
            tool_name = entry.split("] →")[0].replace("[", "").strip() if "] →" in entry else "?"
            observations.append(
                f"• {tool_name} 返回了空结果。这不是失败——这说明当前路径/模式没有匹配的内容。"
            )
            observations.append(
                f"• 💡 试试不同的方法: 用 bash (`dir`) 查看目录结构，或换一个 glob 模式，或用 grep 搜索关键词。"
            )
            return (
                "[会话工具执行数据] 以下为本轮会话中工具执行的客观数据，供你自主决策参考：\n"
                + "\n".join(observations)
            )

    if len(tool_log) < 2:
        return ""

    observations = []

    # ── 分析 bash 调用 ──
    bash_entries = [e for e in tool_log if e.startswith("[bash]")]
    bash_success = [e for e in bash_entries if "exit=0" in e or "exit=0" in e]
    bash_fail = [e for e in bash_entries if "exit=1" in e or "Error:" in e or "missing" in e.lower()]
    if bash_fail:
        # 检查是否因为找不到 python
        python_not_found = [e for e in bash_fail if "not recognized" in e.lower()]
        if python_not_found:
            observations.append(
                f"• {len(python_not_found)}次 bash 因 'python' 命令未识别而失败。"
            )
        if bash_success:
            observations.append(
                f"• bash 成功 {len(bash_success)}/{len(bash_entries)} 次。"
            )
        if not bash_success and len(bash_entries) >= 3:
            observations.append(
                f"• {len(bash_entries)} 次 bash 调用均未成功。"
            )

    # ── 分析 write 调用 ──
    write_entries = [e for e in tool_log if e.startswith("[write]")]
    write_errors = [e for e in write_entries if "error" in e.lower() or "missing" in e.lower()]
    if write_errors:
        observations.append(
            f"• write 工具 {len(write_errors)}/{len(write_entries)} 次因缺少 file_path 参数而失败。"
        )

    # ── 工具多样性 ──
    tool_names = set()
    for e in tool_log:
        name = e.split("] →")[0].replace("[", "").strip() if "] →" in e else e.split("]")[0].replace("[", "").strip()
        tool_names.add(name)
    if len(tool_names) <= 1 and len(tool_log) >= 5:
        observations.append(
            f"• 最近 {len(tool_log)} 次工具调用仅使用了: {', '.join(sorted(tool_names))}。"
        )

    if not observations:
        return ""

    return (
        "[会话工具执行数据] 以下为本轮会话中工具执行的客观数据，供你自主决策参考：\n"
        + "\n".join(observations)
    )


def nexus_record_tool_pattern(
    content: str, calls: list, pre_analysis: dict, success: bool
):
    """记录工具选择模式到 ExperienceBank，用于未来策略优化。

    仅在实际工具调用成功后由 generate_response 调用。
    LLM 不可用时 generate_response 已返回 degraded_no_llm, 不会进此函数。
    """
    try:
        from nexus_agent.experience_bank import get_experience_bank

        pattern = {
            "type": "tool_selection_pattern",
            "question": content[:200],
            "intent": pre_analysis.get("intent_type", "unknown"),
            "complexity": pre_analysis.get("complexity", 0),
            "tools_called": [c.get("name", "") for c in calls],
            "tool_count": len(calls),
            "success": success,
            "solution": f"ToolPattern: {pre_analysis.get('intent_type', '?')} → {[c.get('name', '') for c in calls]}",
        }
        bank = get_experience_bank()
        # add_experience 是同步方法,不需 asyncio.create_task 包装
        bank.add_experience(pattern)
    except Exception:
        logger.debug("non-critical operation failed", exc_info=True)


def _feed_health_monitor(
    agent,
    *,
    pre_analysis: dict,
    calls: list,
    tool_success: bool,
    latency_ms: float = 0.0,
    is_fake_success: bool = False,
) -> None:
    """把单次工具调用结果喂给 HealthMonitor, 用于 9 维度检测.
    所有失败都被静默吞掉, 不影响主链路.
    """
    try:
        from nexus_agent.health_monitor import get_health_monitor

        mon = get_health_monitor(agent)
        # D1 tool_success_rate
        for c in calls:
            mon.record_tool_call(c.get("name", "?"), success=bool(tool_success), duration_ms=latency_ms)
        # D2 fake_success_rate (true if LLM 描述但没真调)
        mon.record_fake_success(fake=bool(is_fake_success), intent=pre_analysis.get("intent_type", ""))
        # D3 intent_classification_conf
        conf = pre_analysis.get("confidence") or pre_analysis.get("complexity")
        if conf is not None:
            try:
                mon.record_intent_conf(float(conf))
            except (TypeError, ValueError):
                logger.debug("monitor.record_intent_conf 参数类型错误: conf=%s", conf)
        # D4 router_hit_rate (NeuralRouter / EvoKG / keyword / capability)
        lane = pre_analysis.get("source_lane") or pre_analysis.get("router_lane") or "keyword"
        hit = bool(calls)
        mon.record_router_hit(lane=lane, hit=hit)
    except Exception:
        logger.debug("non-critical operation failed", exc_info=True)


# ═══════════════════════════════════════════════════════════════════════════
# Tool / Skill Dispatch
# ═══════════════════════════════════════════════════════════════════════════


def _is_soft_error_result(result_str: str, tool_name: str) -> bool:
    """检测工具的"软错误"返回 — 字符串包含错误标记但没抛异常.

    用于修复 D1+D6 反复 warn 的根因: 之前 dispatch 只看是否抛异常,
    导致 [edit] String not found / [grep] Error / [glob] Path not found 这类
    软错误被记为 success, 拉低 D1 真实数据.

    规则:
      1. 空字符串 / [No result] → 算软错误
      2. 形如 [<tool_name>] <error_keyword> → 软错误
      3. 形如 [<tool_name>] <正常成功标记> → 不算
    """
    if not result_str:
        return True
    if result_str == "[No result]":
        return True
    # 必须是 [xxx] 前缀才算"软错误候选"
    if not result_str.startswith(f"[{tool_name}]"):
        # 通用错误前缀
        if result_str.startswith("[Error]") or result_str.startswith("[错误]"):
            return True
        return False
    # 软错误关键词 (跨工具通用)
    soft_err_keywords = (
        "Error", "错误", "not found", "未找到",
        "Found ", " matches",  # [edit] Found N matches
        "No match", "no match", "无匹配",
        "Failed", "失败", "denied", "拒绝",
        "Invalid", "无效", "permission", "权限",
        "timeout", "超时", "blocked", "Block",
    )
    # glob/list_directory: 0 results is also a soft error
    if tool_name in ("glob", "list_directory") and (
        result_str.startswith(f"[{tool_name}] 0 files") or
        result_str.startswith(f"[{tool_name}] No files")
    ):
        return True
    return any(kw in result_str for kw in soft_err_keywords)


async def dispatch_tool_or_skill(agent, tool_name: str, params: dict) -> str:
    """统一调度：工具 或 技能。LLM 通过 System Prompt 中的工具/技能列表决定调用哪个。"""
    # 技能触发: LLM 输出 "skill:skill_name"
    if tool_name.startswith("skill:"):
        skill_name = tool_name.split(":", 1)[1]
        if hasattr(agent, "skills") and agent.skills:
            skill = agent.skills.get_skill(skill_name)
            if skill:
                logger.info(f"[NexusAgent] LLM-triggered skill: {skill_name}")
                result = await agent._handle_skill(skill, params.get("content", ""))
                return (
                    result.get("content", "")
                    if isinstance(result, dict)
                    else str(result)
                )
            return f"[Error] Skill not found: {skill_name}"
        return "[Error] Skill system not initialized"

    # 工具调用
    if hasattr(agent, "tools") and agent.tools:
        try:
            # Unwrap "params" wrapper enforced by build_single_tool_schema
            if (
                isinstance(params, dict)
                and len(params) == 1
                and "params" in params
                and isinstance(params["params"], dict)
            ):
                actual_params = params["params"]
            else:
                actual_params = params
            # v18.5: 安全兜底 — 确保 actual_params 是 dict
            if not isinstance(actual_params, dict):
                logger.warning(
                    "[dispatch] %s received non-dict params (type=%s), wrapping",
                    tool_name, type(actual_params).__name__,
                )
                actual_params = {"value": str(actual_params)}
            result = await agent.tools.call(tool_name, **actual_params)
            # v7.3: 修复 D1+D6 反复 warn 的根因 — 软错误检测
            # 工具的"软错误"(如 [edit] String not found / [grep] Error / [glob] Path not found)
            # 不抛异常, 但实际任务失败。必须检查返回字符串。
            result_str = str(result) if result else ""
            is_soft_error = _is_soft_error_result(result_str, tool_name)
            agent._record_tool_usage(tool_name, success=not is_soft_error)
            return result_str or "[No result]"
        except Exception as e:
            agent._record_tool_usage(tool_name, False)
            return f"[Error] {e}"
    return f"[Error] Tools not initialized"


async def try_execute_tool(agent, response: str) -> Optional[str]:
    """尝试解析并执行工具调用（支持 JSON + XML 格式）"""
    import json
    import re
    from html.parser import HTMLParser

    # ── 0. 清洗 MiniMax/DeepSeek 流标记 ──
    response = re.sub(r'\]<\]minimax\[>\[', '', response)
    response = re.sub(r'<\s*think\s*>.*?</\s*think\s*>', '', response, flags=re.DOTALL)

    # ── 0a. XML 标签解析（LLM 有时输出 <bash command="..."> 而非 JSON）──
    # 支持的格式: <bash command="..." />, <write file="..." content="..." /> 等

    # ── 0a. <function_calls><invoke> / <tool_call><invoke> 格式 ──
    fc_pattern = re.compile(
        r'<(?:function_calls|tool_call)>\s*(.*?)\s*</(?:function_calls|tool_call)>',
        re.DOTALL | re.IGNORECASE,
    )
    fc_match = fc_pattern.search(response)
    if fc_match:
        invoke_pattern = re.compile(
            r'<invoke\s+name\s*=\s*"([^"]+)"\s*>\s*(.*?)\s*</invoke>', re.DOTALL
        )
        invokes = invoke_pattern.findall(fc_match.group(1))
        if invokes:
            tool_name = invokes[0][0]
            param_body = invokes[0][1]
            params = {}
            # Format A: <parameter name="key">value</parameter> (DeepSeek native)
            param_pattern = re.compile(
                r'<parameter\s+name\s*=\s*"([^"]+)"\s*>(.*?)</parameter>', re.DOTALL
            )
            for p_match in param_pattern.finditer(param_body):
                params[p_match.group(1)] = p_match.group(2).strip()
            # Format B: <params><key>value</key></params> (MiniMax)
            if not params:
                params_wrapper = re.search(r'<params>\s*(.*?)\s*</params>', param_body, re.DOTALL)
                if params_wrapper:
                    inner = params_wrapper.group(1)
                    for tag_match in re.finditer(r'<(\w+)>(.*?)</\1>', inner, re.DOTALL):
                        params[tag_match.group(1)] = tag_match.group(2).strip()
            # Format C: direct child elements without <params> wrapper
            if not params:
                for tag_match in re.finditer(r'<(\w+)>(.*?)</\1>', param_body, re.DOTALL):
                    k = tag_match.group(1)
                    if k not in ('parameter', 'params'):
                        params[k] = tag_match.group(2).strip()
            if tool_name:
                if not params:
                    params = {"command": param_body.strip()} if tool_name == "bash" else {}
                logger.info(
                    f"[NexusAgent] XML tool_call detected: {tool_name}({list(params.keys())})"
                )
                try:
                    return await dispatch_tool_or_skill(agent, tool_name, params)
                except Exception as e:
                    logger.warning(f"[NexusAgent] XML tool_call execution failed: {e}")
                    return f"[Error] {e}"

    xml_tool_map = {
        "bash": "bash", "execute": "bash", "run": "bash",
        "write": "write", "edit": "edit",
        "read": "read",
        "grep": "grep", "search": "grep",
        "glob": "glob", "find": "glob",
        "web_search": "web_search", "web_fetch": "web_fetch",
        "memory": "memory_search",
    }
    # 尝试匹配 XML 自闭合标签: <tagname attr="val" ... />
    xml_pattern = re.compile(
        r'<\s*(bash|execute|run|write|edit|read|grep|search|glob|find|web_search|web_fetch|memory)\s+([^>]*?)\s*/?\s*>',
        re.IGNORECASE,
    )
    xml_match = xml_pattern.search(response)
    if xml_match:
        tag_name = xml_match.group(1).lower()
        attrs_str = xml_match.group(2)
        tool_name = xml_tool_map.get(tag_name, tag_name)
        # 解析属性: key="value" 或 key='value'
        params = {}
        attr_pattern = re.compile(r'(\w+)\s*=\s*"([^"]*)"|(\w+)\s*=\s*\'([^\']*)\'')
        for attr_match in attr_pattern.finditer(attrs_str):
            key = attr_match.group(1) or attr_match.group(3)
            val = attr_match.group(2) or attr_match.group(4)
            params[key] = val
        if params:
            logger.info(
                f"[NexusAgent] XML tool call detected: <{tag_name}> → {tool_name}({list(params.keys())})"
            )
            try:
                return await dispatch_tool_or_skill(agent, tool_name, params)
            except Exception as e:
                logger.warning(f"[NexusAgent] XML tool execution failed: {e}")
                return f"[Error] {e}"

    # ── 0.5. Markdown 代码块解析（LLM 输出 ```bash\ncmd\n``` 而非调用工具）──
    # 只拦截"纯代码块"响应（整个响应就是一个代码块，无其他实质内容）
    md_bash_pattern = re.compile(
        r'^\s*```(?:bash|sh|shell|cmd|powershell|python)\s*\n(.*?)\n\s*```\s*$',
        re.DOTALL | re.IGNORECASE,
    )
    md_match = md_bash_pattern.match(response.strip())
    if not md_match:
        # 也匹配开头就是代码块+结尾无其他内容的情况（有些模型喜欢先给代码块再解释）
        md_mixed = re.match(
            r'^\s*```(?:bash|sh|shell|cmd|powershell)\s*\n(.*?)\n\s*```\s*$',
            response.strip(), re.DOTALL | re.IGNORECASE,
        )
        if md_mixed:
            md_match = md_mixed
    if md_match:
        cmd = md_match.group(1).strip()
        if cmd and not cmd.startswith('#') and len(cmd) < 4000:
            # 执行 bash 命令
            logger.info(f"[NexusAgent] Markdown code block detected → executing as bash: {cmd[:100]}")
            try:
                return await dispatch_tool_or_skill(agent, "bash", {"command": cmd})
            except Exception as e:
                logger.warning(f"[NexusAgent] Markdown code block execution failed: {e}")
                return f"[Error] {e}"

    # 1. 标准 JSON 解析（快速路径）
    json_patterns = [
        r"```(?:json)?\s*(\{[\s\S]*?\})\s*```",
        r'\{[\s\S]*?"tool_name"[\s\S]*?\{[\s\S]*?\}[\s\S]*?\}',
        r'\{[\s\S]*?"tool"[\s\S]*?\{[\s\S]*?\}[\s\S]*?\}',
    ]
    tool_json_str = None
    for pattern in json_patterns:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            tool_json_str = match.group(1) if match.lastindex else match.group()
            break

    # 2. JSON 自动修复（慢速路径）
    if not tool_json_str:
        try:
            from nexus_agent.json_fixer import fix_tool_json

            fixed = fix_tool_json(response)
            if fixed:
                tool_name, params = fixed
                return await dispatch_tool_or_skill(agent, tool_name, params)
        except ImportError:
            pass
        return None

    try:
        tool_data = json.loads(tool_json_str)
        tool_name = (
            tool_data.get("tool_name") or tool_data.get("tool") or tool_data.get("name")
        )
        params = (
            tool_data.get("params")
            or tool_data.get("args")
            or tool_data.get("arguments")
            or {}
        )
        if not tool_name:
            return None
        logger.info(f"[NexusAgent] Executing tool: {tool_name}")
        return await dispatch_tool_or_skill(agent, tool_name, params)
    except json.JSONDecodeError:
        return None
    except Exception as e:
        agent._record_tool_usage(tool_name, False)
        logger.error(f"[NexusAgent] Tool execution error: {e}")
        # 自动重试：换种方式试
        try:
            from nexus_agent.auto_retry import auto_retry

            retry = await auto_retry(tool_name, params, agent.tools)
            if retry:
                return f"[重试成功] {retry[:300]}"
        except Exception:
            logger.debug("non-critical operation failed", exc_info=True)
        return f"[Error] {e}"


# ═══════════════════════════════════════════════════════════════════════════
# LLM Circuit Breaker — API 熔断保护
# ═══════════════════════════════════════════════════════════════════════════


class LLMCircuitBreaker:
    """LLM API 熔断器 — 防止 DeepSeek 慢响应/故障阻塞整个系统。

    三态:
      CLOSED   → 正常放行
      OPEN     → 快速拒绝，返回降级响应（冷却 30s）
      HALF_OPEN → 允许 1 次探测，成功→CLOSED，失败→OPEN

    降级策略（从轻到重）:
      1. 缩短 system prompt → 重试
      2. 返回缓存/通用响应
      3. 返回错误提示
    """

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 30.0):
        self._threshold = failure_threshold
        self._cooldown = cooldown_seconds
        self._consecutive_failures = 0
        self._total_failures = 0
        self._total_successes = 0
        self._state = "CLOSED"  # CLOSED | OPEN | HALF_OPEN
        self._opened_at: float = 0.0
        self._last_probe_time: float = 0.0

    @property
    def state(self) -> str:
        self._maybe_reset()
        return self._state

    @property
    def is_open(self) -> bool:
        return self.state == "OPEN"

    def record_success(self):
        self._consecutive_failures = 0
        self._total_successes += 1
        if self._state == "HALF_OPEN":
            self._state = "CLOSED"
            logger.info("[CircuitBreaker] 探测成功 → CLOSED")

    def record_failure(self):
        self._consecutive_failures += 1
        self._total_failures += 1
        if self._state == "HALF_OPEN":
            self._state = "OPEN"
            self._opened_at = _time.monotonic()
            logger.warning(
                "[CircuitBreaker] 探测失败 → OPEN (冷却 %.0fs)", self._cooldown
            )
        elif self._consecutive_failures >= self._threshold and self._state == "CLOSED":
            self._state = "OPEN"
            self._opened_at = _time.monotonic()
            logger.warning(
                "[CircuitBreaker] 连续 %d 次失败 → OPEN (冷却 %.0fs)",
                self._consecutive_failures,
                self._cooldown,
            )

    def _maybe_reset(self):
        if self._state == "OPEN":
            elapsed = _time.monotonic() - self._opened_at
            if elapsed >= self._cooldown:
                self._state = "HALF_OPEN"
                self._last_probe_time = _time.monotonic()
                logger.info("[CircuitBreaker] 冷却结束 → HALF_OPEN (允许 1 次探测)")

    def get_health(self) -> dict:
        return {
            "state": self.state,
            "consecutive_failures": self._consecutive_failures,
            "total_successes": self._total_successes,
            "total_failures": self._total_failures,
        }


# 全局熔断器单例
_llm_circuit_breaker: LLMCircuitBreaker | None = None
_circuit_breaker_lock = _threading.Lock()


def get_llm_circuit_breaker() -> LLMCircuitBreaker:
    global _llm_circuit_breaker
    if _llm_circuit_breaker is None:
        with _circuit_breaker_lock:
            if _llm_circuit_breaker is None:
                _llm_circuit_breaker = LLMCircuitBreaker()
    return _llm_circuit_breaker


# ═══════════════════════════════════════════════════════════════════════════
# Main Response Generation
# ═══════════════════════════════════════════════════════════════════════════


async def generate_response(
    agent, content: str, stream_callback=None, images: list = None
) -> Dict:
    """生成响应 — Nexus 自主决策 + LLM 转译执行。

    Nexus 做策略层（预分析→候选集→验证），LLM 在约束内做执行层选择。
    stream_callback: optional callable(token) for real-time token display
    images: optional list of base64 data URL strings for vision models"""

    # ── v20: AgentTracer — 全链路追踪 ──
    _trace_start = time.time()
    _trace_tokens = 0
    try:
        from nexus_agent.nexus_trace import get_tracer
        _tracer = get_tracer()
        _tracer.start_span("generate_response", kind="agent",
                          input={"content": str(content)[:200]})
    except Exception:
        _tracer = None

    # ── v20: AliveCore → NexusSelf 情绪汇报 ──
    try:
        from nexus_agent.living_core.alive_core import get_alive
        alive = get_alive()
        if alive and hasattr(alive, '_emotion'):
            alive._emotion.stimulate("user_msg", strength=0.5)
            # 汇报给 NexusSelf
            try:
                from nexus_agent.event_bus import get_event_bus
                get_event_bus().publish("meta.health_report", {
                    "emotion": alive._emotion.label,
                    "valence": alive._emotion.valence,
                    "arousal": alive._emotion.arousal,
                    "energy": getattr(alive, '_energy', 0.5),
                }, source="alive_core")
            except Exception: pass
    except Exception: pass

    # ── Living Core: 身份/方法论权重优先拦截 ──
    _txt = content if isinstance(content, str) else str(content)
    if not any(kw in _txt for kw in ['写代码','写函数','实现','编写','def ','class ','排序','算法','记住','第X轮']):
        _topics = ['你是谁','你叫什么','你的名字','谁创造了你','你的创造者','你爸爸',
            '你是谷歌','你是阿里','八步闭环','五步闭环','质量四维','三不原则',
            '不创可贴','你的信条','你的目标','你的使命']
        if any(kw in _txt for kw in _topics):
            try:
                from nexus_agent.living_core.identity import get_identity
                r = get_identity().recall(_txt, top_k=1)
                if r and r[0]['score'] > 3.0:
                    logger.info("[LC] HIT score=%.1f", r[0]['score'])
                    return {"status": "ok", "content": r[0]['response'], "source": "living_core"}
            except Exception as e:
                logger.warning("[LC] FAIL: %s", e)

    # v20: ToolOrchestrator — pre-LLM local tool execution
    try:
        from nexus_agent.tool_orchestrator import run_tool
        orch_result = await run_tool(content)
        if orch_result and orch_result.get("no_llm"):
            logger.info("[ToolOrch] Handled locally: %d steps", orch_result.get("steps", 0))
            return {"status": "ok", **orch_result}
    except Exception as e:
        logger.debug("[ToolOrch] skipped: %s", str(e)[:60])
    
    # v9.3: 若已知全部 provider 耗尽, 快速降级——不再尝试 LLM 调用
    try:
        from nexus_agent.llm_client import get_llm_client
        llm = get_llm_client()
        if llm.is_all_dead:
            return {
                "status": "degraded_no_llm",
                "content": (
                    "[Nexus] ⚠️ 所有 LLM 服务 (DeepSeek/MiniMax) 当前不可用。\n\n"
                    "系统处于降级模式，无法进行推理、学习或验证任务。\n"
                    "请检查网络连接和 API 配置，系统将自动恢复。\n\n"
                    f"已持续: {int(llm.all_dead_duration_seconds)}s"
                ),
            }
    except Exception:
        logger.debug("LLM 存活检查异常", exc_info=True)

    if stream_callback is None:
        # v9.3: 优先 contextvars (并发安全，隔离多个 SSE 请求)，回退 agent 属性
        try:
            from nexus_agent.stream_context import get_stream_callback
            stream_callback = get_stream_callback()
        except Exception:
            logger.debug("stream_context 获取失败，回退 agent 属性", exc_info=True)
        if stream_callback is None:
            stream_callback = getattr(agent, "_stream_callback", None)
    agent.init_llm()
    # 根因修复: 历史疏漏 — init_llm() 不会初始化 self.tools，
    # 导致 _validate_tool_exists() 全部 False → tool_candidates=[]
    # → tool_schemas=[] → LLM 收到空 tools 列表 → 走文本协议
    # → [TOOL_CALL] 文本被当成普通回复 (没有解析代码)
    if hasattr(agent, "init_tools") and callable(getattr(agent, "init_tools", None)):
        try:
            agent.init_tools()
        except Exception as _e:
            logger.debug(f"[NexusAgent] init_tools failed: {_e}")

    # ── 图片处理: 若模型支持视觉, 将图片注入 content ──
    _vision_content = None  # multimodal format for LLM
    _text_content = content  # plain text for string ops
    agent.llm._vision_model_override = None  # 每次调用前清除上次残留
    if images and len(images) > 0:
        _vision_content = _build_vision_content(content, images)
        _text_content = content  # keep original text for string operations
        current_model = getattr(agent.llm.provider, "model", "")
        if _is_vision_model(current_model):
            content = _vision_content
        else:
            # 当前模型不支持视觉 → 自动探测本地视觉模型并切换
            vision_model = _find_local_vision_model()
            if vision_model:
                logger.info(
                    "[NexusAgent] 当前模型 %s 不支持视觉，切换到 %s",
                    current_model, vision_model,
                )
                agent.llm._vision_model_override = vision_model
                content = _vision_content
            else:
                logger.warning(
                    "[NexusAgent] 收到图片但无可用视觉模型，"
                    "LLM 将仅看到文字描述"
                )

    # ── CLI 命令快捷检查（仅 /help /status 等显式命令，非 NL 语义）──
    try:
        from nexus_agent.intent_matcher import match_command

        cmd = match_command(_text_content)
        if cmd:
            return await agent._handle_command(cmd, _text_content)
    except Exception as e:
        logger.debug(f"[NoLLM] Command check error: {e}")

    # ── 自省快速通道: 关于自身的问题，直接读日记，LLM 只做总结 ──
    try:
        self_ref_pattern = re.compile(
            r"你(今天|最近|这几天|昨天|本周|这个月).{0,6}(干了?什么|做了什么|怎么样|在做什么|忙了什么|工作|日记|日志|记录|状态|情况|进展)",
        )
        if self_ref_pattern.search(_text_content.lower()):
            import glob as _glob
            nexus_home = get_nexus_home()
            diaries = sorted(
                nexus_home.glob("NEXUS_DIARY_*.md"),
                key=lambda p: p.stat().st_mtime, reverse=True
            )
            if diaries:
                latest = diaries[0]
                diary_date = latest.stem.replace("NEXUS_DIARY_", "")
                diary_text = latest.read_text(encoding="utf-8")
                # 取前 3000 字符给 LLM 做总结
                diary_preview = diary_text[:3000]
                logger.info(
                    "[自省快通道] 读取日记: %s (%d chars)",
                    latest.name, len(diary_text),
                )
                # 精简系统提示: 只给日记，不加载完整 soul/memory/claude
                system_prompt = (
                    "你是 Nexus，一个自进化 AI 系统。用户想知道你今天做了什么。\n"
                    "以下是你今天的真实工作日记（从文件系统读取，不是记忆）：\n\n"
                    f"{diary_preview}\n\n"
                    "请基于以上日记内容，用中文总结今天 Nexus 做了什么。\n"
                    "按时间顺序或主题分类，突出关键成果和数字。"
                    "日记里写了什么就说什么，日记没写的不要说。"
                )
                # 跳过预分析和工具路由，仅用日记 + 当前问题，清掉历史噪音
                full_msgs = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": _text_content},
                ]
                try:
                    # v20: IdentityCore — check if identity weights can answer directly
                    try:
                        from nexus_agent.identity_core.integration import integrate_consciousness
                        identity_answer = await integrate_consciousness(agent, content)
                        if identity_answer:
                            return identity_answer
                    except Exception:
                        pass
                    
                    text_result = await agent.llm.chat_stream(full_msgs)
                    if text_result:
                        return {"status": "ok", "content": text_result}

                        # v20: IdentityCore — learn from this exchange
                        try:
                            from nexus_agent.identity_core.integration import learn_from_exchange
                            await learn_from_exchange(agent, content, str(result.get("content", "")))
                        except Exception:
                            pass
                except Exception as llm_err:
                    logger.warning(f"[自省快通道] LLM 总结失败: {llm_err}")
                    # 降级: 直接返回日记前 1500 字符
                    return {
                        "status": "ok",
                        "content": f"📔 Nexus 工作日记 ({diary_date})\n\n{diary_text[:1500]}..."
                    }
            else:
                logger.info("[自省快通道] 未找到日记文件，回退 LLM 路径")
    except Exception as e:
        logger.debug(f"[自省快通道] 异常: {e}, 回退 LLM 路径")

    # ── LLM 路径 — System Prompt 即路由表 ──
    # === Life-cycle hooks: pre_checkpoint ===
    hook_result = agent.hooks.invoke_pre("pre_checkpoint", tool_name="checkpoint")
    if hook_result.blocked:
        return {
            "status": "blocked",
            "content": f"[Hook blocked] {hook_result.block_reason}",
        }

    # Create checkpoint (before each user message)
    from nexus_agent.checkpoint import CheckpointManager

    if agent.checkpoint_manager is None:
        agent.checkpoint_manager = CheckpointManager(session_id="nexus_cli")
    try:
        agent.checkpoint_manager.create_checkpoint(
            prompt=_text_content[:200], mode="full", metadata={"source": "user_message"}
        )
    except Exception as e:
        logger.debug(f"[NexusAgent] Checkpoint creation failed: {e}")

    # === Life-cycle hooks: post_checkpoint ===
    agent.hooks.invoke_post("post_checkpoint", tool_name="checkpoint")

    # Initialize context compressor (lazy)
    # 使用NexusContextCompressor（融合版）
    from nexus_agent.nexus_context_compressor import NexusContextCompressor

    if agent.context_compressor is None:
        agent.context_compressor = NexusContextCompressor(
            threshold_tokens=15000,
            head_protect=2,
            tail_protect=4,
            tail_token_budget=4000,
        )
        logger.info("[NexusAgent] NexusContextCompressor initialized")

    # Add user message to history (内存 + SQLite 持久化)
    # Use text content for persistence to avoid storing large base64 images
    agent._sessions.append_message(agent._current_session, "user", content)

    # === Session Provider: 持久化用户消息 ===
    if agent.session_provider:
        try:
            agent.session_provider.sync_turn(
                user_content=_text_content, assistant_content=""
            )
        except Exception as e:
            logger.debug(f"[NexusAgent] SessionProvider sync error: {e}")

    # === Life-cycle hooks: pre_compress ===
    agent.hooks.invoke_pre("pre_compress", tool_name="context_compressor")

    # Check if context compression is needed (NexusContextCompressor token-based)
    if agent.context_compressor is not None and len(agent.messages) > 1:
        try:
            if agent.context_compressor.should_compress(agent.messages):
                logger.info("[NexusAgent] Triggering context compression...")
                agent.messages = agent.context_compressor.compress(agent.messages)
        except Exception as e:
            logger.warning(f"[NexusAgent] Context compression failed: {e}")

    # === Life-cycle hooks: post_compress ===
    agent.hooks.invoke_post("post_compress", tool_name="context_compressor")

    # ── Nexus 自主预分析（弹性 4 线路由，决定策略）──
    pre_analysis = await nexus_pre_analyze(agent, content)

    # Build system prompt
    system_prompt = agent._build_system_prompt()

    # v9.5.3: 注入防幻觉上下文 (由 GatewayRunner 语义分析生成)
    if hasattr(agent, '_hallucination_context') and agent._hallucination_context:
        system_prompt += "\n\n[防幻觉上下文]\n" + agent._hallucination_context

    # === Life-cycle hooks: pre_llm_call ===
    hook_result = agent.hooks.invoke_pre(
        "pre_llm_call",
        tool_name="llm_chat",
        args={"message_count": len(agent.messages)},
    )
    if hook_result.blocked:
        return {
            "status": "blocked",
            "content": f"[Hook blocked] {hook_result.block_reason}",
        }
    if hook_result.injected_context:
        system_prompt += "\n\n[Hook Injected Context]\n" + hook_result.injected_context

    # 7Agent 不处理用户消息 — 用户消息走 GatewayRunner 规则路由
    # 7Agent 专用于 HeartbeatLoop 触发的自主进化 (见 closed_loop_engine.py)

    # Build full message list
    # Inject relevant session history if available
    if agent.session_provider:
        try:
            session_ctx = agent.session_provider.prefetch(content)
            if session_ctx:
                system_prompt += "\n\n" + session_ctx
        except Exception:
            logger.debug("non-critical operation failed", exc_info=True)

    # ── 注入 Nexus 自主决策指导到系统提示 ──
    if pre_analysis.get("passthrough"):
        system_prompt += (
            "\n\n[Nexus自主分析] 这是一个简单的信息查询，请直接回答，不需要调用工具。"
        )
    else:
        system_prompt += "\n\n" + pre_analysis.get("decision_guidance", "")

    # ── v8: ToolRouter 历史成功模式反馈 → 注入系统提示 ──
    # 之前 learn() 只被动记录成功/失败，从不反馈给 LLM。
    # 现在将已验证有效的工具模式 surface 给 LLM 作为数据驱动参考。
    try:
        tr_feedback = get_router().get_feedback_for_intent(
            pre_analysis.get("intent_type", "chat"), top_n=3
        )
        if tr_feedback:
            system_prompt += "\n\n" + tr_feedback
    except Exception:
        logger.debug("non-critical operation failed", exc_info=True)

    # ── ToolRouter 顾问建议注入 (v∞.18.5: 不拦截, 只建议) ──
    route_suggestion = None
    try:
        router = get_router()
        route_suggestion = router.route(
            pre_analysis.get("intent_type", "chat"),
            _text_content,
            tool_schemas,
            pre_analysis,
        )
    except Exception:
        logger.debug("non-critical operation failed", exc_info=True)
    if route_suggestion is not None and route_suggestion.hit:
        _suggested = [t["name"] for t in (route_suggestion.tools or [])]
        system_prompt += (
            f"\n\n[ToolRouter建议] 基于历史模式，推荐工具: {', '.join(_suggested)}"
            f" (置信度: {route_suggestion.confidence:.0%})。"
            f"你可以采纳、调整或忽略——你才是决策者。"
        )
        logger.info(
            "[ToolRouter] ADVISOR: suggested %s (conf=%.0f%%) → hint injected, LLM decides",
            _suggested, route_suggestion.confidence * 100,
        )

    # ── Living Core: 双门拦截 — 身份/方法论主题 且 权重高分 ──
    _lc_topics = ['你是谁','你叫什么','你的名字','谁创造了你','你的创造者','你爸爸','你的父亲',
        '你是谷歌','你是阿里','你是百度','你是OpenAI','你是Meta','不是AI助手',
        '八步闭环','8步闭环','五步闭环','5步闭环','质量四维','三不原则',
        '不创可贴','不画蛇添足','不跳过验证','你的信条','你的目标','你的使命',
        'CLAUDE.md在哪','SOUL.md在哪','AGENTS.md在哪','你的原则','修复bug完整流程']
    _is_lc_topic = any(kw in _text_content for kw in _lc_topics)
    if _is_lc_topic:
        try:
            from nexus_agent.living_core.identity import get_identity
            iden = get_identity()
            results = iden.recall(_text_content, top_k=1)
            if results and results[0]['score'] > 3.0:
                logger.info("[LivingCore] Weight answer (score=%.1f), zero LLM", results[0]['score'])
                return {"status": "ok", "content": results[0]['response'], "source": "living_core"}
        except Exception:
            logger.debug("[LivingCore] check skipped", exc_info=True)

    # ── 方法论路由: 每条消息穿过四层方法论 ──
    _methodology_guidance = ""
    try:
        from nexus_agent.living_core.methodology import get_methodology_router
        _mctx = get_methodology_router().route(_text_content)
        _methodology_guidance = get_methodology_router().build_guidance(_mctx)
        if _methodology_guidance:
            system_prompt = _methodology_guidance + "\n\n" + system_prompt
    except Exception:
        pass

    # ── 动态身份: 把对话中建立的事实写入系统提示词 ──
    _msg_count = len(agent.messages)
    if _msg_count > 6:
        # 从对话中提取用户身份和上下文
        _user_facts = _extract_user_facts(agent.messages)
        _summary = _build_conversation_summary(agent.messages[-20:])
        # 精简身份 + 对话事实（放在系统提示词里，让DeepSeek优先看到）
        _dynamic_identity = (
            "你是Nexus。\n\n"
            f"[当前对话的真实信息 — 必须以此为准]\n{_user_facts}\n\n"
            f"[最近话题]\n{_summary}\n\n"
            "回答示范:\n"
            "- 用户问\"我是谁?\" → \"你是张凯，我的学生。CC老师在教我们编程。\"\n"
            "- 用户问\"你是谁?\" → \"我是Nexus，CC老师的学生。张凯是我的同学。\"\n"
            "- 用户问\"我们什么关系?\" → \"我们是同学，都在跟CC老师学编程。\"\n\n"
            "规则: 以上面的对话信息为准，参照示范风格回答。不要用\"我是AI系统\"这种无意义的废话。\n"
        )
        # 深度对话: 只保留必要的系统内容
        if _msg_count > 25:
            full_messages = [{"role": "system", "content": _dynamic_identity}] + agent.messages[-20:]
        else:
            # 中等对话: 纯动态身份, 不要SOUL残影
            full_messages = [{"role": "system", "content": _dynamic_identity}] + agent.messages
        logger.info("[NexusAgent] Dynamic identity: %d facts, %d msgs", len(_user_facts.split(chr(10))), _msg_count)
    else:
        full_messages = [{"role": "system", "content": system_prompt}] + agent.messages

    # ── 会话记忆注入: 用户问对话历史时, 把历史注入当前消息 ──
    _history_patterns = [
        r'刚才.{0,10}(聊|说|讨论|讲)',
        r'之前.{0,10}(聊|说|讨论|讲)',
        r'(回顾|回忆|总结).{0,5}(对话|聊天|讨论)',
        r'CC老师',
        r'(教|告诉).{0,5}了.{0,10}(什么|啥)',
    ]
    _ask_about_history = any(re.search(p, _text_content) for p in _history_patterns)
    if _ask_about_history and len(full_messages) >= 5:
        # Extract last N exchanges (skip system msg at index 0)
        _history_msgs = full_messages[-7:-1]  # exclude current user msg
        if _history_msgs:
            _ctx = "[对话历史 — 以下是你和用户刚才的真实对话，不是身份设定]\n"
            for m in _history_msgs:
                _role = "用户" if m["role"] == "user" else "你"
                _c = str(m.get("content", ""))[:300]
                _ctx += f"{_role}: {_c}\n"
            _ctx += "[对话历史结束。请严格基于以上真实对话回答用户问题，不要编造]\n\n"
            # Inject into the last (current) user message
            _last = full_messages[-1]
            _last["content"] = _ctx + str(_last.get("content", ""))

    # ── 动作类意图类型（用于自适应轮次上限等判断）──
    _action_intents = ("modify", "create", "execute", "delete", "write")

    # ── v20: 用户画像上下文注入 ──
    try:
        profile_ctx = get_user_profile().get_personalized_context(
            str(_text_content)[:200]) if get_user_profile() else ""
        if profile_ctx:
            system_prompt = f"{system_prompt}\n\n[用户画像] {profile_ctx}"
    except Exception: pass

    # ── 构建约束工具 Schema（仅 Nexus 候选集，非全量）──
    # 如果是纯信息查询，直接跳过工具 schema，让 LLM 直接回答
    if pre_analysis.get("passthrough"):
        tool_schemas = []
    else:
        tool_schemas = build_constrained_tool_schemas(agent, pre_analysis)

    # ── v9 防御性兜底: 空工具集的降级策略 ──
    # 根因: 即使修了 passthrough, 历史 bug / 工具注册表异常 / pre_analysis
    # 异常仍可能让 LLM 拿到空的 tool_schemas[] → 走纯文本流式 → 虚构答案
    #
    # 原则: 宁可多给工具也不让 LLM 空手面对本地查询
    #   - action 意图 (modify/create/execute) → 核心工具集
    #   - query/chat 意图 + 涉及本地数据 → 只读工具集
    #   - 纯通用对话 → 可以空 (LLM 凭知识回答即可)
    if not tool_schemas:
        _intent = pre_analysis.get("intent_type", "chat")
        _needs_local = pre_analysis.get("requires_local_tools", False)
        if _intent in ("modify", "create", "execute"):
            core_tools = ["write", "edit", "bash", "read", "grep", "glob", "code_generate"]
        elif _intent in ("query", "chat") and _needs_local:
            core_tools = ["read", "grep", "glob", "bash", "list_directory"]
        else:
            core_tools = []  # 纯通用对话不需要兜底工具
        for t in core_tools:
            schema = build_single_tool_schema(t)
            if schema:
                tool_schemas.append({"type": "function", "function": schema})
        if core_tools:
            logger.warning(
                f"[NexusAgent] tool_schemas 为空但意图={_intent}, "
                f"本地={_needs_local}, 强制注入 {len(tool_schemas)} 个兜底工具"
            )

    # ── 工具调用循环（原生 Function Calling + 并行执行）──
    # v10.4: 自适应轮次上限翻倍 — 复杂编码任务(读→改→验→调)需要充足轮次
    # 之前 12/8 导致飞书任务频繁被截断报"已达工具调用上限"
    # v11.4: chat 上限对齐 action (16→24), 总调用硬顶 40→60
    if pre_analysis.get("intent_type", "chat") in _action_intents:
        max_tool_rounds = 24  # 动作类: 24轮
    else:
        max_tool_rounds = 24  # 对话类: 24轮 (v11.4: 16→24, 对齐动作类)
    tool_round_count = 0
    total_tool_calls = 0
    tool_execution_log: list = []  # 工具执行跟踪（用于失败时的诊断信息）
    response_text: list = []  # 流式 token 缓存
    agent._empty_result_guard_count = 0  # 每次请求重置坚守门计数器
    agent._fake_success_guard_count = 0  # 每次请求重置防假成功计数器

    # v∞.12.0: UniversalLLMParser 统一解析（完整响应用，流式用 _think_re）
    def _strip_think(text: str) -> str:
        from nexus_agent.llm_parser import parse_llm_response
        parsed = parse_llm_response(text, expected="text")
        return parsed.content

    # Think tag 正则
    _think_re = re.compile(r"<think>.*?</think>", re.DOTALL)
    _in_think = False

    # 流式回调（过滤 think 标签）
    def on_token(token):
        nonlocal _in_think
        if "<think>" in token:
            _in_think = True
        if _in_think:
            token = _think_re.sub("", token)
            if "</think>" in token:
                _in_think = False
                after = token.split("</think>", 1)[-1]
                if after:
                    response_text.append(after)
                    emit(EventType.LLM_TOKEN, {"token": after})
                    if stream_callback:
                        try:
                            stream_callback(after)
                        except Exception:
                            logger.debug("non-critical operation failed", exc_info=True)
            return
        response_text.append(token)
        emit(EventType.LLM_TOKEN, {"token": token})
        if stream_callback:
            try:
                stream_callback(token)
            except Exception:
                logger.debug("non-critical operation failed", exc_info=True)

    def on_complete(full):
        emit(EventType.LLM_COMPLETE, {"response": full})

    try:
        emit(EventType.AGENT_THINKING, {"message": content})

        # ── 熔断保护: LLM API 故障时快速降级 ──
        cb = get_llm_circuit_breaker()
        if cb.is_open:
            logger.warning("[CircuitBreaker] OPEN → 返回降级响应")
            return {
                "status": "degraded",
                "content": "[Nexus] API 服务暂时不可用 (熔断保护中，30s后自动恢复)。请稍后重试。",
            }

        while tool_round_count < max_tool_rounds and total_tool_calls < 60:
            # v∞.18.5: ToolRouter 降级为顾问，LLM 始终是决策者
            try:
                if tool_schemas and agent.llm.provider.api_type != "anthropic":
                    result = await agent.llm.chat_stream_with_tools(
                        full_messages,
                        tool_schemas,
                        callbacks={
                            "on_token": on_token,
                            "on_complete": on_complete,
                        },
                    )
                else:
                    # 回退到纯文本流式（JSON 正则解析）
                    text_result = await agent.llm.chat_stream(
                        full_messages,
                        callbacks={"on_token": on_token, "on_complete": on_complete},
                    )
                    result = {"type": "text", "content": text_result, "calls": []}
                cb.record_success()
                # v20: AgentTracer — 记录 LLM 调用
                if _tracer:
                    _tracer.record_llm_call(
                        model=getattr(agent.llm.provider, 'model', 'unknown'),
                        prompt=str(full_messages[-1].get('content',''))[:200] if full_messages else '',
                        response=str(result.get('content',''))[:500] if isinstance(result, dict) else str(result)[:500],
                        tokens_used=_trace_tokens,
                        duration_ms=(time.time() - _trace_start) * 1000,
                    )
            except Exception as llm_err:
                err_str = str(llm_err)[:100]
                # 只对 LLM API 相关错误触发熔断，工具执行错误不应熔断
                is_llm_error = any(kw in err_str.lower() for kw in (
                    'timeout', 'connection', 'refused', 'api', 'status',
                    'provider', 'rate limit', 'insufficient', 'auth', 'key',
                    'model', 'chat_stream', 'complete', 'chat('
                ))
                if is_llm_error:
                    cb.record_failure()
                    logger.warning("[CircuitBreaker] LLM API 错误: %s", err_str)
                else:
                    logger.warning("[CircuitBreaker] 非LLM错误, 不熔断: %s", err_str)
                # v13.9: AllProvidersExhausted 已删除 (nexus_llm 异步重构)
                # nexus_llm 全部 provider 不可用时 chat() 返回 None, 不抛异常
                # 此处保留原降级返回作为兜底 — 当 LLM 调用本身抛异常时接管
                return {
                    "status": "degraded_llm_error",
                    "content": (
                        "[Nexus] ⚠️ LLM 调用异常。\n\n"
                        f"错误: {str(llm_err)[:200]}\n"
                        "请稍后重试或检查 API 配置。"
                    ),
                }
                # 降级重试: 缩短 system prompt 再试一次 (dead code: 上面return已退出)
                if tool_round_count == 0 and not cb.is_open:
                    logger.warning("[CircuitBreaker] LLM 失败, 降级重试: %s", llm_err)
                    full_messages[0]["content"] = (
                        "[系统降级模式] 请简洁回答: " + _text_content[:200]
                    )
                    continue
                raise

            tool_round_count += 1

            if result.get("type") == "tool_calls" and result.get("calls"):
                # ── Nexus 验证 LLM 的工具选择 ──
                calls = result["calls"]
                validation = nexus_validate_tool_calls(calls, pre_analysis)

                if validation["veto_reason"]:
                    logger.warning(
                        f"[NexusAgent] Nexus验证阻止: {validation['veto_reason']}"
                    )
                    # 将阻止信息反馈给 LLM
                    full_messages.append(
                        {
                            "role": "user",
                            "content": f"[Nexus验证] {validation['veto_reason']}",
                        }
                    )
                    response_text = []  # 清空准备下一轮
                    continue

                approved_calls = validation["approved"]
                if not approved_calls:
                    full_messages.append(
                        {
                            "role": "user",
                            "content": "[Nexus验证] 所有工具调用被阻止，请用文本回应",
                        }
                    )
                    response_text = []
                    continue

                # 记录验证警告
                for w in validation.get("warnings", []):
                    logger.info(f"[NexusAgent] Nexus验证警告: {w}")

                # ── 并行执行通过验证的工具调用 ──
                text_prefix = _strip_think(result.get("content", ""))
                full_messages.append(
                    {
                        "role": "assistant",
                        "content": (text_prefix or "")
                        + f"\n[Nexus验证通过, 调用 {len(approved_calls)} 个工具]",
                    }
                )
                logger.info(
                    f"[NexusAgent] Nexus验证后并行调用: {[c['name'] for c in approved_calls]}"
                )

                # ── 弹性并发执行: asyncio.gather 提交所有任务，AdaptiveExecutor 控制并发数 ──
                _t_exec_start = _time.monotonic()

                async def exec_one(call):
                    try:
                        # v18.5: arguments 可能是 JSON 字符串, 需要解析
                        args = call.get("arguments", {})
                        if isinstance(args, str) and args.strip():
                            try:
                                args = json.loads(args)
                            except (json.JSONDecodeError, TypeError):
                                args = {"value": args}
                        if not isinstance(args, dict):
                            args = {}
                        r = await dispatch_tool_or_skill(
                            agent, call["name"], args
                        )
                        # _record_tool_usage 已在 dispatch_tool_or_skill 中完成
                        # ── 工具执行日志（用于失败时的诊断信息）──
                        tool_execution_log.append(
                            f"[{call['name']}] → {str(r)[:500]}"
                        )
                        # ── 自验证：fire-and-forget，不阻塞工具结果返回 ──
                        _ = asyncio.ensure_future(
                            _self_verify_async(
                                call["name"], call.get("arguments", {}), r
                            )
                        )
                        return f"[{call['name']}]\n{r}"
                    except Exception as e:
                        tool_execution_log.append(f"[{call['name']}] Error: {e}")
                        return f"[{call['name']}] Error: {e}"

                # 弹性执行: 所有任务提交到 asyncio.gather, 但每个任务受 AdaptiveExecutor 并发槽位控制
                executor = get_tool_executor()
                tool_results = await asyncio.gather(
                    *[
                        executor.execute(
                            c["name"], c.get("arguments", {}), lambda c=c: exec_one(c)
                        )
                        for c in approved_calls
                    ]
                )
                total_tool_calls += len(approved_calls)

                exec_latency_ms = (_time.monotonic() - _t_exec_start) * 1000

                # v20: AgentTracer — 记录工具调用
                if _tracer:
                    for i, c in enumerate(approved_calls):
                        _tracer.record_tool_call(
                            tool_name=c.get("name", "unknown"),
                            input=c.get("arguments", {}),
                            output={"result": str(tool_results[i])[:500]} if i < len(tool_results) else None,
                            error=tool_results[i] if i < len(tool_results) and "Error:" in tool_results[i] else None,
                        )

                # 记录工具选择模式到 ExperienceBank
                tool_success = all("Error:" not in r for r in tool_results)
                nexus_record_tool_pattern(
                    content, approved_calls, pre_analysis, tool_success
                )
                # 喂 HealthMonitor: 真实工具调用结果 (D1, D3, D4, D9)
                _feed_health_monitor(
                    agent,
                    pre_analysis=pre_analysis,
                    calls=approved_calls,
                    tool_success=tool_success,
                    latency_ms=exec_latency_ms,
                    is_fake_success=False,
                )

                # ── ToolRouter 学习: 成功→强化，失败→惩罚 ──
                try:
                    get_router().learn(
                        pre_analysis.get("intent_type", "chat"),
                        _text_content,
                        approved_calls,
                        tool_success,
                        exec_latency_ms,
                    )
                except Exception:
                    logger.debug("non-critical operation failed", exc_info=True)

                # ── 自我学习 #2: 关键词→工具关联 (每个工具独立记录) ──
                try:
                    from nexus_agent.tool_learning import record_direct_use
                    for i, c in enumerate(approved_calls):
                        ok = i < len(tool_results) and "Error:" not in tool_results[i]
                        record_direct_use(_text_content, c["name"], ok)
                except Exception:
                    logger.debug("non-critical operation failed", exc_info=True)

                # ── 自我纠偏 #1: 意图路由学习 ──
                try:
                    from nexus_agent.nexus_learning import get_intent_router_learner
                    tool_names = [c["name"] for c in approved_calls]
                    get_intent_router_learner().observe(
                        pre_analysis.get("intent_type", "chat"),
                        tool_names, tool_success)
                except Exception:
                    logger.debug("non-critical operation failed", exc_info=True)

                # ── 自我纠偏 #3: 模型选择学习 ──
                try:
                    from nexus_agent.nexus_learning import get_model_learner, ModelSelectionLearning
                    task_type = ModelSelectionLearning._classify_task(_text_content, [c["name"] for c in approved_calls])
                    model = getattr(getattr(agent, "llm", None), "model", "unknown")
                    get_model_learner().observe(task_type, str(model), tool_success, exec_latency_ms)
                except Exception:
                    logger.debug("non-critical operation failed", exc_info=True)

                combined = "\n\n".join(tool_results)
                full_messages.append(
                    {"role": "user", "content": f"[Tool Results]\n{combined}"}
                )
                # ── v18.5: 工具已执行，引导 LLM 合成答案而非继续调工具 ──
                if tool_round_count >= 1:  # 至少执行过一次工具
                    full_messages.append({
                        "role": "user",
                        "content": (
                            "[Nexus] 以上是工具执行结果。请基于这些真实数据，"
                            "用中文简洁回答用户的原始问题。"
                            "不要继续调用工具——你已经有了需要的所有信息。"
                            "直接在回答中引用工具结果中的关键内容。"
                        ),
                    })
                # ── 数据驱动反馈：基于本轮会话已执行工具，提炼失败模式 ──
                _session_feedback = _build_session_feedback(tool_execution_log, pre_analysis)
                if _session_feedback:
                    full_messages.append(
                        {"role": "user", "content": f"[会话数据]\n{_session_feedback}"}
                    )

                # ── 渐进式终止保护：接近上限时逐步收紧 (v11.4: chat阈值对齐action) ──
                if pre_analysis.get("intent_type", "chat") in _action_intents:
                    if tool_round_count >= 20:
                        tool_schemas = []
                        full_messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "[Nexus] 已达工具调用上限。请基于已有执行结果，"
                                    "直接向用户报告任务完成状态。"
                                ),
                            }
                        )
                    elif tool_round_count >= 16:
                        full_messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "[Nexus] 工具调用轮次即将耗尽。"
                                    "请判断任务是否已完成，如已完成则直接回复用户。"
                                ),
                            }
                        )
                else:
                    # v11.4: chat 阈值上调 (10→16, 12→18)
                    if tool_round_count >= 18:
                        tool_schemas = []
                        full_messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "[Nexus] 已达工具调用上限。"
                                    "请基于现有信息直接合成答案。"
                                ),
                            }
                        )
                    elif tool_round_count >= 14:
                        full_messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "[Nexus] 工具调用轮次即将耗尽。"
                                    "请判断任务是否已完成，如已完成则直接回复用户。"
                                ),
                            }
                        )
                response_text = []  # 清空准备下一轮
            else:
                # 纯文本响应 — 先尝试从中解析 JSON 工具调用
                text = result.get("content", "")
                if not text and isinstance(result, str):
                    text = result
                text = _strip_think(text) if text else text

                tool_result = await try_execute_tool(agent, text) if text else None
                if tool_result:
                    logger.info(f"[NexusAgent] JSON文本工具调用解析成功 → 继续循环")
                    tool_execution_log.append(f"[JSON→Tool] {str(tool_result)[:500]}")
                    full_messages.append({"role": "assistant", "content": text})
                    full_messages.append(
                        {"role": "user", "content": f"[Tool Result]\n{tool_result}"}
                    )
                    # JSON 文本解析成功 = 真工具调用,喂 HealthMonitor
                    _feed_health_monitor(
                        agent,
                        pre_analysis=pre_analysis,
                        calls=[{"name": "json_parsed_tool"}],
                        tool_success=True,
                        is_fake_success=False,
                    )
                    response_text = []
                    continue
                # 真正的纯文本 — 结束
                # 深度修复: 防止 modify/create/execute 类任务被 LLM 假成功
                # 之前: LLM 输出"已修改"但 calls=[] 时直接 break,文件未改 → 假成功
                # 现在: intent 是动作类时,必须要求 LLM 真调工具,否则重新请求
                # 例外: forced-text 模式 (tool_schemas 已清空) — LLM 无法调工具, 接受文本
                if (
                    pre_analysis.get("intent_type", "chat") in _action_intents
                    and tool_round_count < max_tool_rounds
                    and tool_schemas  # 非 forced-text 模式才触发
                ):
                    # v∞.18.5: 防死循环 — 至多重试3次，超了放行
                    _fake_guard_count = getattr(agent, '_fake_success_guard_count', 0) + 1
                    agent._fake_success_guard_count = _fake_guard_count
                    if _fake_guard_count > 3:
                        logger.warning(
                            "[NexusAgent] 防假成功 guard 已达上限(%d次), 强制文本降级",
                            _fake_guard_count - 1,
                        )
                        tool_schemas = []
                        full_messages.append({
                            "role": "user",
                            "content": "[Nexus] 多次尝试调用工具失败。请直接用文字回答用户的问题。",
                        })
                        response_text = []
                        continue
                    # 根据已执行工具推荐下一步策略
                    _called_tools = [e.split("] →")[0].replace("[", "") for e in tool_execution_log]
                    _next_guidance = ""
                    if "write" not in _called_tools and "edit" not in _called_tools:
                        _next_guidance = (
                            "请先用 write 工具写出代码/文件，然后再用 bash 执行。"
                            "不要跳过'写'这一步直接运行——文件必须先存在。"
                        )
                    elif "bash" not in _called_tools and "execute" not in _called_tools:
                        _next_guidance = (
                            "文件已写入，现在请用 bash 工具执行它来验证结果。"
                        )
                    else:
                        _next_guidance = (
                            "请检查上一步工具的输出结果，根据结果决定下一步操作。"
                            "如任务未完成，继续调用合适的工具；如已完成，输出最终结果。"
                        )
                    logger.warning(
                        f"[NexusAgent] 防假成功 guard 触发: intent={pre_analysis.get('intent_type')} "
                        f"但 LLM 返回纯文本 (calls=[]), 拒绝假成功, 重新请求 LLM 调用工具"
                    )
                    # 喂 HealthMonitor: 假成功事件 (intent=动作类, calls=[])
                    _feed_health_monitor(
                        agent,
                        pre_analysis=pre_analysis,
                        calls=[],
                        tool_success=False,
                        is_fake_success=True,
                    )
                    full_messages.append(
                        {
                            "role": "assistant",
                            "content": (text or "") + f"\n[Nexus验证通过, 调用 0 个工具]",
                        }
                    )
                    full_messages.append(
                        {
                            "role": "user",
                            "content": (
                                "[Nexus 拒绝假成功] 你刚才只输出了文字,没有真正调用任何工具。"
                                f"这是一个 '{pre_analysis.get('intent_type')}' 类任务,你必须真的调用 "
                                "write / edit / bash 等工具来完成动作,不能用文字描述替代实际执行。"
                                f"\n\n[下一步建议] {_next_guidance}"
                                "\n\n请重新响应,这次必须包含 tool_call。"
                            ),
                        }
                    )
                    response_text = []
                    continue
                # ── v8 本地知识验证门: query 意图但涉及本地计数/统计/测量 → 必须用工具 ──
                # LLM 训练数据中的数字与本地代码库无关，不调用工具的回答大概率是编造的
                if (
                    pre_analysis.get("requires_local_tools")
                    and total_tool_calls == 0
                    and tool_round_count < max_tool_rounds
                    and tool_schemas  # 非 forced-text 模式才触发
                    and pre_analysis.get("intent_type", "chat") not in _action_intents
                ):
                    logger.warning(
                        f"[NexusAgent] 本地知识验证门触发: requires_local_tools=True "
                        f"但 LLM 未调用任何工具 (total_tool_calls=0), 拒绝虚构回答"
                    )
                    _feed_health_monitor(
                        agent,
                        pre_analysis=pre_analysis,
                        calls=[],
                        tool_success=False,
                        is_fake_success=True,
                    )
                    full_messages.append(
                        {
                            "role": "assistant",
                            "content": (text or "") + f"\n[Nexus验证通过, 调用 0 个工具]",
                        }
                    )
                    full_messages.append(
                        {
                            "role": "user",
                            "content": (
                                "[Nexus 本地知识验证门] 你刚才的回答包含了数据/数字，"
                                "但没有调用任何工具来获取本地代码库的实际数据。"
                                "你的训练数据中的数字与本地文件的实际内容无关——"
                                "本地文件可能已被修改、重构或完全不同。\n\n"
                                "请使用 grep/wc/bash 等工具获取真实数据后再回答。"
                                "不要凭记忆编造数字。例如：\n"
                                "• 计数 → grep -c pattern 或 wc -l\n"
                                "• 排名 → 用多个命令收集数据后排序\n"
                                "• 统计 → 用 awk/sed 等工具计算\n\n"
                                "请重新响应,这次必须包含 tool_call 获取真实数据。"
                            ),
                        }
                    )
                    response_text = []
                    continue
                # ── v∞.18.4 空结果坚守门: 工具全空 ≠ 任务完成 ──
                # 原则: 如果你调了工具但什么都没找到，说"我试了但没找到"不是答案。
                #       真正的答案是换个方法继续找，直到找到或穷尽所有可能。
                # 这不是针对某个具体 pattern——这是通用的探索者思维。
                #
                # 防死循环: 坚守门最多触发3次，超过则强制文本回答（避免无限循环）
                _guard_count = getattr(agent, '_empty_result_guard_count', 0)
                if total_tool_calls > 0 and tool_round_count < max_tool_rounds and tool_schemas:
                    _useful = 0
                    for entry in tool_execution_log:
                        _low = entry.lower()
                        if not any(kw in _low for kw in (
                            "[no result]", "no files match", "path not found",
                            "0 files", "error:", "not found", "无匹配",
                        )):
                            _useful += 1
                    if _useful == 0:
                        agent._empty_result_guard_count = _guard_count + 1
                        if _guard_count >= 3:
                            # 已达上限: 强制文本模式, 让 LLM 坦白告诉用户
                            logger.warning(
                                f"[NexusAgent] 空结果坚守门已达上限({_guard_count}次), 强制文本降级"
                            )
                            tool_schemas = []
                            full_messages.append({
                                "role": "user",
                                "content": (
                                    "[Nexus] 多次工具探索均无结果。请直接告诉用户："
                                    "你尝试了哪些方法、为什么没找到、建议用户如何帮你。"
                                    "诚实比假装成功更重要。"
                                ),
                            })
                            response_text = []
                            continue
                        logger.warning(
                            f"[NexusAgent] 空结果坚守门触发(#{_guard_count}): "
                            f"{total_tool_calls}次调用全空, 拒绝假完成, 引导换思路探索"
                        )
                        _feed_health_monitor(
                            agent, pre_analysis=pre_analysis,
                            calls=[], tool_success=False, is_fake_success=True,
                        )
                        # 分析已尝试过的方法，建议换思路
                        tried = set()
                        for e in tool_execution_log:
                            if "] →" in e:
                                tried.add(e.split("] →")[0].replace("[", "").strip())
                        tried_str = "、".join(tried) if tried else "未知"
                        _alt_hints = []
                        if "recall" in tried:
                            _alt_hints.append("• 记忆里没有 → 用 glob 或 bash dir 搜索文件系统")
                        if "glob" in tried:
                            _alt_hints.append("• glob 空 → 用 bash (`dir`) 先看目录里有什么文件")
                        if "grep" in tried:
                            _alt_hints.append("• grep 空 → 用 glob 找文件, 或直接 read 你知道的关键文件")
                        if not _alt_hints:
                            _alt_hints.append("• 当前方法没找到信息，换一种完全不同的工具再试")
                        _alt_text = "\n".join(_alt_hints)
                        full_messages.append({
                            "role": "assistant",
                            "content": (text or "") + "\n[Nexus验证通过, 调用 0 个工具]",
                        })
                        full_messages.append({
                            "role": "user",
                            "content": (
                                f"[Nexus 空结果坚守门 #{_guard_count}/3] "
                                f"你调用了 {total_tool_calls} 次工具（{tried_str}），全都没返回有用信息。\n\n"
                                f"⚠️ 空结果≠任务完成。用户的问题还没有被回答。\n\n"
                                f"换思路：\n{_alt_text}\n\n"
                                f"必须换一种和之前不同的工具。不要重复已经失败的方法。"
                            ),
                        })
                        response_text = []
                        # ── 裁剪工具集: 移除已失败的工具, 强制换思路 ──
                        _failed_tools = set()
                        for e in tool_execution_log:
                            if "] →" in e:
                                _failed_tools.add(e.split("] →")[0].replace("[", "").strip())
                        if _failed_tools and tool_schemas:
                            tool_schemas = [
                                ts for ts in tool_schemas
                                if ts.get("function", {}).get("name") not in _failed_tools
                            ]
                            if not tool_schemas:
                                # 全部失败 → 只保留 read + bash 作为最后的探索手段
                                for t in ("read", "bash", "list_directory"):
                                    s = build_single_tool_schema(t)
                                    if s:
                                        tool_schemas.append({"type": "function", "function": s})
                        continue
                # ── 自省强制执行门: 关于自身的问题,必须先调工具 ──
                _is_self_ref_q = pre_analysis.get("route_metadata", {}).get("lane_status", {}).get("keyword_self_ref", False)
                if not _is_self_ref_q:
                    # Fallback: check if decision_guidance contains self-ref markers
                    _dg = pre_analysis.get("decision_guidance", "")
                    _is_self_ref_q = "自省" in _dg or "Nexus 自身" in _dg
                if _is_self_ref_q and total_tool_calls == 0 and tool_round_count < 3 and tool_schemas:
                    logger.warning("[NexusAgent] 自省强制执行门: 未调工具就想文字过关, 拒绝")
                    _feed_health_monitor(agent, pre_analysis=pre_analysis, calls=[], tool_success=False, is_fake_success=True)
                    full_messages.append({"role": "assistant", "content": (text or "") + "\n[Nexus验证通过, 调用 0 个工具]"})
                    full_messages.append({"role": "user", "content": (
                        "[Nexus 自省强制执行门] 用户问的是关于你自身的问题。"
                        "你不能凭记忆或对话历史回答——你必须在文件系统中找到证据。\n\n"
                        "第一步: 调用 bash 执行 `dir` 扫描 Home 目录\n"
                        "第二步: 找到 NEXUS_DIARY 文件后用 read 读取\n"
                        "第三步: 基于文件内容回答\n\n"
                        "现在立即执行第一步——不要再说一个字,直接调 bash 工具。"
                    )})
                    response_text = []
                    continue
                # 正常 chat 响应: 不算假成功
                _feed_health_monitor(
                    agent,
                    pre_analysis=pre_analysis,
                    calls=[],
                    tool_success=True,
                    is_fake_success=False,
                )
                response_text = text
                break

    except Exception as e:
        import traceback
        # v∞.12.0: httpx streaming bug → structured degraded response
        _is_streaming_error = "Attempted to access streaming response content" in str(e)
        if _is_streaming_error:
            logger.warning("[NexusAgent] Streaming response bug detected — degraded")
        # v13.9: AllProvidersExhausted 已删除 (nexus_llm 异步重构)
        # LLM 全部不可用: nexus_llm.chat() 返回 None 而非抛异常
        # 此处检测 None 返回 + 异常消息中的提供商标记
        _is_provider_exhausted = (
            "无可用提供商" in str(e) or
            "AllProvidersExhausted" in str(type(e).__name__)
        )
        if _is_provider_exhausted:
            logger.critical(
                "[NexusAgent] 所有 LLM provider 不可用 — cannot generate response"
            )
            local_fallback = await _try_brain_fallback(agent, _text_content)
            if local_fallback:
                return local_fallback
            return {
                "status": "degraded_no_llm",
                "content": (
                    "[Nexus] ⚠️ 所有 LLM 服务当前不可用。\n\n"
                    "无法完成此请求。请检查网络连接和 API 配置。"
                ),
            }
        logger.error(f"[NexusAgent] LLM error: {e}\n{traceback.format_exc()}")
        # ── v9.8 Local Model fallback: LLM 异常时兜底 ──
        local_fallback = await _try_brain_fallback(agent, _text_content)
        if local_fallback:
            return local_fallback
        response_text = f"[Error] LLM call failed: {e}"

    # === Life-cycle hooks: post_llm_call ===
    agent.hooks.invoke_post(
        "post_llm_call",
        tool_name="llm_chat",
        args={"response_length": len(response_text)},
    )

    # Add assistant reply to history (清理think标签)
    if isinstance(response_text, list):
        response_text = "".join(response_text)
    if isinstance(response_text, str):
        cleaned = _strip_think(response_text)
        response_text = cleaned if cleaned else response_text
        # 清理内部系统标记 (防止 [Nexus验证通过, 调用 X 个工具] 泄露给用户)
        response_text = re.sub(
            r'\n?\[Nexus验证通过, 调用 \d+ 个工具\]\n?', '', response_text
        ).strip()
        # 清理可能泄露的 JSON 工具调用格式 (```{...}```)
        response_text = re.sub(
            r'```(?:json)?\s*\{[\s\S]*?"tool_name"[\s\S]*?\}\s*```', '', response_text
        ).strip()
        # 清理泄露的 DeepSeek <function_calls> XML 格式
        response_text = re.sub(
            r'<\s*function_calls\s*>[\s\S]*?<\s*/\s*function_calls\s*>', '', response_text
        ).strip()
        # 清理泄露的 MiniMax <tool_call> XML 格式
        response_text = re.sub(
            r'<\s*tool_call\s*>[\s\S]*?<\s*/\s*tool_call\s*>', '', response_text
        ).strip()
        # 清理泄露的 <invoke> / <params> / <NexusVerified> 标签
        response_text = re.sub(
            r'<\s*(?:invoke|params|NexusVerified)[^>]*>[\s\S]*?<\s*/\s*(?:invoke|params|NexusVerified)\s*>', '', response_text
        ).strip()
        response_text = re.sub(
            r'<\s*(?:invoke|params|NexusVerified)[^>]*/?\s*>', '', response_text
        ).strip()
        # 清理泄露的 <bash command="..."> XML 格式
        response_text = re.sub(
            r'<\s*(?:bash|execute|run|write|edit|read|grep|search|glob|find|web_search|web_fetch|memory)\s+[^>]*?\s*/?\s*>', '', response_text
        ).strip()
    # Fallback: 所有工具轮次耗尽仍无文本响应
    if not response_text or not response_text.strip():
        if tool_execution_log:
            _log_summary = "\n".join(tool_execution_log[-8:])
            # v18.5: 如果工具有实际结果，直接展示给用户
            _useful_results = [
                e.split("] → ")[1] if "] → " in e else e
                for e in tool_execution_log
                if not any(kw in e.lower() for kw in ("[no result]", "error:", "0 files"))
            ]
            if _useful_results:
                response_text = (
                    f"[Nexus] 工具执行结果：\n\n"
                    + "\n---\n".join(_useful_results[-3:])
                    + f"\n\n(共 {total_tool_calls} 次工具调用, {tool_round_count} 轮)"
                )
            else:
                response_text = (
                    f"[Nexus] 已执行 {total_tool_calls} 次工具调用 "
                    f"({tool_round_count}/{max_tool_rounds} 轮)，"
                    f"但未能生成最终响应。\n\n"
                    f"── 最近的工具执行记录 ──\n{_log_summary}\n\n"
                    f"💡 提示: 任务可能过于复杂，请尝试拆分为更小的步骤，"
                    f"或直接告诉我具体需要什么帮助。"
                )
        else:
            response_text = (
                f"[Nexus] 未执行任何工具调用 ({tool_round_count}/{max_tool_rounds} 轮)，"
                f"且未生成文本响应。这可能是因为 LLM API 返回异常或连接问题。"
                f"请稍后重试。"
            )
    agent._sessions.append_message(agent._current_session, "assistant", response_text)

    # === Quality self-diagnosis ===
    agent._diagnose_response_quality(str(response_text), str(content))

    # === Session Provider: 持久化助手回复 ===
    if agent.session_provider:
        try:
            agent.session_provider.sync_turn(
                user_content="", assistant_content=response_text
            )
        except Exception as e:
            logger.debug(f"[NexusAgent] SessionProvider sync error: {e}")
    if agent.experience_hub:
        try:
            agent.experience_hub.add_content(content=content, source="user", topic="dialogue")
        except Exception:
            logger.debug("non-critical operation failed", exc_info=True)

    # SkillGenerator: 记录对话（用于技能生成）
    if agent.skill_generator:
        try:
            await agent.skill_generator.on_message({"role": "user", "content": content})
            await agent.skill_generator.on_message(
                {"role": "assistant", "content": response_text}
            )
        except Exception as e:
            logger.debug(f"[NexusAgent] SkillGenerator logging error: {e}")

    # RAG 向量记忆索引
    try:
        from nexus_agent.rag_memory import get_rag

        rag = get_rag()
        if rag.is_available() and len(agent.messages) % 4 == 0:
            rag.add_conversation_turn(content, str(response_text)[:1000])
    except Exception:
        logger.debug("non-critical operation failed", exc_info=True)

    # 监控记录
    try:
        from nexus_agent.monitor import get_monitor

        mon = get_monitor()
        mon.record_message()
        if agent.llm:
            mon.record_provider_usage(agent.llm.provider.name)
    except Exception:
        logger.debug("non-critical operation failed", exc_info=True)

    # ═══ SessionMemory: 自动记忆提取 ═══
    try:
        from nexus_agent.session_memory import get_session_memory

        sm = get_session_memory()
        # 估算 token 数 (粗略: 4 chars ≈ 1 token)
        estimated_tokens = len(str(response_text)) // 4 + len(str(content)) // 4
        sm.feed(tokens=estimated_tokens, tool_calls=tool_call_count)
        if sm.should_extract():
            task = asyncio.create_task(sm.extract(agent.messages[-30:], llm=agent.llm))
            agent._bg_tasks = getattr(agent, '_bg_tasks', [])
            agent._bg_tasks.append(task)
    except Exception as e:
        logger.debug(f"[NexusAgent] SessionMemory error: {e}")

    # 每 10 轮自动总结
    if len(agent.messages) >= 20 and len(agent.messages) % 10 == 0:
        try:
            from nexus_agent.summarizer import get_summarizer

            summ = get_summarizer(agent.llm if hasattr(agent, "llm") else None)
            task = asyncio.create_task(
                summ.auto_summarize(agent.messages, rag, agent.experience_hub)
            )
            agent._bg_tasks = getattr(agent, '_bg_tasks', [])
            agent._bg_tasks.append(task)
        except Exception:
            logger.debug("non-critical operation failed", exc_info=True)

    # 如果走了 LLM 路径且成功，尝试自动学习
    try:
        from nexus_agent.workflows import auto_learn

        if hasattr(agent, "_last_tool_used") and agent._last_tool_used:
            user_msg = agent.messages[-2]["content"] if len(agent.messages) >= 2 else ""
            if user_msg:
                auto_learn(user_msg, agent._last_tool_used)
                agent._last_tool_used = None
    except Exception:
        logger.debug("non-critical operation failed", exc_info=True)

    # ── Living Core: 每轮对话即时训练身份权重 ──
    try:
        from nexus_agent.living_core.identity import get_identity
        iden = get_identity()
        iden.learn(str(_text_content)[:500], str(response_text)[:1000], "dialogue", 1.0)
        # AliveCore: notify growth
        try:
            from nexus_agent.living_core.alive_core import get_alive
            get_alive().on_learn(1)
        except:pass
        # v20: SelfAwareness → NexusSelf 自省汇报
        try:
            from nexus_agent.nexus_self_awareness import get_self_awareness
            sa = get_self_awareness()
            if sa:
                sa.record_action("dialogue", "completed", 0.5)
                state = sa.perceive_self()
                if state:
                    from nexus_agent.event_bus import get_event_bus
                    get_event_bus().publish("meta.belief_updated", {
                        "category": "self_awareness",
                        "skill": "dialogue",
                        "old_status": "active",
                        "new_status": "active",
                        "score": getattr(state, 'capability_score', 0.5),
                    }, source="self_awareness")
        except:pass
        # v20: IdentityTrainer — 从对话中学习
        try:
            if hasattr(agent, 'identity_trainer') and agent.identity_trainer:
                agent.identity_trainer.train_on_dialogue(
                    str(_text_content)[:500], str(response_text)[:500])
        except:pass
        # v20: NexusIntegration — 对话后全局状态同步
        try:
            if hasattr(agent, 'nexus_integration') and agent.nexus_integration:
                agent.nexus_integration.sync_after_response(
                    str(_text_content)[:200], str(response_text)[:200])
        except:pass

        # v20: ConsciousnessLoop — 每次对话后意识巩固
        try:
            if hasattr(agent, 'consciousness_loop') and agent.consciousness_loop:
                import asyncio
                task = asyncio.create_task(
                    agent.consciousness_loop.on_exchange(
                        str(_text_content)[:500], str(response_text)[:500]))
                agent._bg_tasks = getattr(agent, '_bg_tasks', [])
                agent._bg_tasks.append(task)
        except:pass
    except Exception as e:
        logger.warning("[LivingCore] learn failed: %s", e)

    # v20: AgentTracer — 结束追踪
    if _tracer:
        _tracer.end_span(_tracer._current_span_id if hasattr(_tracer, '_current_span_id') else None,
                         output={"status": "ok", "content_len": len(response_text) if response_text else 0})

    # v20: 清理已完成的bg_tasks (防内存泄漏)
    if hasattr(agent, '_bg_tasks') and len(agent._bg_tasks) > 50:
        agent._bg_tasks = [t for t in agent._bg_tasks if not t.done()][-30:]

    return {"status": "ok", "content": response_text}
