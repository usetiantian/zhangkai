# 乾坤·UZI — A股 AI 分析系统
# 数据源：全免费·全国内可用

## 数据源选型（已验证）

| 数据源 | 用途 | 费用 | 速度 | 状态 |
|--------|------|:--:|------|:--:|
| **baostock** | K线数据（8848只股票） | 免费 | 中 | ✅ 已通 |
| **pytdx（同花顺）** | K线+实时行情 | 免费 | 快（800行/秒） | ✅ 已通 |
| **腾讯qt** | 实时报价 | 免费 | 极快（<0.5s） | ✅ 已通 |
| akshare/EastMoney | 财经数据 | 免费 | - | ❌ 被墙 |
| yfinance | 美股数据 | 免费 | - | ❌ 需代理 |

**结论：只用前三。不依赖被墙的API，不依赖国外API。**

## 数据获取策略

```
Level 1: pytdx （主力 — 快、全、TCP直连）
    ↓ 失败
Level 2: baostock （备用 — 免费HTTP API）
    ↓ 失败  
Level 3: 腾讯qt （兜底 — 实时报价）
```

## 网络要求
- pytdx 公网服务器：180.153.18.170:7709 或 119.147.212.81:7709
- baostock：http://baostock.com （HTTP API，无需注册）
- 腾讯qt：http://qt.gtimg.cn （HTTP GET）
- 全部走 TCP/HTTP，无需代理，无需翻墙

## 不依赖的服务
- ❌ 不需要 Redis（去掉）
- ❌ 不需要 Docker
- ❌ 不需要 Celery + RabbitMQ
- ❌ 不需要 yfinance
- ❌ 不需要 akshare
- ❌ 不需要任何外网代理

## 本地模型
- Qwen3-VL-4B 量化版（LM Studio，端口1234）
- 用途：K线图分析、embedding生成、文本总结
- 显存：~3GB（RTX 5080 16GB 绰绰有余）
