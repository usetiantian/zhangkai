# 乾坤 (QianKun) — A股模拟交易系统
#
# 每日扫描 → Qwen3-VL-4B分析 → 模拟交易 → 持仓跟踪
#
import json, os, sys, io, base64, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import baostock as bs
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ── 配置 ──
PORTFOLIO_FILE = Path(__file__).parent / "portfolio.json"
LMSTUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
INITIAL_CAPITAL = 1_000_000
MAX_POSITIONS = 5
SCAN_BATCH = 300  # 每批扫描数量，全市场5201只约需15批
STOP_LOSS = -0.08  # 止损线
TAKE_PROFIT = 0.20  # 止盈线


# ── 数据获取 ──
def get_stock_list():
    bs.login()
    rs = bs.query_stock_basic(code_name='')
    stocks = []
    while rs.next(): stocks.append(rs.get_row_data())
    bs.logout()
    df = pd.DataFrame(stocks, columns=['code','code_name','ipoDate','outDate','type','status'])
    return df[(df['type']=='1') & (df['status']=='1')]


def get_kline(code, days=60):
    end = datetime.now().strftime('%Y-%m-%d')
    start = (datetime.now() - timedelta(days=days+10)).strftime('%Y-%m-%d')
    bs.login()
    rs = bs.query_history_k_data_plus(code, 'date,open,close,high,low,volume',
                                       start_date=start, end_date=end,
                                       frequency='d', adjustflag='2')
    rows = []
    while rs.next(): rows.append(rs.get_row_data())
    bs.logout()
    if len(rows) < 20:
        return None
    df = pd.DataFrame(rows, columns=['date','open','close','high','low','volume'])
    for c in ['open','close','high','low','volume']:
        df[c] = pd.to_numeric(df[c])
    return df


# ── 图表生成 ──
def make_chart(code, name, df, save_path):
    df['date'] = pd.to_datetime(df['date'])
    df['MA5'] = df['close'].rolling(5).mean()
    df['MA10'] = df['close'].rolling(10).mean()
    df['MA20'] = df['close'].rolling(20).mean()
    df['MA60'] = df['close'].rolling(60).mean()
    x = range(len(df))

    fig = plt.figure(figsize=(14, 8))
    gs = fig.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.05)
    ax1 = fig.add_subplot(gs[0]); ax2 = fig.add_subplot(gs[1])

    colors = ['#ff4444' if df['close'].iloc[i] >= df['open'].iloc[i] else '#00aa00' for i in x]
    for i in x:
        o, c_, h, l = df['open'].iloc[i], df['close'].iloc[i], df['high'].iloc[i], df['low'].iloc[i]
        ax1.plot([i, i], [l, h], color=colors[i], linewidth=0.8)
        ax1.add_patch(plt.Rectangle((i-0.3, min(o, c_)), 0.6, abs(c_-o), color=colors[i], alpha=0.9))

    ax1.plot(x, df['MA5'], 'b-', lw=1, label='MA5')
    ax1.plot(x, df['MA10'], 'orange', lw=1, label='MA10')
    ax1.plot(x, df['MA20'], 'purple', lw=1.5, label='MA20')
    ax1.plot(x, df['MA60'], 'gray', lw=1, label='MA60', alpha=0.6)

    pct_30 = (df['close'].iloc[-1] - df['close'].iloc[-min(21, len(df))]) / df['close'].iloc[-min(21, len(df))] * 100
    ax1.set_title(f'{code} {name}  现价:{df["close"].iloc[-1]:.2f}  30日:{pct_30:+.1f}%', fontsize=14, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=8); ax1.grid(True, alpha=0.3)

    vcolors = ['#ff4444' if df['close'].iloc[i] >= df['open'].iloc[i] else '#00aa00' for i in x]
    ax2.bar(x, df['volume'], color=vcolors, alpha=0.6, width=0.8); ax2.grid(True, alpha=0.3)
    ticks = x[::15]
    ax2.set_xticks(ticks)
    ax2.set_xticklabels([df['date'].iloc[i].strftime('%m/%d') for i in ticks], rotation=45, fontsize=8)
    plt.tight_layout()
    plt.savefig(save_path, dpi=100, bbox_inches='tight')
    plt.close()


