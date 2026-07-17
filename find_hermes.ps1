Write-Host "=== Checking Windows Services ==="
Get-Service -Name "*hermes*" -ErrorAction SilentlyContinue | Format-Table Name, DisplayName, Status

Write-Host "=== Checking running processes (broader search) ==="
Get-Process | Where-Object { $_.ProcessName -like "*herm*" -or $_.ProcessName -like "*gateway*" } | Format-Table Id, ProcessName, Path

Write-Host "=== Checking any Hermes-related executable paths in Program Files, User Profile ==="
$bases = @("C:\Program Files", "C:\Program Files (x86)", "$env:USERPROFILE", "$env:APPDATA", "$env:LOCALAPPDATA")
foreach ($base in $bases) {
    Get-ChildItem -Path $base -Filter "*hermes*" -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "FOUND DIR: $($_.FullName)"
    }
    Get-ChildItem -Path $base -Filter "*hermes*" -File -ErrorAction SilentlyContinue -Recurse -Depth 3 | ForEach-Object {
        Write-Host "FOUND FILE: $($_.FullName)"
    }
}

Write-Host "=== Checking scheduled tasks containing hermes ==="
schtasks /query /fo csv 2>$null | Select-String "hermes" -CaseInsensitive
