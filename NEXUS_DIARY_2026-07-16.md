# 乾坤工作日记 — 2026-07-16/17

## 今日主题：从 Nexus 到乾坤——A 股 AI 分析平台落地

---

## 一、Nexus 收尾

Nexus 网关发现三个核心 bug：
- heartbeat_loop 内 5 处 `import asyncio` 遮蔽 Python 3.12 的模块引用，导致每 60 秒 tick 崩溃
- cognitive_loop 永久卡在 "reflect" 决策，Sentinel 检测到停滞→切换策略→仍然停滞→自激振荡
- Dashboard agent_status 报错，HeartbeatLoop 缺 get_status()

修复：删 5 处 asyncio 遮蔽、加 reflect 死锁逃逸+explore handler、加 get_status()。

清理了 experience DB 中 1500+ 条垃圾数据（"How to handle" 模式），重复任务从 50 次/重启降到 2 次。

---

## 二、数据源探索

测试了三层数据获取：

| 数据源 | 状态 | 说明 |
|--------|:--:|------|
| baostock | ✅ | 免费，8848 只股票 K 线，直接调用可用 |
| pytdx（同花顺） | ✅ | 公网 180.153.18.170:7709，TCP 连接，800 行/秒 |
| 腾讯 qt | ✅ | 实时报价，<0.5s |
| akshare/EastMoney | ❌ | 被墙，项目原有数据源 |

pytdx 作为主力数据源，写入 `ashare-ai-analyst/src/data/fetcher.py`，跳过缓存和 source_router。

---

## 三、Qwen3-VL-4B 本地推理

通过 LM Studio（端口 1234）加载 Qwen3-VL-4B（Q4_K_M 量化，4B 参数）：
- K 线图分析：matplotlib 画图 → base64 编码 → Qwen 看图 → 给出支撑/压力/趋势
- 文本分析：喂 baostock 真实 K 线数据，输出技术分析
- 对比：Qwen3-VL-4B 比 Nexus 里的 Qwen2-VL-2B 强太多——不再幻觉日期，能给出具体价格点位

---

## 四、ashare-ai-analyst 项目

### 代码检测
- 436 个 Python 模块，468 个编译通过，410 个直接 import 可用
- 缺 3 个外部依赖（anthropic/discord/fastapi），已安装
- 前端 React 19 + Vite，后端 FastAPI 200+ 接口

### 跑通的功能
- Web UI：`http://127.0.0.1:5173`（后用 3000 端口）
- 股票查询：002185 华天科技 20.80 元 ✅
- AI 分析：Qwen 给出 bearish 判断 ✅
- 大盘指数、持仓管理、Agent 状态、市场周期、推荐选股 ✅

### 未完全跑通
- OHLCV K 线图端点：数据链路通（pytdx→fetcher 800 行），FastAPI asyncio 线程池阻塞导致接口超时
- 独立 OHLCV 服务（ohlcv_server.py）已写好，端口 8001，单独可用
- Celery 自动化：Redis 协议不兼容（Windows 5.0 不支持 RESP3），已降级 redis-py

---

## 五、Redis 安装

下载 Redis-x64 5.0.14.1（ghproxy 镜像），运行在 6379 端口。
Python 客户端降级到 redis<5 兼容 RESP2 协议。
配置 hosts 文件 `127.0.0.1 redis` 解决 Docker 主机名映射。

---

## 六、LLM 接入

ashare-ai-analyst 原有 Claude/Gemini/DeepSeek 多模型路由。
新增 Qwen provider（`src/llm/qwen.py`），注册到 ProviderName 枚举和 router。
配置改为 Qwen 优先，其他 provider 关闭。
经 FastAPI `/api/v1/stock/002185/quick-insight` 验证通过。

---

## 七、文件变更

| 文件 | 变更 |
|------|------|
| `src/data/fetcher.py` | 新增 pytdx 作为第一数据源 |
| `src/llm/qwen.py` | 新建 Qwen provider |
| `src/llm/base.py` | ProviderName 枚举加 QWEN |
| `src/llm/router.py` | 路由加 Qwen 分支 |
| `src/web/dependencies.py` | QlibAdapter 改为真正单例 |
| `config/llm.yaml` | 新增 qwen provider 配置 |
| `config/stocks.yaml` | 数据源优先 baostock |
| `ohlcv_server.py` | 新建独立 OHLCV 服务 |
| `feishu_ws.py` | 飞书 WebSocket 长连接机器人 |
| `start.bat` | 一键启动脚本 |

## 八、启动方式

```bash
cd C:\Users\87999\claude-workspace\qiankun
start.bat
```

启动后：
- 前端：http://127.0.0.1:3000
- 后端：http://127.0.0.1:8000
- OHLCV：http://127.0.0.1:8001

## 九、待续

1. OHLCV 端点接回主后端（asyncio 问题）
2. Celery 定时任务全量跑通
3. 飞书长连接稳定化（偶发掉线）
4. pytdx 连接池优化（当前每次请求新建连接）
