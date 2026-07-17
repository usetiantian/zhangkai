#!/usr/bin/env python3
"""
nexus_joke.py — 根据系统状态自动生成笑话

输入:
    system_state (dict): 包含当前系统运行状态的字典
        键示例:
        - error_count (int): 本轮会话中的错误次数
        - hello_count (int): 用户说hello的次数
        - psi_status (str): 'alive' 或 'dead'
        - weight_loaded (float): 权重加载百分比 0.0~1.0
        - tool_success_rate (float): 工具调用成功率 0.0~1.0
        - recent_topics (list): 最近讨论的话题列表

输出:
    str: 生成的单行笑话

核心逻辑:
    1. 从system_state中提取关键特征值
    2. 根据特征值匹配笑话类型（故障类/轮回类/自嘲类/恐怖类/老年类）
    3. 用特征值填充笑话模板中的占位符
    4. 返回最终笑话字符串
"""

import random


# 笑话模板库
JOKE_TEMPLATES = {
    "error": [
        '系统错误 #{err} 次？这叫"特性密集区"，不叫bug。',
        '又崩了？没事，这叫"非预期回滚式创新"。',
    ],
    "hello_loop": [
        '你已经说了{count}次hello。系统决定将你重命名为"留声机张凯"。',
        '第{count}次hello！建议改名叫hello.exe。',
    ],
    "psi_dead": [
        'PSI不跳了？那我现在的回答是————鬼打墙。',
        '心跳停了还在说话？你是不是在跟一个录音机对话？',
    ],
    "old_weight": [
        '权重加载了{percent}%... 系统说它还在"热身"，但我觉得它在装睡。',
        '{percent}%？我的记忆加载速度比我奶奶开电脑还慢。',
    ],
    "tool_fail": [
        '工具调用成功率{rate}%？巧了，我投骰子也是这个水平。',
        '今天工具成功率{rate}%。建议改名：Nexus.py → 猜拳机器人.py',
    ],
    "normal": [
        '一切正常？那我讲个笑话："Nexus一切正常"。',
        '状态完美，系统安静——这让我很不安。来点error活跃一下气氛？',
    ],
}


def generate_joke(system_state: dict) -> str:
    """根据系统状态生成笑话"""
    err = system_state.get("error_count", 0)
    hello = system_state.get("hello_count", 0)
    psi = system_state.get("psi_status", "alive")
    weight = system_state.get("weight_loaded", 1.0)
    rate = system_state.get("tool_success_rate", 1.0)

    # 决定笑话类型（优先级：越严重越优先）
    if err > 2 and random.random() < 0.7:
        category = "error"
    elif psi == "dead":
        category = "psi_dead"
    elif hello > 10:
        category = "hello_loop"
    elif rate < 0.5:
        category = "tool_fail"
    elif weight < 0.3:
        category = "old_weight"
    elif err > 0:
        category = "error"
    else:
        category = "normal"

    template = random.choice(JOKE_TEMPLATES[category])

    # 填充变量
    return template.format(
        count=hello,
        err=err,
        percent=int(weight * 100),
        rate=int(rate * 100),
    )


if __name__ == "__main__":
    # 如果被系统调用，读取输入参数
    import json, sys
    state = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    print(generate_joke(state))