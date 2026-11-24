# ============================================================
# MiniMax H3 模型下载脚本 (hf-mirror.com 国内镜像)
# 用法: 在 PowerShell 里跑  .\download_h3.ps1
# 中途中断可重跑,会自动断点续传 + SHA256 校验
# ============================================================

# 国内镜像设置(关键!)
$env:HF_ENDPOINT = "https://hf-mirror.com"

# ComfyUI models 根目录
$BASE = "D:\cli_anything_harnesses\comfyui\comfyui_app\ComfyUI_windows_portable\ComfyUI\models"

# 目标子目录
$VAE = "$BASE\vae"
$TXT = "$BASE\text_encoders"
$DIF = "$BASE\diffusion_models"
New-Item -ItemType Directory -Force -Path $VAE, $TXT, $DIF | Out-Null

# 仓库 + 文件清单 (SHA256 来自 SwarmUI / unsloth 等仓库源码)
$REPO = "Comfy-Org/MiniMax-H3"
$Files = @(
    @{ sub = "vae";              name = "minimax_h3_audio_vae_fp32.safetensors";            dst = $VAE; sha = "8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48" },
    @{ sub = "vae";              name = "minimax_h3_video_vae_fp16.safetensors";            dst = $VAE; sha = "7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522" },
    @{ sub = "text_encoders";    name = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors";     dst = $TXT; sha = "35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6" },
    @{ sub = "diffusion_models"; name = "minimax_h3_fl2va_pruned_int8_convrot.safetensors"; dst = $DIF; sha = "" }
)

function Get-H3Model {
    param($sub, $name, $dst, $sha)

    $url  = "$env:HF_ENDPOINT/$REPO/resolve/main/$sub/$name"
    $path = Join-Path $dst $name

    Write-Host ""
    Write-Host "==> [$name]" -ForegroundColor Cyan

    try {
        $head = Invoke-WebRequest $url -Method Head -UseBasicParsing -ErrorAction Stop
        $remoteBytes = [int64]$head.Headers['Content-Length'][0]
        Write-Host ("    远端大小: {0:N2} GB" -f ($remoteBytes / 1GB))
    } catch {
        Write-Host "    [警告] 无法获取远端大小: $($_.Exception.Message)" -ForegroundColor DarkYellow
        $remoteBytes = 0
    }

    if ((Test-Path $path) -and $sha -ne "") {
        $curSha = (Get-FileHash $path -Algorithm SHA256).Hash.ToLower()
        if ($curSha -eq $sha) {
            Write-Host "    V 已下载且 SHA256 校验通过 (跳过)" -ForegroundColor Green
            return
        }
    }

    Write-Host "    下载: $url" -ForegroundColor Yellow
    & curl.exe -L -C - --retry 5 --retry-delay 10 --connect-timeout 30 -o "$path" "$url"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    X curl 退出码 $LASTEXITCODE,可重跑脚本续传" -ForegroundColor Red
        return
    }

    if ($sha -ne "") {
        $curSha = (Get-FileHash $path -Algorithm SHA256).Hash.ToLower()
        if ($curSha -eq $sha) {
            Write-Host "    V SHA256 校验通过" -ForegroundColor Green
        } else {
            Write-Host "    X SHA256 不一致!" -ForegroundColor Red
            Write-Host "      实际: $curSha"
            Write-Host "      预期: $sha"
        }
    } else {
        $localBytes = (Get-Item $path).Length
        Write-Host ("    ! 无官方 SHA,本地文件: {0:N2} GB (请人工确认与预期大小一致)" -f ($localBytes / 1GB)) -ForegroundColor DarkYellow
    }
}

Write-Host "==== MiniMax H3 模型下载 ====" -ForegroundColor Cyan
Write-Host "仓库: $REPO"
Write-Host "镜像: $env:HF_ENDPOINT"
Write-Host "目标: $BASE"
Write-Host "文件: 4 个,合计约 36 GB"

foreach ($f in $Files) {
    Get-H3Model -sub $f.sub -name $f.name -dst $f.dst -sha $f.sha
}

Write-Host ""
Write-Host "==== 完成 ====" -ForegroundColor Cyan
Write-Host "下一步:重启 ComfyUI,节点应该能正常加载了。"
