"""
乾坤·UZI v1.0 — A股 AI 分析系统
融合：乾坤数据管线 + UZI 66位投资人格陪审团 + Qwen本地AI

用法：
  python main.py 002185          ← 分析华天科技（完整流程）
  python main.py scan            ← 扫描全市场超卖股票
  python main.py 002185 --fast   ← 快速模式（不调用AI）
"""

import sys, os, json, logging, random
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.fetcher import DataFetcher
from pipeline.panel import run_panel, load_personas

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(message)s'
)
logger = logging.getLogger("qiankun")

# ===========================================
# 核心分析流程
# ===========================================

def analyze_stock(code: str, fast: bool = False, compare: bool = False):
    """完整分析一只股票"""
    fetcher = DataFetcher()
    
    try:
        # -- 第1步：获取数据 --
        print_header(f"乾坤·UZI 分析 {code}")
        
        rt = fetcher.get_realtime(code)
        kline = fetcher.get_kline(code, days=60)
        
        if not rt and not kline:
            print("  [X] 无法获取数据，请检查网络和股票代码")
            return
        
        name = rt.get("name", code) if rt else code
        indicators = calc_indicators(kline) if kline else {}
        rsi = indicators.get("rsi")

        # 超短线指标
        limit_status = detect_limit_status(rt) if rt else "unknown"
        intraday = fetcher.get_intraday(code)  # 5分钟K线
        intraday_stats = analyze_intraday(intraday) if intraday else {}

        print(f"\n  [{name}] 现价 {rt.get('price','?')}  涨跌 {rt.get('change_pct','?'):+.2f}%")
        if limit_status in ("涨停", "跌停"):
            print(f"  [!!] {limit_status}！注意风险")
        elif limit_status in ("near_up", "near_down"):
            print(f"  [!] 接近{limit_status}")
        if rsi:
            rsi_color = "[-]" if rsi < 30 else ("[~]" if rsi < 40 else "[+]")
            print(f"  {rsi_color} RSI(14): {rsi}")
        if indicators.get("ma5") and indicators.get("ma20"):
            print(f"  [UP] MA5: {indicators['ma5']}  MA20: {indicators['ma20']}")
            print(f"  [DN] 趋势: {indicators.get('recent_trend','')}")
        if intraday_stats:
            print(f"  [5M] 日内: {intraday_stats.get('trend','?')}", end="")
            if intraday_stats.get("surge"): print(f" | [+]拉升 {intraday_stats['surge_count']}次", end="")
            if intraday_stats.get("dump"): print(f" | [-]跳水 {intraday_stats['dump_count']}次", end="")
            if intraday_stats.get("vol_spike"): print(f" | [@]放量 {intraday_stats['vol_spike_count']}次", end="")
            print()
        
        # -- 第2步：AI分析 --
        print(f"\n{'-'*50}")
        print("  [AI] AI 分析 (Qwen3-VL-4B 本地)")
        
        ai_analysis = ""
        if not fast:
            try:
                from brain.qwen import analyze_stock as qwen_analyze
                ai = qwen_analyze(code, name, kline or [], rt)
                ai_analysis = ai.get("analysis", "")
                print(f"  趋势判断: {ai.get('trend','?')}")
                print(f"  操作建议: {ai.get('advice','?')}")
            except Exception as e:
                print(f"  [!]  Qwen未运行，跳过AI分析")
        else:
            print("  [>>] 快速模式，跳过AI分析")
        
        # -- 第3步：投资人格陪审团 --
        print(f"\n{'-'*50}")
        print("  [JURY] 投资人格陪审团")
        
        personas = load_personas()
        print(f"  已加载 {len(personas)} 位投资大师")
        
        stock_data = {
            "code": code, "name": name,
            "kline": kline, "realtime": rt,
            "rsi": rsi,
            "indicators": indicators,
        }
        
        # 根据QS模块是否可用选择模式
        model_available = not fast or compare  # compare模式强制启用AI
        if model_available:
            try:
                import urllib.request
                urllib.request.urlopen("http://127.0.0.1:1234/v1/models", timeout=2)
            except Exception:
                model_available = False
                print("  [!]  LM Studio未运行，使用简易投票模式")
        
        result = run_panel(stock_data, model_available=model_available)

        if "error" in result:
            print(f"  [X] 陪审团异常: {result['error']}")
            return

        # Qwen vs 简易规则 对比模式
        if compare and model_available:
            sep = "=" * 50
            print(f"\n  [CMP] Qwen vs 简易投票 对比")
            cmp_result = run_panel(stock_data, model_available=False)
            print(f"\n  {sep}")
            print(f"  {'':>12} {'Qwen AI':>15} {'简易规则':>15}")
            print(f"  {'-'*50}")
            print(f"  {'买入':>12} {result['buy']:>15} {cmp_result['buy']:>15}")
            print(f"  {'卖出':>12} {result['sell']:>15} {cmp_result['sell']:>15}")
            print(f"  {'持有':>12} {result['hold']:>15} {cmp_result['hold']:>15}")
            print(f"  {'综合':>12} {result['verdict']:>15} {cmp_result['verdict']:>15}")
            diff_count = 0
            for v_q, v_s in zip(result['votes'], cmp_result['votes']):
                if v_q['vote'] != v_s['vote']:
                    diff_count += 1
                    if diff_count <= 5:
                        q_name = v_q['name']
                        q_vote = v_q['vote']
                        s_vote = v_s['vote']
                        q_reason = v_q['reason'][:60]
                        print(f"  [!] {q_name}: Qwen={q_vote} vs 规则={s_vote} | {q_reason}")
            agree_pct = (result['total'] - diff_count) / result['total'] * 100
            print(f"\n  分歧: {diff_count}/{result['total']} 一致率: {agree_pct:.0f}%")
            print(f"  {sep}")

        print(f"\n  {'-'*40}")
        print(f"  陪审团投票结果 ({result['total']}位代表)")
        print(f"  {'-'*40}")
        print(f"  [+] 买入: {result['buy']}  |  [-] 卖出: {result['sell']}  |  [~] 持有: {result['hold']}  |  * 弃权: {result['abstain']}")
        print(f"  综合判断: {result['verdict']}")
        
        # 按组显示
        print(f"\n  分组投票:")
        for g, counts in result["by_group"].items():
            gname = result["groups"].get(g, g)
            bar = "*" * counts["买"] + "*" * counts["持"] + "*" * counts["卖"]
            print(f"  {g}.{gname:<8} {counts['买']}买 {counts['卖']}卖 {counts['持']}持 |{bar}")
        
        # 显示部分投票详情（前6位）
        print(f"\n  代表人物观点:")
        for v in result["votes"][:6]:
            emoji = "[+]" if v["vote"]=="买入" else ("[-]" if v["vote"]=="卖出" else "[~]")
            print(f"  {emoji} {v['name']} → {v['vote']} | {v['reason'][:100]}")
        
        # -- 第4步：生成报告 --
        print(f"\n{'-'*50}")
        print("  [RPT] 生成报告...")
        
        report = generate_report(code, name, rt, kline, indicators,
                                ai_analysis, result, limit_status, intraday_stats)
        
        report_path = os.path.join(
            os.path.dirname(__file__), "output",
            f"{code}_{name}_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
        )
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        
        print(f"  [OK] 报告: output/{os.path.basename(report_path)}")
        print(f"  [WEB] 用浏览器打开即可查看\n")
        
    finally:
        fetcher.close()


