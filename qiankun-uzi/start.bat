@echo off
chcp 65001 >nul
title 乾坤·UZI — A股 AI 分析系统

echo.
echo   ╔═══════════════════════════════════════╗
echo   ║     乾坤·UZI v1.0                      ║
echo   ║     A股 AI 分析系统                     ║
echo   ╚═══════════════════════════════════════╝
echo.
echo   数据源：pytdx / baostock / 腾讯qt（全免费）
echo   AI模型：Qwen3-VL-4B 本地运行
echo.
echo   ─────────────────────────────────────
echo   用法：
echo.
echo     python main.py 002185       分析华天科技
echo     python main.py scan         扫描超卖股票
echo.
echo   确保 LM Studio 已启动并加载 Qwen3-VL-4B
echo   ─────────────────────────────────────
echo.

set /p CODE=请输入股票代码（直接回车=扫描超卖）: 

if "%CODE%"=="" (
    python main.py scan
) else (
    python main.py %CODE%
)

pause
