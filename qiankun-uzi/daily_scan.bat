@echo off
rem ============================================
rem 乾坤·UZI 每日扫描 — 交给 OpenClaw cron 执行
rem CC 2026-07-17 建
rem ============================================
cd /d "C:\Users\87999\claude-workspace\qiankun-uzi"

set PYTHONIOENCODING=utf-8

echo [%date% %time%] 乾坤UZI 每日扫描开始

python main.py scan --lhb

echo [%date% %time%] 扫描完成，结果在 output/ 目录
