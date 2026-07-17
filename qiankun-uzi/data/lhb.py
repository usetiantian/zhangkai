"""
龙虎榜数据模块
数据源：新浪财经 vLHBData（免费、国内可用）
每日收盘后更新，提供上榜个股统计
"""

import urllib.request, re, logging
from datetime import datetime

logger = logging.getLogger("qiankun.lhb")

SINA_LHB = "https://vip.stock.finance.sina.com.cn/q/go.php/vLHBData/kind/ggtj/index.phtml"


def _parse_sina_lhb_page(html: str) -> list:
    """解析新浪龙虎榜个股统计页面"""
    results = []
    # 找数据行: <tr>...<td>CODE</td>...<td>NAME</td>...<td>买入</td>...
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)

    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        clean = []
        for c in cells:
            text = re.sub(r'<[^>]+>', '', c).strip()
            text = re.sub(r'\s+', '', text)
            if text:
                clean.append(text)

        if len(clean) < 6:
            continue
        # 第一列必须是6位数字代码
        if not re.match(r'^\d{6}$', clean[0]):
            continue

        try:
            results.append({
                "code": clean[0],
                "name": clean[1],
                "on_board_count": int(clean[2]) if len(clean) > 2 else 1,
                "buy_amount": float(clean[3]) if len(clean) > 3 else 0,   # 万元
                "sell_amount": float(clean[4]) if len(clean) > 4 else 0,  # 万元
                "net_amount": float(clean[5]) if len(clean) > 5 else 0,   # 万元
                "buy_seats": int(clean[6]) if len(clean) > 6 else 0,
                "sell_seats": int(clean[7]) if len(clean) > 7 else 0,
            })
        except (ValueError, IndexError):
            continue

    return results


def get_lhb_list() -> list:
    """
    获取龙虎榜上榜股票列表（最近统计周期）
    返回: [{code, name, buy_amount(万元), sell_amount(万元), net_amount(万元), ...}]
    """
    all_data = []
    for page in [1, 2, 3]:
        url = f"{SINA_LHB}?p={page}"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://vip.stock.finance.sina.com.cn/",
            })
            resp = urllib.request.urlopen(req, timeout=10)
            html = resp.read().decode("gbk", errors="ignore")
            page_data = _parse_sina_lhb_page(html)
            if not page_data:
                break
            all_data.extend(page_data)
            if len(page_data) < 40:  # 最后一页
                break
        except Exception as e:
            logger.warning(f"新浪龙虎榜第{page}页失败: {e}")
            break

    logger.info(f"龙虎榜获取: {len(all_data)}条")

    # 保存为手机App用的最新数据
    import os, json
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "latest_lhb.json"), "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False)

    return all_data


def get_top_net_buy(top_n: int = 20) -> list:
    """获取净买入最多的N只股票"""
    return sorted(get_lhb_list(), key=lambda x: x["net_amount"], reverse=True)[:top_n]


def get_top_net_sell(top_n: int = 20) -> list:
    """获取净卖出最多的N只股票"""
    return sorted(get_lhb_list(), key=lambda x: x["net_amount"])[:top_n]


def get_lhb_for_code(code: str, lhb_list: list = None) -> dict:
    """查询某只股票是否在龙虎榜上"""
    if lhb_list is None:
        lhb_list = get_lhb_list()
    code = str(code).zfill(6)
    for item in lhb_list:
        if item["code"] == code:
            return item
    return None


def analyze_lhb_signal(item: dict) -> dict:
    """
    分析龙虎榜信号强度（游资视角）
    """
    net = item.get("net_amount", 0)   # 万元
    buy = item.get("buy_amount", 0)
    sell = item.get("sell_amount", 0)
    total = buy + sell

    if total <= 0:
        return {"signal": "无", "score": 0, "reason": "无交易数据"}

    buy_ratio = buy / total * 100
    score = 0
    reasons = []

    # 净买入
    if net > 10000:       # >1亿
        score += 5
        reasons.append(f"净买入{net/10000:.1f}亿")
    elif net > 5000:
        score += 3
        reasons.append(f"净买入{net/10000:.2f}亿")
    elif net > 1000:
        score += 2
        reasons.append(f"净买入{net/10000:.2f}亿")
    elif net > 0:
        score += 1

    # 买方主导
    if buy_ratio > 70:
        score += 3
        reasons.append("买方主导")
    elif buy_ratio > 55:
        score += 1

    # 上榜次数多 = 持续关注
    count = item.get("on_board_count", 1)
    if count >= 3:
        score += 2
        reasons.append(f"连续{count}天上榜")

    if score >= 6:
        signal = "STRONG"
    elif score >= 3:
        signal = "GOOD"
    elif score >= 1:
        signal = "WATCH"
    else:
        signal = "WEAK"

    return {
        "signal": signal,
        "score": score,
        "reason": "; ".join(reasons),
        "net_amount": net,
        "buy_ratio": round(buy_ratio, 1),
    }


def print_lhb_summary(top_n: int = 15):
    """打印龙虎榜概览"""
    print(f"\n  {'='*75}")
    print(f"  龙虎榜概览 ({datetime.now().strftime('%Y-%m-%d')})  数据: 新浪财经")
    print(f"  {'='*75}")

    lhb_list = get_lhb_list()
    print(f"  上榜股票: {len(lhb_list)}只\n")

    top_buy = sorted(lhb_list, key=lambda x: x["net_amount"], reverse=True)[:top_n]
    print(f"  --- 净买入 Top {top_n} ---")
    print(f"  {'代码':<10} {'名称':<8} {'净买入(万)':<14} {'买入比':<8} {'上榜':<6} {'信号'}")
    print(f"  {'-'*60}")
    for item in top_buy:
        sig = analyze_lhb_signal(item)
        net_wan = item["net_amount"]
        total = item["buy_amount"] + item["sell_amount"]
        buy_ratio = item["buy_amount"] / total * 100 if total > 0 else 0
        count = item.get("on_board_count", 1)
        sig_str = {"STRONG": "[BUY]", "GOOD": "[++]", "WATCH": "[+]", "WEAK": "[-]"}.get(sig["signal"], "?")
        print(f"  {item['code']:<10} {item['name']:<8} {net_wan:>+12.0f}  {buy_ratio:>5.1f}%   {count}天    {sig_str} {sig['reason'][:25]}")

    print(f"\n  --- 净卖出 Top 5 ---")
    top_sell = sorted(lhb_list, key=lambda x: x["net_amount"])[:5]
    for item in top_sell:
        print(f"  {item['code']} {item['name']}  净卖出 {item['net_amount']:+.0f}万  买入{item['buy_amount']:.0f}万 卖出{item['sell_amount']:.0f}万")
    print()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print_lhb_summary()
