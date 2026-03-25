#Requires -Version 5.1
param(
    [string]$ImageName = "foundry-sandbox:latest"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "Building sandbox image: $ImageName"
Write-Host "Context: $ProjectRoot"

docker build `
    -t $ImageName `
    -f "$ProjectRoot\Dockerfile.sandbox" `
    $ProjectRoot

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker build failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Build complete. Verifying..."
Write-Host ""

Write-Host "--- claude --version ---"
docker run --rm $ImageName claude --version

Write-Host ""
Write-Host "--- git --version ---"
docker run --rm $ImageName git --version

Write-Host ""
Write-Host "--- node --version ---"
docker run --rm $ImageName node --version

Write-Host ""
Write-Host "--- whoami ---"
docker run --rm $ImageName whoami

Write-Host ""
Write-Host "Sandbox image '$ImageName' built and verified successfully."
