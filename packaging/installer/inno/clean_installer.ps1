param(
    [switch]$CleanPyInstaller
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..\..")
$outputDir = Join-Path $repoRoot "packaging\installer\output"

if (Test-Path $outputDir) {
    Remove-Item -LiteralPath $outputDir -Recurse -Force
}
New-Item -ItemType Directory -Path $outputDir | Out-Null

if ($CleanPyInstaller) {
    & powershell -ExecutionPolicy Bypass -File (Join-Path $repoRoot "packaging\pyinstaller\clean.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller clean failed with exit code $LASTEXITCODE"
    }
} else {
    Write-Host "installer output cleaned. Use packaging\pyinstaller\clean.ps1 to clean build\ and dist\."
}

Write-Host "clean_installer.ps1 does not remove LocalAppData settings, logs, or user workspaces."