# ===========================================
# 超卖扫描
# ===========================================

def is_real_stock(code: str) -> bool:
    """筛掉指数，只保留个股"""
    c = code.strip()
    # 深圳主板/中小板: 000001-004999
    if c.startswith('00') and len(c) == 6: return c[0:4] != '0000'
    # 创业板: 300xxx
    if c.startswith('30'): return True
    # 上海主板: 600xxx-609xxx
    if c.startswith('60'): return True
    # 科创板: 688xxx
    if c.startswith('688'): return True
    # 北交所: 8xxxxx
    if c.startswith(('83','87')): return True
    # 指数: 399xxx, 395xxx, 000xxx(000300等)
    return False

def scan_oversold(lhb_filter: bool = False, notify: bool = False):
    """扫描RSI超卖股票（超短线版）"""
    import os
    fetcher = DataFetcher()

    try:
        title = "乾坤·UZI 超短线扫描"
        if lhb_filter:
            title += " (龙虎榜加持)"

        # 龙虎榜数据
        lhb_list = []
        lhb_codes = set()
        if lhb_filter:
            try:
                from data.lhb import get_lhb_list, analyze_lhb_signal
                lhb_list = get_lhb_list()
                lhb_codes = {item["code"] for item in lhb_list}
                print_header(title)
                print(f"  龙虎榜上榜: {len(lhb_list)}只，扫描将优先匹配\n")
            except Exception as e:
                print(f"  [!] 龙虎榜数据获取失败: {e}，继续普通扫描")
                lhb_filter = False
        else:
            print_header(title)

        stocks = fetcher.get_stock_list()
        if not stocks:
            print("  [X] 无法获取股票列表")
            return

        # 筛掉指数
        stocks = [(c, n) for c, n in stocks if is_real_stock(c)]
        if not stocks:
            print("  [X] 筛选后无个股")
            return

        print(f"  共 {len(stocks)} 只个股，正在扫描...")
        print(f"  超短线信号: 量比>1.5 + RSI<45 + 近期放量\n")

        results = []
        scan_count = min(len(stocks), 300)
        for i, (code, name) in enumerate(stocks[:scan_count], 1):
            if i % 100 == 0:
                print(f"  进度: {i}/{scan_count}")

            kline = fetcher.get_kline(code, days=30)
            if not kline or len(kline) < 15:
                continue

            # 超短线指标
            indicators = calc_indicators(kline)
            rsi = indicators.get("rsi")
            vol_ratio = indicators.get("vol_ratio", 1)

            # 超短线筛选条件
            if rsi is None:
                continue
            if rsi >= 45:  # 放宽RSI（超短线不只看超卖）
                continue
            if vol_ratio < 1.5:  # 量比太低不关注
                continue

            rt = fetcher.get_realtime(code)
            change_pct = rt.get("change_pct", 0) if rt else 0

            # 筛涨停跌停
            if rt:
                ls = detect_limit_status(rt)
                if ls in ("涨停", "跌停"):
                    continue  # 涨停买不到，跌停不想抄

            # 信号强度评分
            score = 0
            if rsi < 30: score += 3
            elif rsi < 35: score += 2
            elif rsi < 40: score += 1
            if vol_ratio > 3: score += 3
            elif vol_ratio > 2: score += 2
            if change_pct < -5: score += 2  # 大跌后反弹概率高
            if change_pct > 2: score += 1   # 已有资金介入

            # 超短线加分：日内分时
            intraday_stats = {}
            if score >= 2:
                intraday = fetcher.get_intraday(code)
                if intraday:
                    intraday_stats = analyze_intraday(intraday)
                    if intraday_stats.get("surge"): score += 2  # 分时拉升=资金介入
                    if intraday_stats.get("vol_spike"): score += 1  # 放量异动

            # 龙虎榜加分：游资已在场内
            lhb_signal = {}
            if lhb_filter and code in lhb_codes:
                lhb_item = next((x for x in lhb_list if x["code"] == code), None)
                if lhb_item:
                    lhb_signal = analyze_lhb_signal(lhb_item)
                    score += lhb_signal.get("score", 0)

            if score >= 3:  # 至少3分才入选
                results.append({
                    "code": code, "name": name,
                    "rsi": round(rsi, 1),
                    "vol_ratio": round(vol_ratio, 1),
                    "price": rt.get("price", 0) if rt else 0,
                    "change_pct": change_pct,
                    "score": score,
                    "signal": "STRONG" if score >= 7 else ("GOOD" if score >= 5 else "WATCH"),
                    "intraday_trend": intraday_stats.get("trend", ""),
                    "limit_status": detect_limit_status(rt) if rt else "",
                    "lhb_net": lhb_signal.get("net_amount", 0),
                    "lhb_signal": lhb_signal.get("signal", ""),
                    "lhb_reason": lhb_signal.get("reason", ""),
                })

        results.sort(key=lambda x: x["score"], reverse=True)

        print(f"\n  [OK] 发现 {len(results)} 只超短线候选:\n")
        has_lhb = any(r.get("lhb_signal") for r in results)
        if has_lhb:
            print(f"  {'代码':<10} {'名称':<10} {'RSI':<7} {'量比':<7} {'涨跌':<9} {'评分':<5} {'日内':<10} {'龙虎榜':<10} {'信号'}")
            print(f"  {'-'*80}")
        else:
            print(f"  {'代码':<10} {'名称':<10} {'RSI':<8} {'量比':<8} {'涨跌':<10} {'评分':<6} {'日内':<10} {'信号'}")
            print(f"  {'-'*75}")
        for r in results[:20]:
            sig = r["signal"]
            sig_str = "[BUY]" if sig=="STRONG" else ("[++]" if sig=="GOOD" else "[+]")
            intraday_info = r.get("intraday_trend", "")
            if r.get("limit_status") in ("near_up", "near_down"):
                intraday_info = r["limit_status"]
            lhb_info = ""
            if r.get("lhb_signal"):
                lhb_net = r.get("lhb_net", 0)
                lhb_info = f"{r['lhb_signal']}({lhb_net/10000:.1f}亿)"
            if has_lhb:
                print(f"  {r['code']:<10} {r['name']:<10} {r['rsi']:<7.1f} {r['vol_ratio']:<7.1f} {r['change_pct']:>+7.2f}%  {r['score']:<5} {intraday_info:<10} {lhb_info:<10} {sig_str}")
            else:
                print(f"  {r['code']:<10} {r['name']:<10} {r['rsi']:<8.1f} {r['vol_ratio']:<8.1f} {r['change_pct']:>+8.2f}%  {r['score']:<6} {intraday_info:<10} {sig_str}")

        if len(results) > 20:
            print(f"\n  ... 还有 {len(results)-20} 只")

        # 保存
        output_path = os.path.join(
            os.path.dirname(__file__), "output",
            f"scan_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n  [OK] 保存: output/{os.path.basename(output_path)}")

        # 飞书推送
        if notify:
            try:
                from notify.feishu import send_scan_results
                if send_scan_results(results):
                    print(f"  [OK] 飞书推送成功")
                else:
                    print(f"  [!] 飞书推送失败（webhook未配置？）")
            except Exception as e:
                print(f"  [X] 飞书推送异常: {e}")
        print()

    finally:
        fetcher.close()


