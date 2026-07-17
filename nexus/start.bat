@echo off
cd /d "%~dp0"
echo.
echo   ==============================
echo     Nexus v1.0
echo   ==============================
echo.
echo   [1] Running tests...
python tests\test_all.py
echo.
echo   [2] Running demo...
python demo.py
echo.
echo   [3] Nexus ready. python main.py  to chat.
echo.
pause
