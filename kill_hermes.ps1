Write-Host "=== Searching for Hermes/gateway Python processes ==="
$procs = Get-Process | Where-Object { $_.ProcessName -match "python|node|hermes|gateway" }
$procs | ForEach-Object {
    try {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
        Write-Host "PID: $($_.Id)  Name: $($_.ProcessName)  Cmd: $cmd"
    } catch {
        Write-Host "PID: $($_.Id)  Name: $($_.ProcessName)"
    }
}

Write-Host "`n=== Checking Hermes gateway startup ==="
$startup = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
Get-ChildItem $startup -Filter "*hermes*" -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "Startup: $($_.FullName)" }

Write-Host "`n=== Checking registry Run keys for hermes ==="
$regPaths = @(
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run",
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run"
)
foreach ($rp in $regPaths) {
    Get-ItemProperty $rp -ErrorAction SilentlyContinue | Get-Member -MemberType NoteProperty | ForEach-Object {
        $name = $_.Name
        if ($name -match "hermes") {
            $val = (Get-ItemProperty $rp).$name
            Write-Host "Registry Run: $name = $val"
        }
    }
}

Write-Host "`n=== Content of Hermes Gateway CMD ==="
$cmdPath = "$env:LOCALAPPDATA\hermes\gateway-service\Hermes_Gateway.cmd"
if (Test-Path $cmdPath) {
    Get-Content $cmdPath
}
