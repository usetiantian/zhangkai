"""乾坤 OHLCV 数据服务 — 独立进程，通过 HTTP 提供 K 线数据。
绕过 FastAPI asyncio 线程池限制，直接走 pytdx TCP。
启动: python ohlcv_server.py --port 8001
"""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pytdx.hq import TdxHq_API
import pandas as pd

TDX_HOST = '180.153.18.170'
TDX_PORT = 7709


def get_ohlcv(symbol: str):
    """拉取日K线"""
    mkt = 0 if symbol.startswith(('0', '3')) else 1
    api = TdxHq_API()
    try:
        if not api.connect(TDX_HOST, TDX_PORT):
            return None
        bars = api.get_security_bars(9, mkt, symbol, 0, 800)
        if not bars or len(bars) < 5:
            return None
        df = pd.DataFrame(bars)
        df['date'] = pd.to_datetime(df[['year', 'month', 'day']]).dt.strftime('%Y-%m-%d')
        result = []
        for _, row in df.iterrows():
            result.append({
                'date': str(row['date']),
                'open': float(row['open']),
                'close': float(row['close']),
                'high': float(row['high']),
                'low': float(row['low']),
                'volume': int(row['vol']),
            })
        return result
    finally:
        api.disconnect()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/health':
            self.send_json({'status': 'ok'})
        elif path.startswith('/ohlcv/'):
            symbol = path.split('/')[-1]
            data = get_ohlcv(symbol)
            if data:
                self.send_json(data)
            else:
                self.send_error(404, f'No data for {symbol}')
        else:
            self.send_error(404)

    def send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # silent


if __name__ == '__main__':
    port = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == '--port' else 8001
    server = HTTPServer(('127.0.0.1', port), Handler)
    print(f'OHLCV server on port {port}')
    server.serve_forever()
