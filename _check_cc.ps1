$ErrorActionPreference = "Continue"
Write-Output "=== ALL claude/node processes ==="
Get-Process | Where-Object {
    $_.ProcessName -match "^(claude|node)$"
} | ForEach-Object {
    $cmd = ""
    try { $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine } catch {}
    Write-Output ("PID {0,-6} {1,-12} Started {2,-20} Cmd: {3}" -f $_.Id, $_.ProcessName, $_.StartTime, $cmd)
}

Write-Output ""
Write-Output "=== Bin state ==="
$bin = 'C:\Users\87999\AppData\Roaming\npm\node_modules\@anthropic-ai\claude-code\bin\claude.exe'
Get-Item $bin | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize

Write-Output ""
Write-Output "=== Real binary location ==="
$real = 'C:\Users\87999\AppData\Roaming\npm\node_modules\@anthropic-ai\.claude-code-3i9SWAYR\bin\claude.exe.old.1784045949516'
if (Test-Path $real) {
    Get-Item $real | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
} else {
    Write-Output "not found"
}

Write-Output ""
Write-Output "=== Listener on 19666? ==="
Get-NetTCPConnection -LocalPort 19666 -ErrorAction SilentlyContinue | Select-Object LocalAddress, LocalPort, State, OwningProcess | Format-Table -AutoSize