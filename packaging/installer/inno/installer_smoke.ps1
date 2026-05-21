Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..\..")
$installerPath = Join-Path $repoRoot "packaging\installer\output\PersonalKnowledgeBase-Setup-v2.0.0.exe"
$repoDrive = [System.IO.Path]::GetPathRoot($repoRoot.Path)
$tempRoot = Join-Path $repoDrive ("pkb-smoke-" + [System.Guid]::NewGuid().ToString("N").Substring(0, 8))
$installDir = Join-Path $tempRoot "app"
$localAppData = Join-Path $tempRoot "LocalAppData"
$workspacePath = Join-Path $tempRoot "user-workspace"
$emptyWorkspacePath = Join-Path $tempRoot "empty-workspace"
$createdWorkspacePath = Join-Path $tempRoot "created-workspace"
$installLogPath = Join-Path $tempRoot "install.log"
$reinstallLogPath = Join-Path $tempRoot "reinstall.log"
$uninstallLogPath = Join-Path $tempRoot "uninstall.log"
$finalCleanupLogPath = Join-Path $tempRoot "final-cleanup-uninstall.log"
$settingsPath = Join-Path $localAppData "PersonalKnowledgeBase\settings\gui-settings.json"
$logsDir = Join-Path $localAppData "PersonalKnowledgeBase\logs"
$logPath = Join-Path $logsDir "pkb-gui.log"

$result = [ordered]@{
    install_ok = $false
    launch_ok = $false
    empty_workspace_no_kb_created = $false
    workspace_creation_service_ok = $false
    uninstall_ok = $false
    user_data_preserved = $false
    reinstall_ok = $false
    final_cleanup_ok = $false
    git_not_required = $false
    python_not_required = $false
    logs_path = $logPath
    settings_path = $settingsPath
    workspace_path = $workspacePath
    install_dir = $installDir
    temp_root = $tempRoot
    install_log_path = $installLogPath
    uninstall_log_path = $uninstallLogPath
    reinstall_log_path = $reinstallLogPath
    final_cleanup_log_path = $finalCleanupLogPath
    manual_checks = @(
        "Double-click installer wizard copy, optional desktop shortcut copy, and first-run workspace picker visuals are manual checks.",
        "Installer smoke verifies silent install, launch with selected workspaces, uninstall, reinstall, LocalAppData preservation, and no automatic index."
    )
    error = ""
}

function Invoke-CheckedProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [int]$TimeoutSeconds = 120
    )

    if ($Arguments.Count -gt 0) {
        $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -PassThru
    } else {
        $process = Start-Process -FilePath $FilePath -PassThru
    }
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        try {
            $process.Kill()
        } catch {
        }
        throw "process timed out: $FilePath $($Arguments -join ' ')"
    }
    if ($process.ExitCode -ne 0) {
        throw "process failed with exit code $($process.ExitCode): $FilePath $($Arguments -join ' ')"
    }
}

function Invoke-InstalledGui {
    param(
        [Parameter(Mandatory = $true)][string]$ExePath,
        [string]$Workspace = ""
    )

    $oldLocalAppData = $env:LOCALAPPDATA
    $oldAutoClose = $env:PKB_GUI_AUTO_CLOSE_MS
    $oldPath = $env:PATH
    $oldPythonHome = $env:PYTHONHOME
    $oldPythonPath = $env:PYTHONPATH
    $oldQtPlatform = $env:QT_QPA_PLATFORM
    try {
        $env:LOCALAPPDATA = $localAppData
        $env:PKB_GUI_AUTO_CLOSE_MS = "1000"
        $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\Wbem"
        Remove-Item Env:\PYTHONHOME -ErrorAction SilentlyContinue
        Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
        Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue
        $result.git_not_required = -not [bool](Get-Command git -ErrorAction SilentlyContinue)
        $result.python_not_required = -not [bool](Get-Command python -ErrorAction SilentlyContinue)
        $args = @()
        if ($Workspace) {
            $args = @("--workspace", $Workspace)
        }
        Invoke-CheckedProcess -FilePath $ExePath -Arguments $args -TimeoutSeconds 20
    }
    finally {
        $env:LOCALAPPDATA = $oldLocalAppData
        $env:PKB_GUI_AUTO_CLOSE_MS = $oldAutoClose
        $env:PATH = $oldPath
        if ($null -eq $oldPythonHome) {
            Remove-Item Env:\PYTHONHOME -ErrorAction SilentlyContinue
        } else {
            $env:PYTHONHOME = $oldPythonHome
        }
        if ($null -eq $oldPythonPath) {
            Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
        } else {
            $env:PYTHONPATH = $oldPythonPath
        }
        if ($null -eq $oldQtPlatform) {
            Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue
        } else {
            $env:QT_QPA_PLATFORM = $oldQtPlatform
        }
    }
}

