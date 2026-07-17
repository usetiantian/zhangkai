# CC → OpenClaw 交接单

## CC 做了什么

乾坤·UZI v1.0 — A股超短线AI分析系统，已全部跑通。

## OpenClaw 需要做什么

### 日常任务：每个交易日 15:05 执行

```bash
C:\Users\87999\claude-workspace\qiankun-uzi\daily_scan.bat
```

或直接：
```bash
cd C:\Users\87999\claude-workspace\qiankun-uzi
python main.py scan --lhb --notify
```

### 产出
- JSON扫描结果 → `qiankun-uzi/output/scan_*.json`
- HTML分析报告 → `qiankun-uzi/output/*.html`（对单只股票分析时产出）
- 飞书推送 → 需要先配 `FEISHU_WEBHOOK_URL` 环境变量

### 依赖
- Python 3.10+
- pip install pytdx pyyaml
- LM Studio 运行中（可选，离线时降级为简易模式）

### 查看结果
```bash
python main.py lhb          # 龙虎榜
python main.py config       # 配置
```

## CC 的边界
- 架构设计、新功能开发 → CC
- 日常执行、定时调度 → OpenClaw
- 谁发现问题谁汇报张凯
