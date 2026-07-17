"""
乾坤·UZI 主程序
用法：
  python main.py 002185          ← 分析华天科技
  python main.py scan            ← 扫描超卖股票
  python main.py web             ← 启动Web界面
"""

import sys, os, logging, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.fetcher import DataFetcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(message)s'
)
logger = logging.getLogger("qiankun")

# ═══════════════════════════════════════════
# 分析流程
# ═══════════════════════════════════════════

def analyze_stock(code: str):
    """分析一只股票 — 完整流程"""
    fetcher = DataFetcher()
    
    try:
        print(f"\n{'='*50}")
        print(f"  乾坤·UZI — 分析 {code}")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*50}\n")
        
        # 第1步：获取数据
        print("[1/4] 获取数据...")
        rt = fetcher.get_realtime(code)
        kline = fetcher.get_kline(code, days=60)
        
        if not rt and not kline:
            print(f"  ❌ 无法获取 {code} 的数据，请检查网络和股票代码")
            return
        
        name = rt.get("name", code) if rt else code
        
        if rt:
            print(f"  {name} 现价:{rt.get('price')} 涨跌:{rt.get('change_pct')}%")
        if kline:
            print(f"  K线数据: {len(kline)}条 (最新:{kline[-1]['date']})")
        
        # 第2步：技术指标
        print("\n[2/4] 计算技术指标...")
        indicators = calc_indicators(kline)
        print(f"  RSI(14): {indicators.get('rsi', '?')}")
        print(f"  MA5: {indicators.get('ma5', '?')}  MA20: {indicators.get('ma20', '?')}")
        print(f"  近5日涨跌: {indicators.get('recent_trend', '?')}")
        
        # 第3步：AI分析（尝试本地Qwen）
        print("\n[3/4] AI分析...")
        try:
            from brain.qwen import analyze_stock as qwen_analyze
            ai = qwen_analyze(code, name, kline or [], rt)
            print(f"  趋势: {ai.get('trend', '?')}")
            print(f"  建议: {ai.get('advice', '?')}")
            print(f"  分析: {ai.get('analysis', '')[:200]}...")
        except Exception as e:
            logger.warning(f"AI分析跳过（Qwen未运行）: {e}")
            ai = {"trend": "?", "advice": "?", "analysis": "Qwen模型未运行"}
        
        # 第4步：生成报告
        print("\n[4/4] 生成报告...")
        report = generate_report(code, name, rt, kline, indicators, ai)
        
        report_path = os.path.join(
            os.path.dirname(__file__), "output",
            f"{code}_{name}_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
        )
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        
        print(f"\n  ✅ 报告已生成: {report_path}")
        print(f"  用浏览器打开即可查看")
        
    finally:
        fetcher.close()


def scan_oversold():
    """扫描RSI超卖股票"""
    fetcher = DataFetcher()
    
    try:
        print(f"\n{'='*50}")
        print(f"  乾坤·UZI — 超卖扫描")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*50}\n")
        
        print("[1/3] 获取股票列表...")
        stocks = fetcher.get_stock_list()
        if not stocks:
            print("  ❌ 无法获取股票列表")
            return
        
        print(f"  共 {len(stocks)} 只股票")
        print(f"\n[2/3] 扫描超卖信号...")
        
        results = []
        for i, (code, name) in enumerate(stocks[:200], 1):  # 先扫前200只
            if i % 50 == 0:
                print(f"  进度: {i}/{min(200, len(stocks))}")
            
            kline = fetcher.get_kline(code, days=30)
            if not kline or len(kline) < 15:
                continue
            
            rsi = calc_rsi(kline)
            if rsi is None or rsi >= 40:
                continue
            
            # RSI<40 超卖信号
            rt = fetcher.get_realtime(code)
            change_pct = rt.get("change_pct", 0) if rt else 0
            
            results.append({
                "code": code,
                "name": name,
                "rsi": round(rsi, 1),
                "price": rt.get("price", 0) if rt else 0,
                "change_pct": change_pct,
            })
        
        # 按RSI从低到高排序
        results.sort(key=lambda x: x["rsi"])
        
        print(f"\n[3/3] 发现 {len(results)} 只超卖股票（RSI<40）:\n")
        print(f"  {'代码':<10} {'名称':<10} {'RSI':<8} {'现价':<10} {'涨跌'}")
        print(f"  {'-'*50}")
        for r in results[:20]:
            print(f"  {r['code']:<10} {r['name']:<10} {r['rsi']:<8.1f} {r['price']:<10.2f} {r['change_pct']:+.2f}%")
        
        if len(results) > 20:
            print(f"\n  ... 还有 {len(results)-20} 只，详见输出文件")
        
        # 保存结果
        output_path = os.path.join(
            os.path.dirname(__file__), "output",
            f"scan_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n  ✅ 结果已保存: {output_path}")
        
    finally:
        fetcher.close()


