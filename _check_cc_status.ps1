$ErrorActionPreference = "Continue"
$cutoff = (Get-Date).AddMinutes(-45)
Write-Output "=== Recent node processes (last 45 min) ==="
Get-Process node -ErrorAction SilentlyContinue | Where-Object { $_.StartTime -gt $cutoff } | ForEach-Object {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue
    $cmd = if ($proc) { $proc.CommandLine } else { "" }
    $cmdShort = if ($cmd.Length -gt 200) { $cmd.Substring(0, 200) + "..." } else { $cmd }
    Write-Output ("PID {0,-6} Started {1,-20} Cmd: {2}" -f $_.Id, $_.StartTime, $cmdShort)
}

Write-Output ""
Write-Output "=== CC_NEXUS_AUDIT contents ==="
Get-ChildItem 'C:\Users\87999\claude-workspace\CC_NEXUS_AUDIT' -ErrorAction SilentlyContinue | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize