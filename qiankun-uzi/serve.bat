@echo off
cd /d "C:\Users\87999\claude-workspace\qiankun-uzi"
echo.
echo ============================================
echo  乾坤UZI 手机版已启动
echo  手机访问: http://你的电脑IP:8080/app.html
echo  本机访问: http://localhost:8080/app.html
echo ============================================
echo.
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do echo  IP: %%a
echo.
python -m http.server 8080
