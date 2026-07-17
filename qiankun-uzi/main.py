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

def analyze_stock(code: str, fast: bool = False):
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
        
        print(f"\n  [{name}] 现价 {rt.get('price','?')}  涨跌 {rt.get('change_pct','?'):+.2f}%")
        if rsi:
            rsi_color = "[-]" if rsi < 30 else ("[~]" if rsi < 40 else "[+]")
            print(f"  {rsi_color} RSI(14): {rsi}")
        if indicators.get("ma5") and indicators.get("ma20"):
            print(f"  [UP] MA5: {indicators['ma5']}  MA20: {indicators['ma20']}")
            print(f"  [DN] 趋势: {indicators.get('recent_trend','')}")
        
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
        model_available = not fast
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
        
        # 显示投票结果
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
                                ai_analysis, result)
        
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

def scan_oversold():
    """扫描RSI超卖股票（超短线版）"""
    fetcher = DataFetcher()

    try:
        print_header("乾坤·UZI 超短线扫描")

        stocks = fetcher.get_stock_list()
        if not stocks:
            print("  [X] 无法获取股票列表")
            return

        print(f"  共 {len(stocks)} 只股票，正在扫描...")
        print(f"  超短线信号: 量比>2 + RSI<45 + 近期放量\n")

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

            # 信号强度评分
            score = 0
            if rsi < 30: score += 3
            elif rsi < 35: score += 2
            elif rsi < 40: score += 1
            if vol_ratio > 3: score += 3
            elif vol_ratio > 2: score += 2
            if change_pct < -5: score += 2  # 大跌后反弹概率高
            if change_pct > 2: score += 1   # 已有资金介入

            if score >= 3:  # 至少3分才入选
                results.append({
                    "code": code, "name": name,
                    "rsi": round(rsi, 1),
                    "vol_ratio": round(vol_ratio, 1),
                    "price": rt.get("price", 0) if rt else 0,
                    "change_pct": change_pct,
                    "score": score,
                    "signal": "STRONG" if score >= 5 else ("GOOD" if score >= 4 else "WATCH"),
                })

        results.sort(key=lambda x: x["score"], reverse=True)

        print(f"\n  [OK] 发现 {len(results)} 只超短线候选:\n")
        print(f"  {'代码':<10} {'名称':<10} {'RSI':<8} {'量比':<8} {'涨跌':<10} {'评分':<6} {'信号'}")
        print(f"  {'-'*65}")
        for r in results[:20]:
            sig = r["signal"]
            sig_str = "[BUY]" if sig=="STRONG" else ("[++]" if sig=="GOOD" else "[+]")
            print(f"  {r['code']:<10} {r['name']:<10} {r['rsi']:<8.1f} {r['vol_ratio']:<8.1f} {r['change_pct']:>+8.2f}%  {r['score']:<6} {sig_str}")

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
        print(f"\n  [OK] 保存: output/{os.path.basename(output_path)}\n")

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


# ===========================================
# 报告生成
# ===========================================

def generate_report(code, name, rt, kline, indicators, ai_text, panel_result):
    rt = rt or {}
    ind = indicators or {}
    
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
    python main.py scan            扫描超卖股票
""")
        sys.exit(0)
    
    arg = sys.argv[1]
    fast = "--fast" in sys.argv
    
    if arg == "scan":
        scan_oversold()
    elif arg.replace(".","").isdigit():
        analyze_stock(arg, fast=fast)
    else:
        print(f"未知命令: {arg}")
