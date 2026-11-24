@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
set CF=D:\ComfyUI_windows_portable
set PY=%CF%\python_embeded\python.exe
set CN=%CF%\ComfyUI\custom_nodes
set MIR=https://mirrors.aliyun.com/pypi/simple/

echo ============================================================
echo   换脸加速收尾
echo   请先手动关闭 ComfyUI 窗口再运行！
echo ============================================================
echo.

echo [1/4] 检查 ComfyUI 是否已关闭 ...
netstat -ano | findstr ":8188" | findstr "LISTENING" >nul
if not errorlevel 1 (
  echo   8188 还被占用 —— onnxruntime 的 DLL 被 ComfyUI 锁着，必须先关掉它。
  echo   请关闭 ComfyUI 窗口后重新运行本脚本。
  pause
  exit /b 1
)
echo   OK.

echo.
echo [2/4] 卸载 CPU 版 onnxruntime ...
"%PY%" -m pip uninstall -y onnxruntime
echo.
echo [3/4] 安装 GPU 版 onnxruntime-gpu (阿里云源) ...
"%PY%" -m pip install --index-url %MIR% --upgrade onnxruntime-gpu
if errorlevel 1 (
  echo   安装失败。网络问题可手动下载 wheel 后本地安装。
) else (
  echo   OK.
)
echo.
echo   验证 provider ...
"%PY%" -c "import torch,os;tl=os.path.join(os.path.dirname(torch.__file__),'lib');os.add_dll_directory(tl);os.environ['PATH']=tl+os.pathsep+os.environ['PATH'];import onnxruntime as ort;print('   onnxruntime',ort.__version__);print('   providers:',ort.get_available_providers())"

echo.
echo [4/4] 安装 h3-relay 节点 (官方角色替换工作流需要) ...
if exist "%CN%\h3-relay" (
  echo   已存在，跳过
) else (
  git clone --depth 1 https://github.com/akatz-ai/h3-relay.git "%CN%\h3-relay"
)

echo.
echo ============================================================
echo   完成！重新启动 ComfyUI 即可
echo   视频换脸   : %CF%\ComfyUI\user\default\workflows\视频换脸_ReActor.json
echo   角色替换   : %CF%\ComfyUI\user\default\workflows\H3角色替换_CharacterSwap_官方.json
echo ============================================================
echo.
pause
