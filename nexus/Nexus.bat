@echo off
cd /d "%~dp0"
echo.
echo   ==============================
echo     Nexus v1.0  Full Launch
echo   ==============================
echo.

echo   [1/3] Running tests...
python tests\test_all.py 2>nul
echo.

echo   [2/3] Loading Qwen model...
echo   (this takes ~12 seconds)
echo.

echo   [3/3] Starting Nexus...
echo.
echo   You can talk to Nexus now.
echo   Type 'quit' to exit.
echo   ==============================
echo.

python main.py

pause
