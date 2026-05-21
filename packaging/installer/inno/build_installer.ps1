Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..\..")
$pyinstallerBuild = Join-Path $repoRoot "packaging\pyinstaller\build.ps1"
$issPath = Join-Path $scriptDir "pkb-gui.iss"
$distExe = Join-Path $repoRoot "dist\pkb-gui\pkb-gui.exe"
$installerPath = Join-Path $repoRoot "packaging\installer\output\PersonalKnowledgeBase-Setup-v2.0.0-rc.1.exe"
$checkScript = Join-Path $scriptDir "check_installer.py"

function Resolve-Iscc {
    $command = Get-Command ISCC -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }
    return $null
}

Push-Location $repoRoot
try {
    & powershell -ExecutionPolicy Bypass -File $pyinstallerBuild
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed with exit code $LASTEXITCODE"
    }

    if (-not (Test-Path $distExe)) {
        throw "PyInstaller one-folder executable is missing: $distExe"
    }

    $iscc = Resolve-Iscc
    if (-not $iscc) {
        Write-Error "blocked: Inno Setup 6 ISCC was not found. Install Inno Setup 6 from https://jrsoftware.org/isdl.php, reopen the shell, then rerun this script."
    }

    & $iscc $issPath
    if ($LASTEXITCODE -ne 0) {
        throw "ISCC failed with exit code $LASTEXITCODE"
    }

    & python $checkScript
    if ($LASTEXITCODE -ne 0) {
        throw "installer check failed with exit code $LASTEXITCODE"
    }

    $installer = Get-Item $installerPath
    Write-Host ("installer_path={0}" -f $installer.FullName)
    Write-Host ("installer_size_bytes={0}" -f $installer.Length)
}
finally {
    Pop-Location
}
