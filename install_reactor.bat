@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
set CF=D:\ComfyUI_windows_portable
set CN=%CF%\ComfyUI\custom_nodes
set MD=%CF%\ComfyUI\models
set HF=https://hf-mirror.com/datasets/Gourieff/ReActor/resolve/main/models
set PY=%CF%\python_embeded\python.exe

echo ============================================================
echo   一键安装 ReActor 换脸插件 + 模型
echo ============================================================
echo.

echo [1/5] 克隆插件 ComfyUI-ReActor ...
if exist "%CN%\ComfyUI-ReActor\__init__.py" (
  echo       已存在，跳过
) else (
  git clone --depth 1 https://github.com/Gourieff/ComfyUI-ReActor.git "%CN%\ComfyUI-ReActor"
)

echo.
echo [2/5] 安装 Python 依赖 ...
if exist "%CN%\ComfyUI-ReActor\install.bat" (
  call "%CN%\ComfyUI-ReActor\install.bat"
) else (
  "%PY%" -m pip install onnx opencv-python ultralytics albumentations segment-anything colour-science
)

echo.
echo [3/5] 下载 inswapper_128_fp16.onnx (264 MB) ...
if exist "%MD%\insightface\inswapper_128_fp16.onnx" (
  echo       已存在，跳过
) else (
  curl -L -C - -o "%MD%\insightface\inswapper_128_fp16.onnx" "%HF%/inswapper_128_fp16.onnx"
)

echo.
echo [4/5] 解压 buffalo_l ...
if exist "%MD%\insightface\models\buffalo_l\w600k_r50.onnx" (
  echo       已存在，跳过
) else (
  if not exist "%MD%\insightface\buffalo_l.zip" (
    curl -L -C - -o "%MD%\insightface\buffalo_l.zip" "%HF%/buffalo_l.zip"
  )
  mkdir "%MD%\insightface\models\buffalo_l" 2>nul
  tar -xf "%MD%\insightface\buffalo_l.zip" -C "%MD%\insightface\models\buffalo_l"
)

echo.
echo [5/5] 补齐 GFPGAN 修脸模型 ...
if exist "%MD%\facerestore_models\GFPGANv1.4.pth" (
  echo       已存在，跳过
) else (
  if exist "%MD%\gfpgan\GFPGANv1.4.pth" (
    copy "%MD%\gfpgan\GFPGANv1.4.pth" "%MD%\facerestore_models\GFPGANv1.4.pth"
  ) else (
    curl -L -C - -o "%MD%\facerestore_models\GFPGANv1.4.pth" "%HF%/facerestore_models/GFPGANv1.4.pth"
  )
)

echo.
echo ============================================================
echo   完成！重启 ComfyUI 后打开工作流：
echo   %CF%\ComfyUI\user\default\workflows\视频换脸_ReActor.json
echo ============================================================
echo.
pause