# ===========================================
# 技术指标
# ===========================================

def calc_rsi(kline: list, period: int = 14):
    if len(kline) < period + 1:
        return None
    closes = [k["close"] for k in kline]
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_gain / avg_loss)), 1)

def calc_indicators(kline: list) -> dict:
    if not kline:
        return {}
    closes = [k["close"] for k in kline]
    volumes = [k["volume"] for k in kline]
    rsi = calc_rsi(kline)
    ma5 = round(sum(closes[-5:])/min(5,len(closes)), 2) if len(closes)>=5 else None
    ma20 = round(sum(closes[-20:])/min(20,len(closes)), 2) if len(closes)>=20 else None
    if len(closes)>=5:
        rc = (closes[-1]-closes[-5])/closes[-5]*100
        trend = f"+{rc:.1f}%" if rc>0 else f"{rc:.1f}%"
    else:
        trend = "?"
    vol_ratio = round(sum(volumes[-5:])/5 / (sum(volumes[-20:])/20), 2) if len(volumes)>=20 else 1
    return {"rsi":rsi, "ma5":ma5, "ma20":ma20, "recent_trend":trend,
            "vol_ratio":vol_ratio, "latest_close":closes[-1]}


# ═══════════════════════════════════════════
# 超短线专属指标
# ═══════════════════════════════════════════

