@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo.
echo   music3 音乐工作室 - 打包
echo   -----------------------
python -m pip install --quiet pyinstaller || goto :fail
python -m PyInstaller --noconfirm --clean music3.spec || goto :fail
if not exist "release" mkdir release
copy /y "dist\music3.exe" "release\music3.exe" > nul
copy /y "LICENSE" "release\LICENSE" > nul
copy /y "LICENSE-MINIMAX-MUSIC3.txt" "release\" > nul
copy /y "THIRD-PARTY-NOTICES.md" "release\" > nul
copy /y "使用说明.txt" "release\" > nul
echo.
echo   完成 -> release\music3.exe
echo.
pause
exit /b 0
:fail
echo   打包失败，请检查上面的错误输出。
pause
