@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo   ==============================
echo     Nexus — 个人AI平台
echo   ==============================
echo.
echo   [1] 运行全量测试... 
python tests\test_all.py
echo.
echo   [2] 运行能力演示...
python demo.py
echo.
echo   [3] Nexus 就绪。python main.py 启动交互模式
echo.
