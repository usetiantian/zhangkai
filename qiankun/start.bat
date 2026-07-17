@echo off
cd /d C:\Users\87999\claude-workspace\qiankun

echo === 乾坤 A股分析平台 一键启动 ===

REM 1. 清数据（避免SQLite锁死）
echo [1/5] 清理旧数据...
rd /s /q "references\ashare-ai-analyst-main\data_new" 2>nul
mkdir "references\ashare-ai-analyst-main\data_new\raw" 2>nul
mkdir "references\ashare-ai-analyst-main\data_new\processed" 2>nul

REM 2. OHLCV 独立数据服务
echo [2/5] 启动 OHLCV 服务...
start "OHLCV" C:\Users\87999\AppData\Local\Programs\Python\Python312\python.exe ohlcv_server.py --port 8001

REM 3. 后端 API
echo [3/5] 启动后端 API...
set QK_DATA_DIR=C:\Users\87999\claude-workspace\qiankun\references\ashare-ai-analyst-main\data_new
cd references\ashare-ai-analyst-main
start "Backend" C:\Users\87999\AppData\Local\Programs\Python\Python312\python.exe -B -m uvicorn src.web.app:app --host 127.0.0.1 --port 8000

REM 4. 前端
echo [4/5] 启动前端...
cd frontend
start "Frontend" C:\Program Files\nodejs\npx.cmd vite --port 3000 --host 127.0.0.1

REM 5. 打开浏览器
echo [5/5] 打开浏览器...
timeout /t 60 /nobreak
start http://127.0.0.1:3000

echo === 启动完成 ===
echo 前端: http://127.0.0.1:3000
echo API:  http://127.0.0.1:8000
echo OHLCV: http://127.0.0.1:8001
pause
