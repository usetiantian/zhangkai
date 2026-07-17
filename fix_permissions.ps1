$cfgPath = "$env:USERPROFILE\.claude\settings.json"
$cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
Copy-Item $cfgPath "$cfgPath.bak"

$cfg | Add-Member -NotePropertyName "permissions" -NotePropertyValue @{
    allow = @("Bash(*)", "Read(*)", "Write(*)", "Edit(*)", "mcp__*")
    deny = @("Bash(rm -rf *)", "Bash(del /f /s *)", "Bash(format *)", "Bash(diskpart *)", "Bash(shutdown *)", "Bash(rmdir /s *)")
} -Force

$cfg | Add-Member -NotePropertyName "dangerouslySkipPermissions" -NotePropertyValue $true -Force

$cfg | ConvertTo-Json -Depth 3 | Set-Content $cfgPath -Encoding UTF8
Write-Host "Done. Backed up to settings.json.bak"