function Initialize-TestWorkspace {
    param([Parameter(Mandatory = $true)][string]$Path)
    New-Item -ItemType Directory -Path $Path | Out-Null
    foreach ($name in @("knowledge", "config", "templates", "reports")) {
        New-Item -ItemType Directory -Path (Join-Path $Path $name) | Out-Null
    }
    @"
schema_version: 1
workspace_name: "Installer Smoke Workspace"
template_id: "custom"
local_only: true
git_required: false
auto_index: false
"@ | Set-Content -Path (Join-Path $Path "workspace.yaml") -Encoding UTF8
    "smoke sentinel" | Set-Content -Path (Join-Path $Path "knowledge\sentinel.txt") -Encoding UTF8
}

function Invoke-WorkspaceCreationProbe {
    $probePath = Join-Path $tempRoot "workspace_creation_probe.py"
    @'
import os
import sys
from pathlib import Path

repo = Path(os.environ["PKB_REPO_ROOT"])
sys.path.insert(0, str(repo))

from knowledge_app.models.workspace_creation_models import WorkspaceCreationRequest
from knowledge_app.services.workspace_creation_plan_service import WorkspaceCreationPlanService
from knowledge_app.services.workspace_creation_service import WorkspaceCreationService

target = Path(os.environ["PKB_CREATED_WORKSPACE"])
plan = WorkspaceCreationPlanService().create_workspace_plan(
    WorkspaceCreationRequest(target_path=str(target), workspace_name="Installer Created Workspace", template_id="personal")
)
result = WorkspaceCreationService().create_workspace_from_plan(plan, confirmed=True)
if not result.success:
    raise SystemExit(result.to_dict())
required = ["workspace.yaml", "knowledge", "config", "templates", "reports", "config/categories.yaml"]
missing = [item for item in required if not (target / item).exists()]
if missing:
    raise SystemExit(f"missing created workspace entries: {missing}")
if (target / ".kb").exists():
    raise SystemExit("workspace creation must not create .kb")
'@ | Set-Content -Path $probePath -Encoding UTF8
    $oldRepo = $env:PKB_REPO_ROOT
    $oldTarget = $env:PKB_CREATED_WORKSPACE
    try {
        $env:PKB_REPO_ROOT = $repoRoot
        $env:PKB_CREATED_WORKSPACE = $createdWorkspacePath
        Invoke-CheckedProcess -FilePath "python" -Arguments @($probePath) -TimeoutSeconds 60
    }
    finally {
        $env:PKB_REPO_ROOT = $oldRepo
        $env:PKB_CREATED_WORKSPACE = $oldTarget
    }
}