# ═══════════════════════════════════════════
# 技术指标
# ═══════════════════════════════════════════

def calc_rsi(kline: list, period: int = 14) -> float:
    """计算RSI"""
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
    return 100 - (100 / (1 + avg_gain / avg_loss))

def calc_indicators(kline: list) -> dict:
    """计算常用技术指标"""
    if not kline:
        return {}
    
    closes = [k["close"] for k in kline]
    volumes = [k["volume"] for k in kline]
    
    rsi = calc_rsi(kline)
    
    # 移动均线
    ma5 = sum(closes[-5:]) / min(5, len(closes)) if len(closes) >= 5 else None
    ma20 = sum(closes[-20:]) / min(20, len(closes)) if len(closes) >= 20 else None
    
    # 近期趋势
    if len(closes) >= 5:
        recent_change = (closes[-1] - closes[-5]) / closes[-5] * 100
        if recent_change > 5:
            trend = f"短期强势 +{recent_change:.1f}%"
        elif recent_change > 0:
            trend = f"短期偏强 +{recent_change:.1f}%"
        elif recent_change > -5:
            trend = f"短期偏弱 {recent_change:.1f}%"
        else:
            trend = f"短期弱势 {recent_change:.1f}%"
    else:
        trend = "数据不足"
    
    # 量价关系
    if len(volumes) >= 5:
        vol_avg_5 = sum(volumes[-5:]) / 5
        vol_avg_20 = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else vol_avg_5
        vol_ratio = vol_avg_5 / vol_avg_20 if vol_avg_20 > 0 else 1
    else:
        vol_ratio = 1
    
    return {
        "rsi": round(rsi, 1) if rsi else None,
        "ma5": round(ma5, 2) if ma5 else None,
        "ma20": round(ma20, 2) if ma20 else None,
        "recent_trend": trend,
        "vol_ratio": round(vol_ratio, 2),
        "latest_close": closes[-1] if closes else None,
        "latest_volume": volumes[-1] if volumes else None,
    }


# ═══════════════════════════════════════════
# 报告生成
# ═══════════════════════════════════════════

