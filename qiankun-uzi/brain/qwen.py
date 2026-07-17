"""
Qwen3-VL-4B 本地模型接口
通过 LM Studio (端口1234) 调用
"""

import json, base64, urllib.request, logging

logger = logging.getLogger("qiankun.brain")

LM_STUDIO = "http://127.0.0.1:1234/v1"
MODEL = "qwen/qwen3-vl-4b"

def ask(prompt: str, max_tokens: int = 1024, temperature: float = 0.1) -> str:
    """调用本地 Qwen 模型"""
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()
    req = urllib.request.Request(
        f"{LM_STUDIO}/chat/completions", body,
        {"Content-Type": "application/json"}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"Qwen调用失败: {e}")
        return ""

def analyze_chart(image_path: str, question: str = None) -> str:
    """用 Qwen3-VL 分析K线图"""
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    
    prompt = question or "分析这张K线图：支撑位、压力位、趋势方向、成交量特征"
    
    body = json.dumps({
        "model": MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/png;base64,{img_b64}"
                }}
            ]
        }],
        "max_tokens": 800,
        "temperature": 0.1,
    }).encode()
    req = urllib.request.Request(
        f"{LM_STUDIO}/chat/completions", body,
        {"Content-Type": "application/json"}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"Qwen看图失败: {e}")
        return ""

def analyze_stock(code: str, name: str, kline_data: list, realtime: dict) -> dict:
    """综合分析一只股票"""
    # 准备上下文
    recent = kline_data[-10:] if kline_data else []
    kline_str = "\n".join([
        f"{k['date']} O{k['open']:.2f} H{k['high']:.2f} L{k['low']:.2f} C{k['close']:.2f} V{k['volume']}"
        for k in recent
    ])
    
    rt = realtime or {}
    rt_str = f"现价{rt.get('price','?')} 涨跌{rt.get('change_pct','?')}%"
    
    prompt = f"""你是一位资深A股分析师。根据以下数据，给出这只股票的短线研判（100字以内）。

股票：{name}（{code}）
{rt_str}

近10日K线：
{kline_str}

请回答：
1. 当前处于什么趋势？（上涨/下跌/震荡）
2. 支撑位和压力位在哪？
3. 短线操作建议（买入/持有/卖出）"""

    analysis = ask(prompt, max_tokens=300)
    
    return {
        "code": code,
        "name": name,
        "trend": _extract_label(analysis, ["上涨", "下跌", "震荡"]),
        "advice": _extract_label(analysis, ["买入", "持有", "卖出"]),
        "analysis": analysis.strip(),
    }

def _extract_label(text: str, labels: list) -> str:
    """从文本中提取第一个匹配的标签"""
    for label in labels:
        if label in text:
            return label
    return "未知"
