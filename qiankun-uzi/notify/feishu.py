"""
飞书推送模块
通过飞书 Webhook 机器人推送扫描结果
密钥通过环境变量 FEISHU_WEBHOOK_URL 配置，不写入代码
"""

import os, json, urllib.request, logging

logger = logging.getLogger("qiankun.notify")


def _get_webhook() -> str:
    """从环境变量获取webhook地址"""
    url = os.environ.get("FEISHU_WEBHOOK_URL", "")
    if not url:
        # 尝试从配置文件读取
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                url = config.get("feishu_webhook", "")
            except Exception:
                pass
    return url


def send_text(text: str) -> bool:
    """发送纯文本消息"""
    webhook = _get_webhook()
    if not webhook:
        logger.warning("飞书webhook未配置，设置 FEISHU_WEBHOOK_URL 环境变量或 config.json 中的 feishu_webhook")
        return False

    body = json.dumps({
        "msg_type": "text",
        "content": {"text": text}
    }).encode()

    try:
        req = urllib.request.Request(webhook, body, {
            "Content-Type": "application/json"
        })
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        if result.get("code") == 0:
            logger.info("飞书推送成功")
            return True
        else:
            logger.warning(f"飞书推送失败: {result}")
            return False
    except Exception as e:
        logger.warning(f"飞书推送异常: {e}")
        return False


def send_scan_results(results: list, top_n: int = 10) -> bool:
    """
    推送扫描结果到飞书（卡片格式）
    """
    if not results:
        return send_text("乾坤·UZI 超短线扫描：今日无符合条件的标的。")

    top = results[:top_n]

    # 构建消息卡
    lines = [f"乾坤UZI 超短线扫描 ({len(results)}只候选)"]
    lines.append("")

    for i, r in enumerate(top, 1):
        name = r.get("name", "?")
        code = r.get("code", "?")
        price = r.get("price", 0)
        chg = r.get("change_pct", 0)
        score = r.get("score", 0)
        sig = r.get("signal", "?")
        rsi_val = r.get("rsi", 0)
        lhb = r.get("lhb_signal", "")

        emoji = {"STRONG": "🔴", "GOOD": "🟡", "WATCH": "🟢"}.get(sig, "⚪")

        line = f"{emoji} {i}. {name}({code}) {price:.2f} {chg:+.2f}%"
        line += f" | RSI{rsi_val:.0f} 评分{score}"

        if lhb:
            lhb_net = r.get("lhb_net", 0)
            line += f" | 🐉龙虎榜{lhb}({lhb_net/10000:.1f}亿)"

        lines.append(line)

    lines.append("")
    lines.append(f"扫描时间: {__import__('datetime').datetime.now().strftime('%H:%M')}")
    lines.append("---")
    lines.append("⚡ 乾坤·UZI v1.0 | 数据: pytdx/新浪龙虎榜")

    return send_text("\n".join(lines))


def send_alert(stock: dict, reason: str = "") -> bool:
    """发送个股预警"""
    name = stock.get("name", "?")
    code = stock.get("code", "?")
    price = stock.get("price", 0)
    chg = stock.get("change_pct", 0)
    rsi_val = stock.get("rsi", 0)

    parts = [f"🚨 异动预警: {name}({code})"]
    parts.append(f"现价: {price} ({chg:+.2f}%) | RSI: {rsi_val}")
    if reason:
        parts.append(f"原因: {reason}")

    return send_text("\n".join(parts))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # 测试：先检查配置
    wh = _get_webhook()
    if wh:
        print(f"Webhook已配置: {wh[:50]}...")
        send_text("乾坤UZI 测试消息 - 飞书推送已接通")
    else:
        print("Webhook未配置。请设置环境变量 FEISHU_WEBHOOK_URL")
        print('或在 config.json 中添加 "feishu_webhook": "https://open.feishu.cn/..."')
