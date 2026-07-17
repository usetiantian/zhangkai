@echo off
rem ============================================
rem 乾坤·UZI 每日扫描 — 生成手机App数据
rem ============================================
cd /d "C:\Users\87999\claude-workspace\qiankun-uzi"

set PYTHONIOENCODING=utf-8

echo [%date% %time%] 开始

rem 1. 刷新龙虎榜数据（生成 output/latest_lhb.json）
python -c "from data.lhb import get_lhb_list; get_lhb_list(); print('LHB done')"

rem 2. 扫描（生成 output/latest_scan.json）
python main.py scan --lhb

rem 3. 手机打开 app.html 即看结果
echo.
echo [%date% %time%] 完成。手机打开 app.html 查看结果。
