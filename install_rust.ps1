$rustupUrl = "https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe"
$output = "$env:TEMP\rustup-init.exe"
Write-Host "Downloading Rust installer..."
Invoke-WebRequest -Uri $rustupUrl -OutFile $output
Write-Host "Running installer..."
& $output -y --default-toolchain stable 2>&1
Write-Host "Done. Rust installed."
