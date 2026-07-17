"""
乾坤·UZI 数据层 — 全免费·全国内可用
三级降级：pytdx → baostock → 腾讯qt
"""

import time, logging
from typing import Optional

logger = logging.getLogger("qiankun.data")

# ═══════════════════════════════════════════
# Level 1: pytdx（同花顺 TCP直连，最快）
# ═══════════════════════════════════════════

PYTDX_SERVERS = [
    ("180.153.18.170", 7709),
    ("119.147.212.81", 7709),
    ("123.125.218.42", 7709),
]

class PyTdxSource:
    """同花顺 pytdx — TCP直连，800行/秒"""
    
    def __init__(self):
        self.api = None
        self._connected = False

    def _connect(self):
        if self._connected:
            return True
        try:
            from pytdx.hq import TdxHq_API
            self.api = TdxHq_API()
            for host, port in PYTDX_SERVERS:
                try:
                    if self.api.connect(host, port):
                        self._connected = True
                        logger.info(f"pytdx已连接: {host}:{port}")
                        return True
                except Exception:
                    continue
            logger.warning("pytdx所有服务器连接失败")
        except ImportError:
            logger.warning("pytdx未安装: pip install pytdx")
        return False

    def get_kline(self, code: str, market: int = 0, days: int = 60):
        """获取日K线数据"""
        if not self._connect():
            return None
        try:
            data = self.api.get_security_bars(
                9, market, code, 0, days
            )
            if data:
                return [{
                    "date": str(row["datetime"])[:10],
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["vol"],
                    "amount": row["amount"],
                } for row in data]
        except Exception as e:
            logger.warning(f"pytdx获取K线失败 {code}: {e}")
        return None

    def get_realtime(self, code: str, market: int = 0):
        """获取实时报价"""
        if not self._connect():
            return None
        try:
            from pytdx.hq import TdxHq_API
            data = self.api.get_security_quotes([(market, code)])
            if data:
                row = data[0]
                # pytdx 字段名可能是 name 或 其他，尝试多个
                name = row.get("name", "") or row.get("NAME", "") or ""
                if not name:
                    # 用股票列表反查名称
                    all_fields = dir(row) if hasattr(row, '__dict__') else []
                    for f in all_fields:
                        if not f.startswith('_'):
                            val = getattr(row, f, '')
                            if isinstance(val, str) and len(val) > 1 and len(val) < 10 and '一' <= val[0] <= '鿿':
                                name = val
                                break
                return {
                    "code": code,
                    "name": name,
                    "price": row.get("price", 0) or row.get("last_close", 0),
                    "open": row.get("open", 0),
                    "high": row.get("high", 0),
                    "low": row.get("low", 0),
                    "pre_close": row.get("last_close", 0) or row.get("pre_close", 0),
                    "volume": row.get("vol", 0) or row.get("volume", 0),
                    "amount": row.get("amount", 0),
                    "change_pct": round(
                        ((row.get("price", 0) or row.get("last_close", 1)) - (row.get("last_close", 1) or row.get("pre_close", 1)))
                        / (row.get("last_close", 1) or row.get("pre_close", 1)) * 100, 2
                    ) if (row.get("last_close", 0) or row.get("pre_close", 0)) > 0 else 0,
                }
        except Exception as e:
            logger.warning(f"pytdx实时报价失败 {code}: {e}")
        return None

    def get_stock_list(self, market: int = 0):
        """获取股票列表"""
        if not self._connect():
            return None
        try:
            data = self.api.get_security_list(market, 0)
            return [(row["code"], row["name"]) for row in data] if data else None
        except Exception as e:
            logger.warning(f"pytdx获取股票列表失败: {e}")
        return None

    def get_intraday(self, code: str, market: int = 0, period: int = 5):
        """获取5分钟K线（超短线核心数据）"""
        if not self._connect():
            return None
        try:
            # category=4 是5分钟线
            data = self.api.get_security_bars(
                4, market, code, 0, 48  # 48根5分钟线 = 4小时交易时间
            )
            if data:
                return [{
                    "time": str(row["datetime"]),
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["vol"],
                } for row in data]
        except Exception as e:
            logger.debug(f"pytdx5分钟线失败 {code}: {e}")
        return None

    def close(self):
        if self.api:
            try:
                self.api.disconnect()
            except Exception:
                pass
            self._connected = False


# ═══════════════════════════════════════════
# Level 2: baostock（免费HTTP API）
# ═══════════════════════════════════════════

