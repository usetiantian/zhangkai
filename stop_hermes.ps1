# Kill the Hermes gateway process
$hermesPid = 26452
try {
    $proc = Get-Process -Id $hermesPid -ErrorAction Stop
    Write-Host "Killing Hermes Gateway (PID: $hermesPid, Name: $($proc.ProcessName))..."
    Stop-Process -Id $hermesPid -Force
    Write-Host "Hermes Gateway process killed successfully."
} catch {
    Write-Host "Process PID $hermesPid not found or already stopped: $_"
}

# Also check for any remaining hermes python processes
Write-Host "Checking for any remaining hermes processes..."
$allProcs = Get-Process | Where-Object { $_.ProcessName -match "python" }
foreach ($p in $allProcs) {
    try {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)").CommandLine
        if ($cmd -match "hermes") {
            Write-Host "Found remaining Hermes process: PID $($p.Id) - $cmd"
            Stop-Process -Id $p.Id -Force
            Write-Host "  -> Killed."
        }
    } catch {}
}

Write-Host "Done."