def generate_report(code, name, rt, kline, indicators, ai) -> str:
    """生成HTML报告"""
    rt = rt or {}
    indicators = indicators or {}
    ai = ai or {}
    
    change_pct = rt.get("change_pct", 0)
    color = "#ff4444" if change_pct > 0 else ("#44ff44" if change_pct < 0 else "#aaaaaa")
    
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name}({code}) - 乾坤·UZI 分析报告</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: 'Microsoft YaHei', sans-serif; background:#0a0e27; color:#e0e0e0; padding:20px; }}
  .container {{ max-width:900px; margin:0 auto; }}
  .header {{ text-align:center; padding:30px 0; border-bottom:1px solid #1a2040; }}
  .header h1 {{ font-size:28px; color:#fff; }}
  .header .code {{ color:#888; font-size:14px; }}
  .price {{ font-size:36px; font-weight:bold; color:{color}; margin:10px 0; }}
  .change {{ font-size:18px; color:{color}; }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; margin:20px 0; }}
  .card {{ background:#111633; border-radius:8px; padding:20px; border:1px solid #1a2040; }}
  .card h3 {{ color:#4a9eff; margin-bottom:12px; font-size:16px; }}
  .card table {{ width:100%; border-collapse:collapse; }}
  .card td {{ padding:6px 8px; border-bottom:1px solid #1a2040; font-size:14px; }}
  .card td:first-child {{ color:#888; width:40%; }}
  .card td:last-child {{ color:#e0e0e0; text-align:right; }}
  .ai-box {{ background:#0d1230; border:1px solid #1e3a60; border-radius:8px; padding:20px; margin:20px 0; }}
  .ai-box h3 {{ color:#ff9800; margin-bottom:10px; }}
  .ai-box .advice {{ display:inline-block; padding:4px 12px; border-radius:4px; font-weight:bold; }}
  .advice-buy {{ background:#1a3a1a; color:#4caf50; }}
  .advice-hold {{ background:#1a1a3a; color:#ff9800; }}
  .advice-sell {{ background:#3a1a1a; color:#f44336; }}
  .footer {{ text-align:center; color:#555; font-size:12px; padding:20px; border-top:1px solid #1a2040; margin-top:30px; }}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>{name}</h1>
  <div class="code">{code}</div>
  <div class="price">{rt.get('price', '-')}</div>
  <div class="change">{change_pct:+.2f}%</div>
</div>

<div class="grid">
  <div class="card">
    <h3>📊 技术指标</h3>
    <table>
      <tr><td>RSI(14)</td><td>{indicators.get('rsi', '-')}</td></tr>
      <tr><td>MA5</td><td>{indicators.get('ma5', '-')}</td></tr>
      <tr><td>MA20</td><td>{indicators.get('ma20', '-')}</td></tr>
      <tr><td>近期趋势</td><td>{indicators.get('recent_trend', '-')}</td></tr>
      <tr><td>量比</td><td>{indicators.get('vol_ratio', '-')}</td></tr>
    </table>
  </div>
  
  <div class="card">
    <h3>💰 实时行情</h3>
    <table>
      <tr><td>开盘</td><td>{rt.get('open', '-')}</td></tr>
      <tr><td>最高</td><td>{rt.get('high', '-')}</td></tr>
      <tr><td>最低</td><td>{rt.get('low', '-')}</td></tr>
      <tr><td>昨收</td><td>{rt.get('pre_close', '-')}</td></tr>
      <tr><td>成交量</td><td>{rt.get('volume', '-')}</td></tr>
    </table>
  </div>
</div>

<div class="ai-box">
  <h3>🤖 AI 分析 (Qwen3-VL-4B)</h3>
  <p style="margin:8px 0;">
    趋势: <strong>{ai.get('trend', '-')}</strong> &nbsp;|&nbsp; 
    建议: <span class="advice {'advice-buy' if ai.get('advice')=='买入' else 'advice-sell' if ai.get('advice')=='卖出' else 'advice-hold'}">{ai.get('advice', '-')}</span>
  </p>
  <p style="color:#bbb; font-size:14px; line-height:1.6;">{ai.get('analysis', '-')}</p>
</div>

<div class="footer">
  乾坤·UZI v1.0 | 数据: pytdx/baostock/腾讯qt | AI: Qwen3-VL-4B 本地运行<br>
  风险提示：本报告仅供参考，不构成投资建议。股市有风险，投资需谨慎。
</div>

</div>
</body>
</html>"""


# ═══════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python main.py 002185       ← 分析股票")
        print("  python main.py scan         ← 扫描超卖")
        sys.exit(0)
    
    arg = sys.argv[1]
    
    if arg == "scan":
        scan_oversold()
    elif arg.isdigit():
        analyze_stock(arg)
    else:
        print(f"未知命令: {arg}")
