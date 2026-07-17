"""
Qwen3-VL-4B 本地模型 — 省钱引擎
把能甩给本地模型的任务全甩过去，省 Claude token

用法：
  from brain.qwen import ask, analyze_stock, summarize_scan, quick_judge
"""

import json, urllib.request, logging

logger = logging.getLogger("qiankun.brain")

LM_STUDIO = "http://127.0.0.1:1234/v1"
MODEL = "qwen/qwen3-vl-4b"


def _call_qwen(prompt: str, max_tokens: int = 300, temperature: float = 0.1) -> str:
    """底层调用 Qwen"""
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()
    try:
        req = urllib.request.Request(
            f"{LM_STUDIO}/chat/completions", body,
            {"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.debug(f"Qwen调用失败: {e}")
        return ""


def is_available() -> bool:
    """检查 Qwen 是否在线"""
    try:
        req = urllib.request.Request(f"{LM_STUDIO}/models")
        urllib.request.urlopen(req, timeout=2)
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