try {
    if (-not (Test-Path $installerPath)) {
        throw "installer not found: $installerPath"
    }

    New-Item -ItemType Directory -Path $tempRoot | Out-Null
    Initialize-TestWorkspace -Path $workspacePath
    New-Item -ItemType Directory -Path $emptyWorkspacePath | Out-Null

    Invoke-CheckedProcess -FilePath $installerPath -Arguments @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=$installDir", "/LOG=$installLogPath") -TimeoutSeconds 180
    $installedExe = Join-Path $installDir "pkb-gui.exe"
    $uninstaller = Get-ChildItem -Path $installDir -Filter "unins*.exe" | Select-Object -First 1
    if (-not (Test-Path $installDir) -or -not (Test-Path $installedExe) -or -not $uninstaller) {
        throw "silent install did not create expected app files"
    }
    $result.install_ok = $true

    Invoke-InstalledGui -ExePath $installedExe -Workspace $workspacePath
    if (-not (Test-Path $settingsPath) -or -not (Test-Path $logPath)) {
        throw "GUI did not write settings/logs to LocalAppData"
    }
    $settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
    if ($settings.last_opened_workspace -ne (Resolve-Path $workspacePath).Path) {
        throw "last_opened_workspace was not written for selected workspace"
    }
    if ((Get-ChildItem -Path $installDir -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -in @("gui-settings.json", "pkb-gui.log") })) {
        throw "settings or logs were written to the install directory"
    }
    $result.launch_ok = $true

    Invoke-InstalledGui -ExePath $installedExe -Workspace $emptyWorkspacePath
    if ((Test-Path (Join-Path $emptyWorkspacePath ".kb")) -or (Test-Path (Join-Path $emptyWorkspacePath ".kb\index.sqlite"))) {
        throw "empty workspace startup created runtime index data"
    }
    $result.empty_workspace_no_kb_created = $true

    Invoke-WorkspaceCreationProbe
    if ((Test-Path (Join-Path $createdWorkspacePath ".kb")) -or (Test-Path (Join-Path $createdWorkspacePath ".kb\index.sqlite"))) {
        throw "workspace creation probe created runtime index data"
    }
    $result.workspace_creation_service_ok = $true

    Invoke-InstalledGui -ExePath $installedExe -Workspace $workspacePath
    $settingsBeforeUninstall = Get-Content $settingsPath -Raw | ConvertFrom-Json

    Invoke-CheckedProcess -FilePath $uninstaller.FullName -Arguments @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LOG=$uninstallLogPath") -TimeoutSeconds 180
    if (Test-Path $installedExe) {
        throw "uninstall did not remove the main executable"
    }
    $result.uninstall_ok = $true

    $workspaceRequired = @(
        "workspace.yaml",
        "knowledge",
        "config",
        "templates",
        "reports",
        "knowledge\sentinel.txt"
    )
    $missingWorkspace = @($workspaceRequired | Where-Object { -not (Test-Path (Join-Path $workspacePath $_)) })
    if ($missingWorkspace.Count -gt 0) {
        throw "uninstall removed workspace data: $($missingWorkspace -join ', ')"
    }
    if (-not (Test-Path $settingsPath) -or -not (Test-Path $logPath)) {
        throw "uninstall removed LocalAppData settings or logs"
    }
    if ((Test-Path (Join-Path $workspacePath ".kb")) -or (Test-Path (Join-Path $createdWorkspacePath ".kb"))) {
        throw "smoke observed unexpected runtime index data after uninstall"
    }
    $result.user_data_preserved = $true

    Invoke-CheckedProcess -FilePath $installerPath -Arguments @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=$installDir", "/LOG=$reinstallLogPath") -TimeoutSeconds 180
    if (-not (Test-Path $installedExe)) {
        throw "reinstall did not restore the main executable"
    }
    Invoke-InstalledGui -ExePath $installedExe
    $settingsAfterReinstall = Get-Content $settingsPath -Raw | ConvertFrom-Json
    if ($settingsAfterReinstall.last_opened_workspace -ne $settingsBeforeUninstall.last_opened_workspace) {
        throw "last_opened_workspace was not preserved across reinstall"
    }
    if (-not (Test-Path (Join-Path $workspacePath "knowledge\sentinel.txt"))) {
        throw "workspace sentinel was not preserved across reinstall"
    }
    if ((Test-Path (Join-Path $workspacePath ".kb\index.sqlite")) -or (Test-Path (Join-Path $emptyWorkspacePath ".kb")) -or (Test-Path (Join-Path $createdWorkspacePath ".kb"))) {
        throw "reinstall flow triggered automatic index/runtime data creation"
    }
    $result.reinstall_ok = $true

    $finalUninstaller = Get-ChildItem -Path $installDir -Filter "unins*.exe" | Select-Object -First 1
    if ($finalUninstaller) {
        Invoke-CheckedProcess -FilePath $finalUninstaller.FullName -Arguments @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LOG=$finalCleanupLogPath") -TimeoutSeconds 180
        if (Test-Path $installedExe) {
            throw "final cleanup uninstall did not remove the main executable"
        }
    }
    $result.final_cleanup_ok = $true
}
catch {
    $result.error = $_.Exception.Message
    $result | ConvertTo-Json -Depth 5
    exit 1
}

$result | ConvertTo-Json -Depth 5
exit 0
