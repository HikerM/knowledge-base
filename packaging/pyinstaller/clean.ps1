Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$repoRootPath = $repoRoot.Path
$targets = @(
    (Join-Path $repoRootPath "build"),
    (Join-Path $repoRootPath "dist")
)

foreach ($target in $targets) {
    if (-not ($target.StartsWith($repoRootPath))) {
        throw "Refusing to remove path outside repository: $target"
    }
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}
