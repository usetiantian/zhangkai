#!/usr/bin/env bash
# MiniMax H3 模型下载脚本 (hf-mirror.com 国内镜像)
# 用法:  bash download_h3.sh           # 前台跑
#        bash download_h3.sh &        # 后台跑(推荐)
# 中途中断可重跑,会自动断点续传 + SHA256 校验

set -u

BASE="D:/cli_anything_harnesses/comfyui/comfyui_app/ComfyUI_windows_portable/ComfyUI/models"
VAE="$BASE/vae"
TXT="$BASE/text_encoders"
DIF="$BASE/diffusion_models"
mkdir -p "$VAE" "$TXT" "$DIF"

REPO="Comfy-Org/MiniMax-H3"
MIRROR="https://hf-mirror.com"

# 子目录|文件名|目标目录|SHA256(空=不校验)
FILES=(
  "vae|minimax_h3_audio_vae_fp32.safetensors|$VAE|8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48"
  "vae|minimax_h3_video_vae_fp16.safetensors|$VAE|7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522"
  "text_encoders|qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors|$TXT|35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6"
  "diffusion_models|minimax_h3_fl2va_pruned_int8_convrot.safetensors|$DIF|"
)

log() { echo "[$(date '+%H:%M:%S')] $*"; }

download_one() {
  local sub="$1" name="$2" dst="$3" sha="$4"
  local url="$MIRROR/$REPO/resolve/main/$sub/$name"
  local path="$dst/$name"

  log "==> $name"
  log "    URL: $url"

  local remote_bytes
  remote_bytes=$(curl -sIL "$url" | grep -i '^content-length:' | tail -1 | awk '{print $2}' | tr -d '\r\n')
  if [[ -n "$remote_bytes" ]]; then
    log "    远端大小: $(awk "BEGIN{printf \"%.2f GB\", $remote_bytes/1073741824}")"
  fi

  if [[ -f "$path" && -n "$sha" ]]; then
    local cur
    cur=$(sha256sum "$path" | awk '{print $1}')
    if [[ "$cur" == "$sha" ]]; then
      log "    V 已存在且 SHA256 匹配,跳过"
      return 0
    fi
  fi

  curl -L -C - --retry 10 --retry-delay 10 --retry-all-errors \
       --connect-timeout 30 --speed-time 60 --speed-limit 100 \
       -o "$path" "$url"
  local rc=$?
  if [[ $rc -ne 0 ]]; then
    log "    X curl 退出码 $rc (重跑脚本可续传)"
    return $rc
  fi

  if [[ -n "$sha" ]]; then
    local cur
    cur=$(sha256sum "$path" | awk '{print $1}')
    if [[ "$cur" == "$sha" ]]; then
      local sz=$(ls -lh "$path" | awk '{print $5}')
      log "    V SHA256 校验通过 ($sz)"
    else
      log "    X SHA256 不一致!"
      log "      实际: $cur"
      log "      预期: $sha"
      return 1
    fi
  else
    local sz=$(ls -lh "$path" | awk '{print $5}')
    log "    ! 无官方 SHA,本地: $sz (请人工核对大小)"
  fi
  return 0
}

log "==== MiniMax H3 模型下载 ===="
log "仓库: $REPO"
log "镜像: $MIRROR"
log "目标: $BASE"

fail=0
for line in "${FILES[@]}"; do
  IFS='|' read -r sub name dst sha <<< "$line"
  download_one "$sub" "$name" "$dst" "$sha" || fail=$((fail+1))
done

log "==== 完成 ===="
if [[ $fail -eq 0 ]]; then
  log "全部 4 个文件已就位,重启 ComfyUI 即可"
else
  log "有 $fail 个文件失败,可重跑 $0 续传"
fi
