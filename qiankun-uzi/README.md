# 乾坤·UZI v1.0 — A股 AI 分析系统

> 全免费·全国内可用·超短线专用
> 数据: pytdx + 新浪龙虎榜 | AI: Qwen3-VL-4B 本地 | 陪审团: 51位投资大师

---

## 快速开始

```bash
# 安装依赖
pip install pytdx baostock pyyaml

# 确保 LM Studio 运行中（可选，用于AI分析）
# 端口: 127.0.0.1:1234

# 分析单只股票
python main.py 002185                # 完整分析（AI+陪审团）
python main.py 002185 --fast         # 快速模式（跳过AI）
python main.py 002185 --compare      # 对比模式（Qwen vs 简易规则）

# 全市场扫描
python main.py scan                  # 扫描 300 只超短线候选
python main.py scan --lhb            # 扫描 + 龙虎榜加成
python main.py scan --notify         # 扫描 + 飞书推送
python main.py scan --lhb --notify   # 全部组合

# 独立功能
python main.py lhb                   # 查看龙虎榜净买入排行
python main.py config                # 查看/修改配置
python main.py config set scan_limit 800  # 修改扫描数量
```

---

## 功能清单

### 1. 数据分析 (`main.py 002185`)
- 实时行情 + 60日日K线
- 技术指标：RSI(14)、MA5/MA20、量比、近期趋势
- 涨停/跌停自动检测（自动识别主板10%/科创20%/北交30%）
- 5分钟K线日内分析：分时拉升、跳水、放量异动

### 2. AI分析 (`brain/qwen.py`)
- Qwen3-VL-4B 本地模型（LM Studio）
- 给出趋势判断、操作建议、100字研判
- AI不可用时自动跳过，不影响其他功能

### 3. 投资人格陪审团 (`pipeline/panel.py`)
- 51位投资大师（巴菲特→赵老哥）
- 每组选出代表投票：买入/持有/卖出
- 两种模式：
  - **Qwen模式**（默认）：每人角色扮演，AI给出个性化理由
  - **简易模式**（离线降级）：根据RSI+流派规则机械投票
- `--compare` 可同时运行两种模式并对比

### 4. 龙虎榜 (`data/lhb.py`)
- 数据源：新浪财经（免费、国内可用）
- 120只上榜个股 + 净买入/卖出统计
- 游资信号评分：净买入额 + 买方比例 + 上榜天数
- `scan --lhb` 扫描时龙虎榜信号自动加分

### 5. 飞书推送 (`notify/feishu.py`)
- 扫描结果推送到飞书群
- 支持卡片格式和预警消息
- 密钥通过环境变量配置，不写入代码

### 6. 配置管理 (`main.py config`)
- 可配置项：扫描数量、RSI阈值、量比门槛、最低评分
- 配置文件 `config.json`（不进入git）

---

## 命令行参考

```
python main.py 002185          分析华天科技（AI+陪审团+报告）
python main.py 002185 --fast   快速模式（不调AI）
python main.py 002185 --compare 对比模式（Qwen vs 简易投票）
python main.py scan            扫描超卖股票（300只）
python main.py scan --lhb      扫描+龙虎榜加成
python main.py scan --notify   扫描+飞书推送
python main.py lhb             查看龙虎榜净买入Top15
python main.py config          查看配置
python main.py config set <key> <value>  修改配置
```

---

## 项目结构

```
qiankun-uzi/
├── main.py              # 统一入口
├── data/
│   ├── fetcher.py       # pytdx → baostock → 腾讯qt 四级降级
│   └── lhb.py           # 新浪龙虎榜 + 游资信号评分
├── brain/
│   └── qwen.py          # Qwen3-VL-4B 本地AI接口
├── pipeline/
│   └── panel.py         # 51位投资大师陪审团
├── notify/
│   └── feishu.py        # 飞书Webhook推送
├── personas/            # 51个YAML投资人格文件
├── output/              # HTML报告 + JSON扫描结果
├── start.bat            # Windows双击启动
├── config.json          # 用户配置（不入git）
└── requirements.txt     # pip依赖
```

---

## 环境要求

| 组件 | 说明 | 必须 |
|------|------|:--:|
| Python 3.10+ | 运行环境 | ✅ |
| pytdx | 同花顺TCP数据（K线+实时行情） | ✅ |
| pyyaml | 投资人格文件解析 | ✅ |
| baostock | K线备用数据源 | ⚠️ |
| LM Studio + Qwen3-VL-4B | 本地AI分析 | ⚠️ |
| 飞书Webhook | 推送通知 | ⚠️ |

### 飞书推送配置

```bash
# 方式1: 环境变量
set FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx

# 方式2: config.json
{
  "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
}
```

---

## 数据源策略

```
实时报价:  pytdx → 腾讯qt（自动降级）
K线数据:   pytdx → baostock（自动降级）
股票名称:  本地缓存 + 腾讯qt兜底（解决pytdx名称丢失）
龙虎榜:    新浪财经 vLHBData（免费、国内可用）
股票列表:  adata(5532只) → pytdx(1000只)
```

---

## 扫描信号说明

| 信号 | 评分 | 含义 |
|:--:|:--:|------|
| [BUY] STRONG | ≥7 | 强烈关注 |
| [++] GOOD | ≥5 | 值得关注 |
| [+] WATCH | ≥3 | 保持观察 |

**评分因素**: RSI(1-3分) + 量比(2-3分) + 涨跌幅(1-2分) + 分时拉升(2分) + 放量异动(1分) + 龙虎榜(1-5分)

---

## 注意事项

1. **收盘后扫描最有效**：盘中数据波动大，15:00后数据稳定
2. **LM Studio离线不影响基本功能**：陪审团自动降级为简易规则
3. **飞书密钥不要写入代码**：用环境变量或config.json
4. **config.json不进git**：已在.gitignore中排除
5. **首次运行较慢**：adata需要下载股票列表缓存
6. **Windows控制台中文字符显示问题**：用 `PYTHONIOENCODING=utf-8` 或查看HTML报告

---

## 更新日志

### v1.0 (2026-07-17)
- 数据分析：pytdx K线+实时行情
- 超短线指标：涨停/跌停检测、5分钟K线分析、分时拉升
- AI分析：Qwen3-VL-4B 本地模型
- 陪审团：51位投资人格 + Qwen角色扮演投票
- 龙虎榜：新浪数据源 + 游资信号评分
- 飞书推送：Webhook通知
- 统一配置：config + main.py config
- HTML报告生成

---

> 乾坤在手，UZI冲锋。数据为矛，AI为盾。
