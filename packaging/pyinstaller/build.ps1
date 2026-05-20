Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$specPath = Join-Path $scriptDir "pkb-gui.spec"

Push-Location $repoRoot
try {
    python -m PyInstaller $specPath --noconfirm
    python (Join-Path $scriptDir "check_dist.py")
}
finally {
    Pop-Location
}
