$rustup = Join-Path $env:USERPROFILE ".cargo\bin\rustup.exe"
if (Test-Path $rustup) {
    Write-Host "Found rustup at: $rustup"
    & $rustup component add rust-analyzer
} else {
    Write-Host "rustup not found at: $rustup"
}
