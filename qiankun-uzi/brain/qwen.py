"""
Qwen3-VL-4B 本地模型 — 省钱引擎
把能甩给本地模型的任务全甩过去，省 Claude token

用法：
  from brain.qwen import ask, analyze_stock, summarize_scan, quick_judge
"""

import json, urllib.request, logging

logger = logging.getLogger("qiankun.brain")
from brain.minimax_client import chat as _mm_chat, vision_describe as _mm_vision

MINIMAX_MODEL = "MiniMax-M3"  # 2026-07-30: 用 mmx CLI, 不用 LMStudio
# 旧的 qwen3-vl-4b


def _call_qwen(prompt: str, max_tokens: int = 300, temperature: float = 0.1) -> str:
    """2026-07-30: 底层用 mmx chat (MiniMax M3). 返回 string (从 list 抽 text)."""
    try:
        result = _mm_chat(
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        # mmx 返回可能是 str 或 list[dict] (text blocks)
        if isinstance(result, str):
            return result.strip()
        if isinstance(result, list):
            parts = []
            for blk in result:
                if isinstance(blk, dict) and blk.get('type') == 'text':
                    parts.append(blk.get('text', ''))
                elif isinstance(blk, str):
                    parts.append(blk)
            return chr(10).join(parts).strip()
        return str(result).strip()
    except Exception as e:
        logger.debug(f"MiniMax call failed: {e}")
        return ""


def is_available() -> bool:
    """检查 MiniMax M3 是否可用 (2026-07-30 切换)."""
    try:
        from brain.minimax_client import _run_mmx  # noqa: F401
        return True
    except Exception:
        return False


# ════════════════════════════════════
# 股票分析（核心省钱入口）
# ════════════════════════════════════

def analyze_stock(code: str, name: str, kline_data: list, realtime: dict) -> dict:
    """综合分析一只股票 — 全部走 Qwen，零 token 消耗"""
    recent = kline_data[-10:] if kline_data else []
    kline_str = "\n".join([
        f"{k['date']} O{k['open']:.2f} H{k['high']:.2f} L{k['low']:.2f} C{k['close']:.2f} V{k['volume']}"
        for k in recent
    ])
    rt = realtime or {}
    rt_str = f"现价{rt.get('price','?')} 涨跌{rt.get('change_pct','?')}%"

    prompt = f"""你是资深A股短线分析师。用50字以内给出研判。

股票：{name}（{code}）
{rt_str}
近10日K线：{kline_str}

回答格式：趋势|建议|一句话理由"""

    analysis = _call_qwen(prompt, max_tokens=200)

    return {
        "code": code, "name": name,
        "trend": _extract_label(analysis, ["上涨", "下跌", "震荡"]),
        "advice": _extract_label(analysis, ["买入", "持有", "卖出"]),
        "analysis": analysis,
    }


def summarize_scan(results: list) -> str:
    """用 Qwen 总结扫描结果 — 省去 Claude 思考和措辞"""
    if not results:
        return "今日无符合条件的超短线标的。"

    top5 = results[:5]
    summary = "\n".join([
        f"{r['code']} {r.get('name','?')} RSI{r.get('rsi','?')} 评分{r.get('score','?')} {r.get('signal','?')}"
        for r in top5
    ])

    prompt = f"""用30字以内总结以下超短线扫描结果：

{summary}

直接给结论，不需要分析过程。"""

    return _call_qwen(prompt, max_tokens=100) or f"发现{len(results)}只候选，Top: {top5[0].get('code','?')}"


def quick_judge(code: str, name: str, price: float, change_pct: float, rsi: float) -> str:
    """快速单只判断 — 一行结论"""
    return _call_qwen(
        f"{name}({code}) 现价{price} {change_pct:+.2f}% RSI{rsi}。超短线能否参与？10字以内。",
        max_tokens=50
    )


# ════════════════════════════════════
# 代码生成（省小 token）
# ════════════════════════════════════

def generate_code(description: str, language: str = "python") -> str:
    """用 Qwen 生成简单代码片段"""
    prompt = f"用{language}写一段代码：{description}。只输出代码，不要解释。"
    return _call_qwen(prompt, max_tokens=500)


# ════════════════════════════════════
# 工具
# ════════════════════════════════════

def _extract_label(text: str, labels: list) -> str:
    for label in labels:
        if label in text:
            return label
    return "未知"


# backward compatibility
ask = _call_qwen
