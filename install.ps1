# One-liner install: irm https://raw.githubusercontent.com/context-foundry/context-foundry/main/install.ps1 | iex
# Clean install:     powershell -File install.ps1 -Clean
param(
    [switch]$Clean
)
$ErrorActionPreference = "Stop"

# Force TLS 1.2 (older PowerShell defaults to TLS 1.0 which GitHub rejects)
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo = "context-foundry/context-foundry"
$Target = "windows"
$InstallDir = if ($env:FOUNDRY_INSTALL_DIR) { $env:FOUNDRY_INSTALL_DIR } else { "$env:USERPROFILE\.local\bin" }

# ─── Clean: remove stale binary and app data ───────────────────────
if ($Clean) {
    Write-Host "Cleaning previous installation..."

    # Remove old binary
    $OldBinary = Join-Path $InstallDir "foundry.exe"
    if (Test-Path $OldBinary) {
        Remove-Item $OldBinary -Force
        Write-Host "  Removed $OldBinary"
    }

    # Remove app data (patterns, embeddings cache, doubt history, config)
    $AppDataDirs = @(
        (Join-Path $env:LOCALAPPDATA "context-foundry"),
        (Join-Path $env:USERPROFILE ".context-foundry"),
        (Join-Path $env:USERPROFILE ".foundry")
    )
    foreach ($Dir in $AppDataDirs) {
        if (Test-Path $Dir) {
            Remove-Item $Dir -Recurse -Force
            Write-Host "  Removed $Dir"
        }
    }

    Write-Host "Clean complete. Per-project files (.buildloop, TASKS.md) are untouched."
    Write-Host ""
}

# ─── Install ────────────────────────────────────────────────────────

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
