# 乾坤 (QianKun) — 数据获取层
# 优先级: baostock → pytdx(同花顺) → 腾讯qt
import baostock as bs
import pandas as pd
import numpy as np
import urllib.request
from datetime import datetime, timedelta

# pytdx 公网服务器
_TDX_HOST = '180.153.18.170'
_TDX_PORT = 7709


def get_stock_list():
    """获取A股列表 (baostock)"""
    bs.login()
    rs = bs.query_stock_basic(code_name='')
    stocks = []
    while rs.next(): stocks.append(rs.get_row_data())
    bs.logout()
    df = pd.DataFrame(stocks, columns=['code','code_name','ipoDate','outDate','type','status'])
    return df[(df['type']=='1') & (df['status']=='1')]


def get_kline(code, days=60):
    """获取日K线 (baostock优先, pytdx备用)"""
    # 尝试 baostock
    try:
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=days+10)).strftime('%Y-%m-%d')
        bs.login()
        rs = bs.query_history_k_data_plus(code, 'date,open,close,high,low,volume',
                                           start_date=start, end_date=end,
                                           frequency='d', adjustflag='2')
        rows = []
        while rs.next(): rows.append(rs.get_row_data())
        bs.logout()
        if len(rows) >= 20:
            df = pd.DataFrame(rows, columns=['date','open','close','high','low','volume'])
            for c in ['open','close','high','low','volume']:
                df[c] = pd.to_numeric(df[c])
            return df
    except Exception:
        pass

    # 备用 pytdx
    return get_kline_pytdx(code, days)


def get_kline_pytdx(code, days=60):
    """同花顺 pytdx K线"""
    try:
        from pytdx.hq import TdxHq_API
        api = TdxHq_API()
        if not api.connect(_TDX_HOST, _TDX_PORT):
            return None

        market = 0 if code.startswith(('0', '3')) else 1
        # 每批拉800条，取最近days条
        bars = api.get_security_bars(9, market, code, 0, min(days+20, 800))
        api.disconnect()

        if not bars or len(bars) < 20:
            return None

        df = pd.DataFrame(bars)
        df = df.rename(columns={'open': 'open', 'close': 'close', 'high': 'high',
                                 'low': 'low', 'vol': 'volume'})
        df['date'] = pd.to_datetime(df[['year','month','day']])
        for c in ['open','close','high','low','volume']:
            df[c] = pd.to_numeric(df[c])
        return df[['date','open','close','high','low','volume']].tail(days)
    except Exception:
        return None


def get_realtime_quote(code):
    """实时报价 (pytdx优先, 腾讯qt备用)"""
    # 尝试 pytdx
    try:
        from pytdx.hq import TdxHq_API
        api = TdxHq_API()
        if api.connect(_TDX_HOST, _TDX_PORT):
            market = 0 if code.startswith(('0', '3')) else 1
            quotes = api.get_security_quotes([(market, code)])
            api.disconnect()
            if quotes and len(quotes) > 0:
                q = quotes[0]
                return {'name': '', 'code': code, 'price': float(q['price']),
                        'open': float(q['open']), 'high': float(q['high']),
                        'low': float(q['low']), 'volume': float(q['vol']),
                        'last_close': float(q['last_close'])}
    except Exception:
        pass

    # 备用 腾讯qt
    try:
        qt_code = f'sh{code}' if code.startswith('6') else f'sz{code}'
        url = f'http://qt.gtimg.cn/q={qt_code}'
        resp = urllib.request.urlopen(url, timeout=5).read().decode('gbk')
        parts = resp.split('~')
        if len(parts) > 5:
            return {'name': parts[1], 'code': parts[2], 'price': float(parts[3]),
                    'change': float(parts[32]) if len(parts) > 32 else 0}
    except Exception:
        pass
    return None
