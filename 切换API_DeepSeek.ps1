# 切换导演台 AI 的 API 到 DeepSeek
# 密钥从剪贴板读取，全程不写进命令行、不写进脚本、不进日志。
# 用法：复制 DeepSeek Key 到剪贴板 -> 右键本文件"用 PowerShell 运行" -> 看最后一行输出

$ErrorActionPreference = 'Stop'
$key = (Get-Clipboard -Raw).Trim()
if (-not $key) { Write-Host "剪贴板是空的，先复制 DeepSeek API Key" -ForegroundColor Red; exit 1 }

$body = @{
  base_url = "https://api.deepseek.com/v1"
  model    = "deepseek-chat"
  api_key  = $key
} | ConvertTo-Json

try {
  $r = Invoke-RestMethod -Uri "http://127.0.0.1:8188/h3director/api_config" -Method Post -ContentType "application/json" -Body $body
} catch {
  Write-Host ("保存失败: " + $_.Exception.Message) -ForegroundColor Red
  Write-Host "确认 ComfyUI 正在运行 (8188 端口)" -ForegroundColor Yellow
  exit 1
}
Write-Host ("已保存: {0} / {1}" -f $r.base_url, $r.model) -ForegroundColor Green

try {
  $t = Invoke-RestMethod -Uri "http://127.0.0.1:8188/h3director/api_test" -Method Post -ContentType "application/json" -Body "{}"
} catch {
  Write-Host ("测试连接失败: " + $_.Exception.Message) -ForegroundColor Red
  exit 1
}
if ($t.ok) {
  Write-Host ("连接正常: model={0}" -f $t.model) -ForegroundColor Green
  Write-Host ("返回前40字: {0}" -f $t.content.Substring(0, [Math]::Min(40, $t.content.Length))) -ForegroundColor Gray
} else {
  Write-Host ("连接失败: {0}" -f $t.error) -ForegroundColor Red
}
