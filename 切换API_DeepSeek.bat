@echo off
chcp 65001 >nul
title 切换导演台 AI API -> DeepSeek
echo.
echo   请确认剪贴板里已经是 DeepSeek API Key (sk- 开头)
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0切换API_DeepSeek.ps1"
echo.
pause
