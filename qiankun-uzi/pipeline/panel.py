"""
投资人格陪审团 — UZI核心能力
加载51位投资大师，每人从自己的角度分析股票并投票
"""

import os, yaml, random, logging

logger = logging.getLogger("qiankun.panel")

PERSONAS_DIR = os.path.join(os.path.dirname(__file__), "personas")

# 人格分组
GROUPS = {
    "A": "经典价值",    # 巴菲特、格雷厄姆等
    "B": "成长投资",    # 费雪、林奇等
    "C": "宏观对冲",    # 索罗斯、达里奥等
    "D": "技术分析",    # 利弗莫尔、欧奈尔等
    "E": "中国价值",    # 张坤、陈晓群等
    "F": "中国游资",    # 养家、赵老哥等
    "G": "量化交易",    # 西蒙斯等
}

def load_personas() -> list:
    """加载所有投资人格"""
    personas = []
    if not os.path.exists(PERSONAS_DIR):
        return personas
    
    for filename in sorted(os.listdir(PERSONAS_DIR)):
        if not filename.endswith(".yaml"):
            continue
        filepath = os.path.join(PERSONAS_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and "id" in data:
                    personas.append(data)
        except Exception as e:
            logger.warning(f"加载人格失败 {filename}: {e}")
    
    return personas

def get_persona_summary(persona: dict) -> str:
    """生成人格的简短摘要"""
    return f"""[{persona.get('name','')}] {persona.get('school','')}派 | {persona.get('nationality','')}
投资哲学: {persona.get('philosophy','')[:200]}
A股观点: {persona.get('a_share_view','')[:200]}"""

def select_relevant_personas(personas: list, stock_info: dict, count: int = 12) -> list:
    """
    根据股票特征选择最相关的人格
    小盘/游资型 → 多选中国游资(F组)
    蓝筹/价值型 → 多选经典价值(A组)
    成长型 → 多选成长(B组)
    """
    # 优先选中国人格（更懂A股）+ 每组至少1个代表人物
    selected = []
    group_quota = {"F": 3, "E": 2, "A": 2, "B": 1, "D": 1, "C": 1, "G": 1}
    
    by_group = {}
    for p in personas:
        g = p.get("group", "A")
        by_group.setdefault(g, []).append(p)
    
    for g, quota in group_quota.items():
        candidates = by_group.get(g, [])
        random.shuffle(candidates)
        selected.extend(candidates[:quota])
    
    # 如果还不到count，随机补
    if len(selected) < count:
        remaining = [p for p in personas if p not in selected]
        random.shuffle(remaining)
        selected.extend(remaining[:count - len(selected)])
    
    return selected[:count]

def persona_vote(persona: dict, stock_data: dict) -> dict:
    """
    让一个人格对股票投票（使用本地Qwen角色扮演）
    """
    import urllib.request, json as j
    
    # 构建角色扮演提示
    kline_summary = ""
    if stock_data.get("kline"):
        closes = [k["close"] for k in stock_data["kline"][-10:]]
        kline_summary = f"近10日收盘: {', '.join([str(round(c,2)) for c in closes])}"
    
    rt = stock_data.get("realtime", {})
    price_info = f"现价{rt.get('price','?')} 涨跌{rt.get('change_pct','?')}%"
    
    prompt = f"""你现在是{persona['name']}（{persona.get('school','')}派投资大师）。

你的投资哲学：{persona.get('philosophy','')[:300]}

你对A股的看法：{persona.get('a_share_view','')[:200]}

你关注的关键指标：{', '.join(persona.get('key_metrics',[]) or [])[:200]}
你回避的情况：{', '.join(persona.get('avoids',[]) or [])[:200]}

现在有一只股票需要你判断：
代码：{stock_data.get('code','')}
名称：{stock_data.get('name','')}
{price_info}
{kline_summary}
RSI(14): {stock_data.get('rsi','?')}

请以{persona['name']}的口吻，用{persona.get('voice','')[:100]}的风格，给出你的判断：
1. 这只股票是否符合你的投资标准？（是/否/部分）
2. 你会买入、持有、还是卖出？
3. 一句话理由

请用中文回答，直接输出判断，不要多余解释。格式：投票|理由"""

    try:
        body = j.dumps({
            "model": "qwen/qwen3-vl-4b",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
            "temperature": 0.3,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:1234/v1/chat/completions", body,
            {"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=60)
        data = j.loads(resp.read())
        reply = data["choices"][0]["message"]["content"]
        
        # 解析投票
        vote = "持有"
        if "买入" in reply or "buy" in reply.lower():
            vote = "买入"
        elif "卖出" in reply or "sell" in reply.lower():
            vote = "卖出"
        
        return {
            "name": persona["name"],
            "group": persona.get("group", "?"),
            "vote": vote,
            "reason": reply.strip()[:200],
        }
    except Exception as e:
        logger.warning(f"{persona['name']}投票失败: {e}")
        return {
            "name": persona["name"],
            "group": persona.get("group", "?"),
            "vote": "弃权",
            "reason": f"模型调用失败",
        }

def run_panel(stock_data: dict, model_available: bool = True) -> dict:
    """
    运行投资人格陪审团
    返回投票汇总
    """
    personas = load_personas()
    if not personas:
        return {"error": "未找到投资人格文件", "votes": []}
    
    # 选择12位代表
    selected = select_relevant_personas(personas, stock_data, count=12)
    
    votes = []
    for p in selected:
        if model_available:
            vote = persona_vote(p, stock_data)
        else:
            # 模型不可用时，根据RSI和人格特点做简单判断
            vote = _simple_vote(p, stock_data)
        votes.append(vote)
    
    # 统计
    buy = sum(1 for v in votes if v["vote"] == "买入")
    sell = sum(1 for v in votes if v["vote"] == "卖出")
    hold = sum(1 for v in votes if v["vote"] == "持有")
    abstain = sum(1 for v in votes if v["vote"] == "弃权")
    
    # 按组统计
    by_group = {}
    for v in votes:
        g = v["group"]
        by_group.setdefault(g, {"买":0, "卖":0, "持":0, "弃":0})
        if v["vote"] == "买入": by_group[g]["买"] += 1
        elif v["vote"] == "卖出": by_group[g]["卖"] += 1
        elif v["vote"] == "持有": by_group[g]["持"] += 1
        else: by_group[g]["弃"] += 1
    
    # 综合判断
    if buy > sell and buy > hold:
        verdict = "偏多"
    elif sell > buy and sell > hold:
        verdict = "偏空"
    else:
        verdict = "中性"
    
    return {
        "total": len(votes),
        "buy": buy,
        "sell": sell,
        "hold": hold,
        "abstain": abstain,
        "verdict": verdict,
        "by_group": by_group,
        "votes": votes,
        "groups": GROUPS,
    }

def _simple_vote(persona: dict, stock_data: dict) -> dict:
    """简易投票（本地模型不可用时的降级方案）"""
    rsi = stock_data.get("rsi", 50)
    school = persona.get("school", "")
    group = persona.get("group", "")
    
    # 简单规则
    if group in ("A", "E"):  # 价值投资者 → RSI越低越买
        vote = "买入" if rsi and rsi < 35 else ("持有" if rsi and rsi < 50 else "卖出")
    elif group in ("B",):  # 成长投资者 → 中等RSI偏好
        vote = "买入" if rsi and 30 < rsi < 55 else "持有"
    elif group in ("F",):  # 游资 → 喜欢动量
        vote = "买入" if rsi and 20 < rsi < 45 else "持有"
    elif group in ("D",):  # 技术分析 → 看趋势
        vote = "买入" if rsi and rsi < 40 else "卖出"
    else:
        vote = "持有"
    
    reason = f"{'RSI超卖' if (rsi or 50) < 40 else 'RSI正常'}，{persona['name']}投票{vote}"
    
    return {
        "name": persona["name"],
        "group": group,
        "vote": vote,
        "reason": reason,
    }