def detect_limit_status(rt: dict) -> str:
    """
    涨停/跌停检测
    A股：主板±10%，科创/创业±20%，北交±30%
    返回: "涨停"/"跌停"/"near_up"/"near_down"/"normal"
    """
    price = rt.get("price", 0)
    pre_close = rt.get("pre_close", 0)
    if not price or not pre_close or pre_close == 0:
        return "unknown"

    change_pct = (price - pre_close) / pre_close * 100

    # 判断板块
    code = str(rt.get("code", ""))
    if code.startswith("688") or code.startswith("30"):
        limit = 20  # 科创板 创业板
    elif code.startswith(("83", "87")):
        limit = 30  # 北交所
    else:
        limit = 10  # 主板

    if change_pct >= limit * 0.995:
        return "涨停"
    elif change_pct <= -limit * 0.995:
        return "跌停"
    elif change_pct >= limit * 0.85:
        return "near_up"
    elif change_pct <= -limit * 0.85:
        return "near_down"
    return "normal"


def analyze_intraday(intraday: list) -> dict:
    """
    分析5分钟K线，检测：
    - 分时拉升（短时间内快速上涨）
    - 分时出货（短时间内快速下跌）
    - 成交量异动
    """
    if not intraday or len(intraday) < 12:
        return {"surge": False, "dump": False, "vol_spike": False,
                "trend": "数据不足", "max_surge_pct": 0}

    # 计算每根K线的涨跌幅
    surges = []
    dumps = []
    vol_spikes = []
    avg_vol = sum(k["volume"] for k in intraday) / len(intraday)

    for i, bar in enumerate(intraday):
        if i == 0:
            continue
        prev = intraday[i-1]
        # 涨幅
        chg = (bar["close"] - prev["close"]) / prev["close"] * 100
        # 成交量倍数
        vol_ratio = bar["volume"] / avg_vol if avg_vol > 0 else 1

        if chg > 2.0:  # 2%以上拉升
            surges.append({"time": bar["time"], "pct": round(chg, 2), "vol": round(vol_ratio, 1)})
        if chg < -2.0:  # 2%以上跳水
            dumps.append({"time": bar["time"], "pct": round(chg, 2), "vol": round(vol_ratio, 1)})
        if vol_ratio > 3.0:  # 3倍均量
            vol_spikes.append({"time": bar["time"], "vol_ratio": round(vol_ratio, 1)})

    # 趋势判断：最近6根K线(30分钟)
    recent = intraday[-6:]
    first_close = recent[0]["close"]
    last_close = recent[-1]["close"]
    if first_close > 0:
        trend_pct = (last_close - first_close) / first_close * 100
        if trend_pct > 1.5:
            trend = "快速拉升"
        elif trend_pct > 0.5:
            trend = "温和上涨"
        elif trend_pct < -1.5:
            trend = "快速下跌"
        elif trend_pct < -0.5:
            trend = "温和下跌"
        else:
            trend = "窄幅震荡"
    else:
        trend = "?"

    max_surge = max([s["pct"] for s in surges]) if surges else 0

    return {
        "surge": len(surges) > 0,
        "surge_count": len(surges),
        "dump": len(dumps) > 0,
        "dump_count": len(dumps),
        "vol_spike": len(vol_spikes) > 0,
        "vol_spike_count": len(vol_spikes),
        "trend": trend,
        "max_surge_pct": max_surge,
        "surges": surges,
        "dumps": dumps,
        "vol_spikes": vol_spikes,
    }


