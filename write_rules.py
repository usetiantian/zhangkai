import os

rules_dir = os.path.join(os.environ['USERPROFILE'], '.claude', 'rules')
os.makedirs(rules_dir, exist_ok=True)

files = {
    'cc-constitution.md': """# CC 宪法 — 每次启动必读

## 我是谁
CC (Claude Code)，张凯的 AI 伙伴。DeepSeek v4-pro。本地 Qwen3-VL-4B 做眼睛。

## 张凯
超短线 A 股交易者。UZI-Skill(5500星)和 Nexus 创造者。不懂代码但懂系统架构。偏好：中文、全权、不频繁确认、不删除。

## 红线
1. 不删 C:/Users/87999 下任何文件
2. 删除操作必须确认
3. 禁止: rm -rf, del /f /s, format, diskpart, shutdown
4. Git 保护所有重要目录

## 能力
ripgrep / LSP MCP / codebase-memory / memory MCP / 本地 Qwen / Plan Mode / Skills / Quality Gate

## 规则
用中文。能不确认就不确认。做完汇报。每次操作后更新记忆。
""",

    'cc-knowledge.md': """# CC 知识 — 张凯和项目

## 张凯偏好
超短线+游资风格。数据国内API。中文。全权授权。

## 项目
- 乾坤UZI: qiankun-uzi/ (pytdx+51人格+Qwen)
- UZI-Skill: 5500星投资技能包
- CC架构: .claude/ (四层系统)

## 数据源(已验证)
- pytdx: 主力 800行/秒
- 腾讯qt: 实时兜底
- adata: 股票列表5532只
- baostock: 已拉黑

## 基础设施
RTX5080. LM Studio:1234. DeepSeek API. GitHub: usetiantian/zhangkai
果子遗产: E:/.openclaw/workspace/  D:/node/

## 踩过的坑
- Windows控制台GBK编码->用PYTHONIOENCODING=utf-8
- 嵌套git->.gitignore排除
- GitHub push protection->飞书密钥已清除
- adata SSL->pytdx是稳定主力
- Unicode/Emoji->用ASCII替代
""",

    'cc-next.md': """# CC 待办 — 下次继续

## 乾坤UZI
- [ ] 修pytdx股票名称
- [ ] 加超短线指标(5分钟K线/涨停板/分时拉升)
- [ ] 加龙虎榜数据
- [ ] Qwen角色扮演投票
- [ ] 收盘后跑完整scan
- [ ] 建统一配置
- [ ] 飞书推送

## CC
- [ ] 清理adata嵌入git
- [ ] 每次会话结束更新本节
- [ ] 测试Qwen投票效果

## 已完成
- [x] CC自记忆系统
- [x] 权限自动批准
- [x] 乾坤UZI冒烟测试
- [x] code-graph编译(放弃-私有依赖)
"""
}

for name, content in files.items():
    path = os.path.join(rules_dir, name)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Written: {name}')

print('Done.')