class BaoStockSource:
    """baostock — 免费HTTP，8848只股票，无需注册"""
    
    def __init__(self):
        self._login = False

    def _ensure_login(self):
        if self._login:
            return True
        try:
            import baostock as bs
            lg = bs.login()
            if lg.error_code == '0':
                self._login = True
                return True
            logger.warning(f"baostock登录失败: {lg.error_msg}")
        except ImportError:
            logger.warning("baostock未安装: pip install baostock")
        except Exception as e:
            logger.warning(f"baostock连接失败: {e}")
        return False

    def _format_code(self, code: str) -> str:
        """格式化股票代码：002185 → sz.002185"""
        code = code.strip().replace(".", "")
        if code.startswith(("6", "9")):
            return f"sh.{code}"
        elif code.startswith(("0", "2", "3")):
            return f"sz.{code}"
        elif code.startswith(("4", "8")):
            return f"bj.{code}"
        return code

    def get_kline(self, code: str, days: int = 60):
        """获取日K线"""
        if not self._ensure_login():
            return None
        try:
            import baostock as bs
            bs_code = self._format_code(code)
            end_date = time.strftime("%Y-%m-%d")
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume,amount",
                start_date='',
                end_date=end_date,
                frequency="d",
                adjustflag="2"  # 前复权
            )
            if rs.error_code != '0':
                return None
            result = []
            while rs.next():
                row = rs.get_row_data()
                result.append({
                    "date": row[0],
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": int(row[5]),
                    "amount": float(row[6]),
                })
            return result[-days:]
        except Exception as e:
            logger.warning(f"baostock K线失败 {code}: {e}")
        return None

    def get_stock_list(self):
        """获取全A股列表"""
        if not self._ensure_login():
            return None
        try:
            import baostock as bs
            rs = bs.query_stock_basic()
            if rs.error_code != '0':
                return None
            stocks = []
            while rs.next():
                row = rs.get_row_data()
                stocks.append({
                    "code": row[0],
                    "name": row[1],
                    "ipo_date": row[2],
                    "type": row[3],
                })
            return stocks
        except Exception as e:
            logger.warning(f"baostock股票列表失败: {e}")
        return None

    def logout(self):
        try:
            import baostock as bs
            bs.logout()
        except Exception:
            pass
        self._login = False


# ═══════════════════════════════════════════
# Level 3: 腾讯qt（免费实时报价）
# ═══════════════════════════════════════════

class TencentQtSource:
    """腾讯qt — HTTP GET，极快（<0.5s），实时报价"""
    
    @staticmethod
    def _format_code(code: str) -> str:
        """格式化：002185 → sz002185"""
        code = code.strip()
        if code.startswith(("6", "9")):
            return f"sh{code}"
        elif code.startswith(("0", "2", "3")):
            return f"sz{code}"
        elif code.startswith(("4", "8")):
            return f"bj{code}"
        return code

    def get_realtime(self, codes: list) -> dict:
        """批量获取实时报价"""
        import urllib.request
        qt_codes = [self._format_code(c) for c in codes]
        url = f"http://qt.gtimg.cn/q={','.join(qt_codes)}"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "http://finance.qq.com",
            })
            resp = urllib.request.urlopen(req, timeout=5)
            text = resp.read().decode("gbk")
            return self._parse(text)
        except Exception as e:
            logger.warning(f"腾讯qt请求失败: {e}")
        return {}

    def _parse(self, text: str) -> dict:
        """解析腾讯qt返回"""
        result = {}
        for line in text.strip().split("\n"):
            if '="' not in line:
                continue
            code_raw = line.split("=")[0].replace("v_", "")
            data = line.split('="')[1].strip('";\n').split("~")
            if len(data) < 40:
                continue
            try:
                result[code_raw] = {
                    "name": data[1],
                    "code": data[2],
                    "price": float(data[3]) if data[3] else 0,
                    "pre_close": float(data[4]) if data[4] else 0,
                    "open": float(data[5]) if data[5] else 0,
                    "volume": int(data[6]) if data[6] else 0,
                    "high": float(data[33]) if data[33] else 0,
                    "low": float(data[34]) if data[34] else 0,
                    "amount": float(data[37]) if data[37] else 0,
                    "change_pct": float(data[32]) if data[32] else 0,
                }
            except (ValueError, IndexError):
                continue
        return result


# ═══════════════════════════════════════════
# 统一接口：三级降级
# ═══════════════════════════════════════════

class DataFetcher:
    """数据获取统一入口 — 三级自动降级"""

    def __init__(self):
        self.pytdx = PyTdxSource()
        self.baostock = BaoStockSource()
        self.tencent = TencentQtSource()

    def get_kline(self, code: str, days: int = 60):
        """获取K线 — pytdx → baostock 降级"""
        # Level 1: pytdx
        data = self.pytdx.get_kline(code, days=days)
        if data:
            logger.info(f"{code} K线: pytdx {len(data)}条")
            return data
        
        # Level 2: baostock
        data = self.baostock.get_kline(code, days=days)
        if data:
            logger.info(f"{code} K线: baostock {len(data)}条")
        return data

    def get_realtime(self, code: str):
        """获取实时报价 — pytdx → 腾讯qt 降级"""
        result = self.pytdx.get_realtime(code)
        if result:
            return result
        
        result = self.tencent.get_realtime([code])
        if result:
            key = list(result.keys())[0]
            return result[key]
        return None

    def get_stock_list(self):
        """获取股票列表"""
        stocks = self.pytdx.get_stock_list()
        if stocks:
            return stocks
        data = self.baostock.get_stock_list()
        if data:
            return [(s["code"], s["name"]) for s in data]
        return None

    def close(self):
        self.pytdx.close()
        self.baostock.logout()


# ═══════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    fetcher = DataFetcher()
    
    print("=== K线测试 ===")
    kline = fetcher.get_kline("002185", days=5)
    if kline:
        for k in kline[-3:]:
            print(f"  {k['date']} O:{k['open']} H:{k['high']} L:{k['low']} C:{k['close']} V:{k['volume']}")
    
    print("\n=== 实时报价测试 ===")
    rt = fetcher.get_realtime("002185")
    if rt:
        print(f"  {rt.get('name','')} 现价:{rt.get('price')} 涨跌:{rt.get('change_pct')}%")
    
    fetcher.close()