# ── Qwen3-VL-4B 分析 ──
def ask_qwen(image_path, prompt):
    with open(image_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode()
    payload = {
        'model': 'qwen/qwen3-vl-4b',
        'messages': [{'role': 'user', 'content': [
            {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{img_b64}'}},
            {'type': 'text', 'text': prompt}
        ]}],
        'max_tokens': 300, 'temperature': 0.3
    }
    req = urllib.request.Request(LMSTUDIO_URL, data=json.dumps(payload).encode(),
                                  headers={'Content-Type': 'application/json'})
    resp = urllib.request.urlopen(req, timeout=90)
    return json.loads(resp.read())['choices'][0]['message']['content']


# ── 持仓管理 ──
def load_portfolio():
    if PORTFOLIO_FILE.exists():
        with open(PORTFOLIO_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {'cash': INITIAL_CAPITAL, 'positions': [], 'history': []}


def save_portfolio(pf):
    with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
        json.dump(pf, f, ensure_ascii=False, indent=2)


def check_positions(pf, market_prices):
    """检查持仓：止损/止盈"""
    updated = False
    for pos in pf['positions']:
        if pos['status'] != 'holding':
            continue
        code = pos['code']
        if code not in market_prices:
            continue
        current = market_prices[code]
        pnl_pct = (current - pos['buy_price']) / pos['buy_price']
        pos['current_price'] = current
        pos['pnl_pct'] = round(pnl_pct * 100, 1)

        if pnl_pct <= STOP_LOSS:
            pos['status'] = 'stopped_out'
            pos['sell_price'] = current
            pos['sell_date'] = datetime.now().strftime('%Y-%m-%d')
            pos['reason'] = f'止损 ({pnl_pct*100:.1f}%)'
            pf['cash'] += current * pos['shares'] * 0.997  # 扣除手续费
            updated = True
            print(f'  🔴 止损: {pos["name"]}({code}) {pnl_pct*100:.1f}%')

        elif pnl_pct >= TAKE_PROFIT:
            pos['status'] = 'take_profit'
            pos['sell_price'] = current
            pos['sell_date'] = datetime.now().strftime('%Y-%m-%d')
            pos['reason'] = f'止盈 ({pnl_pct*100:.1f}%)'
            pf['cash'] += current * pos['shares'] * 0.997
            updated = True
            print(f'  🟢 止盈: {pos["name"]}({code}) {pnl_pct*100:.1f}%')

    return updated


def buy_stock(pf, code, name, price, shares, reason):
    cost = price * shares * 1.003  # 手续费
    if cost > pf['cash']:
        return False
    pf['cash'] -= cost
    pf['positions'].append({
        'code': code, 'name': name, 'buy_price': price,
        'shares': shares, 'buy_date': datetime.now().strftime('%Y-%m-%d'),
        'cost': cost, 'reason': reason, 'status': 'holding',
        'current_price': price, 'pnl_pct': 0
    })
    pf['history'].append({
        'type': 'buy', 'code': code, 'name': name,
        'price': price, 'shares': shares, 'date': datetime.now().strftime('%Y-%m-%d'),
        'reason': reason
    })
    return True


# ── 主流程 ──
def main():
    print(f'{"="*60}')
    print(f'  乾坤 A股模拟交易系统')
    print(f'  时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'{"="*60}')

    pf = load_portfolio()
    holding_codes = {p['code'] for p in pf['positions'] if p['status'] == 'holding'}
    print(f'\n💰 现金: {pf["cash"]:,.0f} | 持仓: {len(holding_codes)}/{MAX_POSITIONS}')
    for p in pf['positions']:
        if p['status'] == 'holding':
            print(f'   {p["code"]} {p["name"]} 买入{p["buy_price"]:.1f} 现价{p.get("current_price","?")} PnL:{p.get("pnl_pct",0):+.1f}%')

    # 扫描市场
    print(f'\n📊 扫描全市场...')
    all_stocks = get_stock_list()
    codes = all_stocks['code'].tolist()
    names = dict(zip(all_stocks['code'], all_stocks['code_name']))
    print(f'   共 {len(codes)} 只A股，分批扫描...')

    candidates = []
    scanned = 0
    for i in range(0, min(len(codes), SCAN_BATCH * 5), 10):
        batch = codes[i:i+10]
        try:
            bs.login()
            for code in batch:
                try:
                    df = get_kline(code, days=60)
                    if df is None or len(df) < 30:
                        continue
                    closes = df['close'].values
                    volumes = df['volume'].values
                    pct_30 = (closes[-1] - closes[-min(21,len(closes))]) / closes[-min(21,len(closes))] * 100
                    avg_vol = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)
                    vol_ratio = volumes[-1] / avg_vol if avg_vol > 0 else 0
                    if pct_30 > 3 and vol_ratio > 1.2:
                        candidates.append({
                            'code': code, 'name': names.get(code, '?'),
                            'pct_30': round(pct_30, 1), 'close': closes[-1],
                            'vol_ratio': round(vol_ratio, 1)
                        })
                except:
                    pass
            bs.logout()
        except:
            pass
        scanned += len(batch)
        if scanned % 100 == 0:
            print(f'   进度: {scanned}/{min(len(codes), SCAN_BATCH * 5)}')

    candidates.sort(key=lambda x: x['pct_30'], reverse=True)
    print(f'\n📈 候选: {len(candidates)} 只 (30日涨>3%, 放量)')

    # Qwen3-VL-4B 深度分析前 N 只
    top_n = min(10, len(candidates))
    print(f'\n🤖 Qwen3-VL-4B 深度分析前 {top_n} 只...')
    print()

    charts_dir = Path(__file__).parent / "charts"
    charts_dir.mkdir(exist_ok=True)

    for c in candidates[:top_n]:
        code = c['code']
        name = c['name']
        short_code = code[3:]

        if code in holding_codes:
            print(f'  ⏭ {short_code} {name} — 已持仓，跳过')
            continue

        # 拉完整 K 线画图
        df = get_kline(code, days=120)
        if df is None:
            continue

        chart_path = charts_dir / f'{short_code}.png'
        make_chart(short_code, name, df, str(chart_path))

        # Qwen 分析
        try:
            prompt = f'{short_code} {name}，近30日涨{c["pct_30"]}%。看图：能买吗？趋势、支撑压力、目标价。中文60字。'
            analysis = ask_qwen(str(chart_path), prompt)
            print(f'  {short_code} {name} +{c["pct_30"]}%')
            print(f'  {analysis[:200]}')

            # 简单决策：含"买""逢低""介入""布局"等词 → 模拟买入
            buy_keywords = ['买入', '可买', '逢低', '介入', '布局', '建仓', '加仓', '持有']
            if any(kw in analysis for kw in buy_keywords) and len(holding_codes) < MAX_POSITIONS:
                price = c['close']
                shares = int(pf['cash'] * 0.15 / price / 100) * 100  # 15%仓位，整手
                if shares >= 100 and buy_stock(pf, code, name, price, shares, analysis[:100]):
                    holding_codes.add(code)
                    print(f'  ✅ 模拟买入 {shares}股 @{price:.2f} = {shares*price:,.0f}元')
            else:
                print(f'  ⏸ 观望')
        except Exception as e:
            print(f'  ❌ {e}')
        print()

    # 检查现有持仓
    print(f'📋 检查持仓...')
    market_prices = {}
    for pos in pf['positions']:
        if pos['status'] == 'holding':
            df = get_kline(pos['code'], days=5)
            if df is not None and len(df) > 0:
                market_prices[pos['code']] = float(df['close'].iloc[-1])

    updated = check_positions(pf, market_prices)
    if not updated:
        print(f'  无需操作')

    # 保存
    save_portfolio(pf)

    # 总览
    print(f'\n{"="*60}')
    total_value = pf['cash']
    for p in pf['positions']:
        if p['status'] == 'holding':
            total_value += p.get('current_price', p['buy_price']) * p['shares']
    total_pnl = total_value - INITIAL_CAPITAL
    print(f'💰 现金: {pf["cash"]:,.0f} | 持仓市值: {total_value-pf["cash"]:,.0f} | 总资产: {total_value:,.0f}')
    print(f'📊 累计收益: {total_pnl:+,.0f} ({total_pnl/INITIAL_CAPITAL*100:+.2f}%)')
    print(f'📈 持仓 {len([p for p in pf["positions"] if p["status"]=="holding"])} 只')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()
