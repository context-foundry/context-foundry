# One-liner install: irm https://raw.githubusercontent.com/context-foundry/context-foundry/main/install.ps1 | iex
$ErrorActionPreference = "Stop"

$Repo = "context-foundry/context-foundry"
$Target = "x86_64-pc-windows-msvc"
$InstallDir = if ($env:FOUNDRY_INSTALL_DIR) { $env:FOUNDRY_INSTALL_DIR } else { "$env:USERPROFILE\.local\bin" }

# Get latest version
$Release = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest"
$Version = $Release.tag_name
if (-not $Version) {
    Write-Error "Failed to determine latest version"
    exit 1
}

$Archive = "foundry-$Target.zip"
$Url = "https://github.com/$Repo/releases/download/$Version/$Archive"

Write-Host "Installing foundry $Version for $Target..."

# Download
$TmpDir = Join-Path ([System.IO.Path]::GetTempPath()) "foundry-install-$(Get-Random)"
New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null
$ZipPath = Join-Path $TmpDir $Archive

Invoke-WebRequest -Uri $Url -OutFile $ZipPath -UseBasicParsing

# Extract
Expand-Archive -Path $ZipPath -DestinationPath $TmpDir -Force

# Install
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}
Copy-Item (Join-Path $TmpDir "foundry.exe") (Join-Path $InstallDir "foundry.exe") -Force

# Cleanup
Remove-Item $TmpDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Installed foundry to $InstallDir\foundry.exe"

# Check PATH
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$InstallDir*") {
    $AddToPath = Read-Host "Add $InstallDir to PATH? (Y/n)"
    if ($AddToPath -ne "n") {
        [Environment]::SetEnvironmentVariable("Path", "$UserPath;$InstallDir", "User")
        Write-Host "Added to PATH. Restart your terminal for changes to take effect."
    }
}

Write-Host "Run 'foundry' to get started."