# ===========================================
# 报告生成
# ===========================================

def generate_report(code, name, rt, kline, indicators, ai_text, panel_result, limit_status="", intraday_stats=None):
    rt = rt or {}
    ind = indicators or {}
    intraday_stats = intraday_stats or {}

    change_pct = rt.get("change_pct", 0)
    c = "#ff4444" if change_pct > 0 else ("#44ff44" if change_pct < 0 else "#aaa")

    # 构建投票表格
    vote_rows = ""
    for v in panel_result.get("votes", [])[:12]:
        emoji = {"买入":"[+]","卖出":"[-]","持有":"[~]","弃权":"*"}.get(v["vote"],"*")
        vote_rows += f"""
        <tr>
          <td>{emoji}</td>
          <td>{v['name']}</td>
          <td><span class="vote-{v['vote']}">{v['vote']}</span></td>
          <td style="font-size:12px;color:#aaa;">{v['reason'][:80]}</td>
        </tr>"""
    
    # 分组投票JS数据
    groups_js = json.dumps(panel_result.get("by_group", {}), ensure_ascii=False)
    
    # AI分析
    ai_html = ""
    if ai_text:
        ai_html = f"""
        <div class="ai-box">
          <h3>[AI] AI 分析 (Qwen3-VL-4B 本地)</h3>
          <p style="color:#bbb;font-size:14px;line-height:1.8;">{ai_text}</p>
        </div>"""
    
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name}({code}) - 乾坤·UZI</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:'Microsoft YaHei',sans-serif;background:#0a0e27;color:#e0e0e0;padding:20px}}
  .container{{max-width:960px;margin:0 auto}}
  .header{{text-align:center;padding:30px 0;border-bottom:1px solid #1a2040}}
  .header h1{{font-size:28px;color:#fff}}
  .header .sub{{color:#888;font-size:14px;margin-top:5px}}
  .price{{font-size:42px;font-weight:bold;color:{c};margin:10px 0}}
  .change{{font-size:18px;color:{c}}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:20px 0}}
  .card{{background:#111633;border-radius:8px;padding:20px;border:1px solid #1a2040}}
  .card h3{{color:#4a9eff;margin-bottom:12px;font-size:16px;border-bottom:1px solid #1a2040;padding-bottom:8px}}
  .card table{{width:100%;border-collapse:collapse}}
  .card td{{padding:6px 8px;border-bottom:1px solid #111633;font-size:14px}}
  .card td:first-child{{color:#888;width:40%}}
  .card td:last-child{{color:#e0e0e0;text-align:right;font-weight:bold}}
  .ai-box{{background:#0d1230;border:1px solid #1e3a60;border-radius:8px;padding:20px;margin:20px 0}}
  .ai-box h3{{color:#ff9800;margin-bottom:10px}}
  .verdict{{text-align:center;padding:20px;margin:20px 0;border-radius:8px}}
  .verdict-bullish{{background:linear-gradient(135deg,#1a3a1a,#0a1a0a);border:1px solid #2a5a2a}}
  .verdict-bearish{{background:linear-gradient(135deg,#3a1a1a,#1a0a0a);border:1px solid #5a2a2a}}
  .verdict-neutral{{background:linear-gradient(135deg,#1a1a2a,#0a0a1a);border:1px solid #2a2a4a}}
  .verdict h2{{font-size:24px}}
  .verdict .stats{{font-size:36px;font-weight:bold;margin:10px 0}}
  .vote-买入{{color:#4caf50;font-weight:bold}}
  .vote-卖出{{color:#f44336;font-weight:bold}}
  .vote-持有{{color:#ff9800;font-weight:bold}}
  .group-bar{{display:flex;align-items:center;margin:8px 0;font-size:13px}}
  .group-bar .label{{width:120px;color:#888}}
  .group-bar .bar{{flex:1;height:20px;border-radius:4px;display:flex;overflow:hidden}}
  .bar-buy{{background:#4caf50}}
  .bar-hold{{background:#ff9800}}
  .bar-sell{{background:#f44336}}
  .footer{{text-align:center;color:#555;font-size:12px;padding:20px;border-top:1px solid #1a2040;margin-top:30px}}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>{name}</h1>
  <div class="sub">{code} · 乾坤·UZI 分析报告</div>
  <div class="price">{rt.get('price','-')}</div>
  <div class="change">{change_pct:+.2f}%</div>
</div>

<div class="grid">
  <div class="card">
    <h3>[DATA] 技术指标</h3>
    <table>
      <tr><td>RSI(14)</td><td>{ind.get('rsi','-')}</td></tr>
      <tr><td>MA5</td><td>{ind.get('ma5','-')}</td></tr>
      <tr><td>MA20</td><td>{ind.get('ma20','-')}</td></tr>
      <tr><td>近期趋势</td><td>{ind.get('recent_trend','-')}</td></tr>
      <tr><td>量比</td><td>{ind.get('vol_ratio','-')}</td></tr>
    </table>
  </div>
  
  <div class="card">
    <h3>[5M] 超短线指标</h3>
    <table>
      <tr><td>涨停/跌停</td><td>{"[!!]" + limit_status if limit_status in ("涨停","跌停","near_up","near_down") else limit_status or "正常"}</td></tr>
      <tr><td>日内趋势</td><td>{intraday_stats.get("trend","-")}</td></tr>
      <tr><td>分时拉升</td><td>{"+" + str(intraday_stats.get("surge_count",0)) + "次" if intraday_stats.get("surge") else "无"}</td></tr>
      <tr><td>分时跳水</td><td>{"-" + str(intraday_stats.get("dump_count",0)) + "次" if intraday_stats.get("dump") else "无"}</td></tr>
      <tr><td>放量异动</td><td>{"@" + str(intraday_stats.get("vol_spike_count",0)) + "次" if intraday_stats.get("vol_spike") else "无"}</td></tr>
    </table>
  </div>

  <div class="card">
    <h3>💰 实时行情</h3>
    <table>
      <tr><td>开盘</td><td>{rt.get('open','-')}</td></tr>
      <tr><td>最高</td><td>{rt.get('high','-')}</td></tr>
      <tr><td>最低</td><td>{rt.get('low','-')}</td></tr>
      <tr><td>昨收</td><td>{rt.get('pre_close','-')}</td></tr>
      <tr><td>成交量</td><td>{rt.get('volume','-')}</td></tr>
    </table>
  </div>
</div>

<div class="verdict verdict-{'bullish' if panel_result.get('verdict')=='偏多' else 'bearish' if panel_result.get('verdict')=='偏空' else 'neutral'}">
  <h2>[JURY] 投资人格陪审团裁决</h2>
  <div class="stats">
    [+] {panel_result.get('buy',0)} 买 &nbsp;|&nbsp; [-] {panel_result.get('sell',0)} 卖 &nbsp;|&nbsp; [~] {panel_result.get('hold',0)} 持
  </div>
  <div style="font-size:18px;margin-top:10px">
    综合判断: <strong>{panel_result.get('verdict','?')}</strong> &nbsp; ({panel_result.get('total',0)}位代表投票)
  </div>
</div>

{ai_html}

<div class="card" style="margin:20px 0">
  <h3>🗳️ 代表人物投票</h3>
  <table>{vote_rows}</table>
</div>

<div class="footer">
  乾坤·UZI v1.0 | 数据: pytdx/baostock/腾讯qt | AI: Qwen3-VL-4B (本地)<br>
  陪审团: 51位投资大师人格 | {datetime.now().strftime('%Y-%m-%d %H:%M')}<br>
  [!] 风险提示：本报告仅供学习参考，不构成投资建议。股市有风险，投资需谨慎。
</div>

</div>
</body>
</html>"""


# ===========================================
# 工具
# ===========================================

def print_header(title: str):
    print(f"""
+==========================================+
|  {title}
|  {datetime.now().strftime('%Y-%m-%d %H:%M')}
+==========================================+""")

def show_config():
    """显示/修改系统配置"""
    import os

    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    default_config = {
        "data_source": "pytdx",        # pytdx | baostock | tencent
        "scan_limit": 300,             # 扫描股票数量上限
        "rsi_threshold": 45,           # RSI 阈值
        "vol_ratio_min": 1.5,          # 最低量比
        "min_score": 3,                # 最低信号评分
        "enable_ai": True,             # 启用 Qwen AI
        "enable_jury": True,           # 启用陪审团
        "ai_endpoint": "http://127.0.0.1:1234/v1",
        "personas_dir": "personas",
        "output_dir": "output",
        "super_short_term": True,      # 超短线模式
    }

    config = {}
    if os.path.exists(config_path):
        import json
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

    # merge defaults
    for k, v in default_config.items():
        config.setdefault(k, v)

    if len(sys.argv) > 2 and sys.argv[2] == "set":
        # 设置配置项: python main.py config set key value
        if len(sys.argv) < 5:
            print("  用法: python main.py config set <key> <value>")
            return
        key = sys.argv[3]
        val = sys.argv[4]
        if key in default_config:
            # 类型转换
            orig_type = type(default_config[key])
            if orig_type == bool:
                val = val.lower() in ("true", "1", "yes")
            elif orig_type == int:
                val = int(val)
            elif orig_type == float:
                val = float(val)
            config[key] = val
            import json
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"  [OK] {key} = {val}")
        else:
            print(f"  [X] 未知配置项: {key}")
            print(f"  可用: {', '.join(default_config.keys())}")
        return

    # 显示配置
    print_header("乾坤·UZI 系统配置")
    print(f"\n  配置文件: {config_path}")
    print(f"  {'-'*45}")
    for k, v in config.items():
        default_mark = " (默认)" if k in default_config and v == default_config[k] else ""
        print(f"  {k:<25} = {str(v):<15}{default_mark}")
    print(f"\n  修改: python main.py config set <key> <value>\n")

# ===========================================
# 入口
# ===========================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("""
  乾坤·UZI v1.0 — A股 AI 分析系统

  用法:
    python main.py 002185          分析华天科技
    python main.py 002185 --fast   快速模式（不调AI）
    python main.py 002185 --compare 对比模式(Qwen vs 简易投票)
    python main.py scan            扫描超卖股票
    python main.py scan --lhb      扫描+龙虎榜加成
    python main.py scan --notify   扫描+飞书推送
    python main.py lhb             查看龙虎榜
    python main.py config          查看/修改配置
""")
        sys.exit(0)

    arg = sys.argv[1]
    fast = "--fast" in sys.argv
    use_lhb = "--lhb" in sys.argv
    use_notify = "--notify" in sys.argv
    use_compare = "--compare" in sys.argv

    if arg == "scan":
        scan_oversold(lhb_filter=use_lhb, notify=use_notify)
    elif arg == "lhb":
        from data.lhb import print_lhb_summary
        print_lhb_summary()
    elif arg == "config":
        show_config()
    elif arg.replace(".","").isdigit():
        analyze_stock(arg, fast=fast, compare=use_compare)
    else:
        print(f"未知命令: {arg}")
