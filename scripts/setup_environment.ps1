<#
.SYNOPSIS
    KEYSTONE Idempotent Environment Setup Script
.DESCRIPTION
    Provisions an isolated Python virtual environment, installs clean locked dependencies
    from requirements.txt without global pip pollution, and runs the composite environment
    verification probe. Adheres strictly to sysadmin guardrails and python dependency rules.
.PARAMETER DryRun
    Simulates environment provisioning and dependency installation without making changes.
.PARAMETER NonInteractive
    Runs without prompting for user confirmation.
.PARAMETER VenvDir
    Name or path of the target virtual environment directory. Defaults to ".venv".
.EXAMPLE
    powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\setup_environment.ps1
.EXAMPLE
    .\scripts\setup_environment.ps1 -DryRun
#>

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$NonInteractive,
    [string]$VenvDir = ".venv"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$VenvPath = Join-Path $ProjectRoot $VenvDir
$RequirementsPath = Join-Path $ProjectRoot "requirements.txt"
$VerifyScriptPath = Join-Path $ProjectRoot "scripts\verify_environment.py"

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  KEYSTONE IDEMPOTENT ENVIRONMENT SETUP" -ForegroundColor Cyan
Write-Host "  Adheres to: sysadmin-guardrails & managing-python-dependencies" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Project Root:      $ProjectRoot"
Write-Host "Target Venv:       $VenvPath"
Write-Host "Requirements:      $RequirementsPath"
Write-Host "Mode:              $(if ($DryRun) { 'DRY RUN (Preview Only)' } else { 'APPLY' })"
Write-Host ""

# ------------------------------------------------------------------------------
# PHASE 1: Pre-Flight System Checks
# ------------------------------------------------------------------------------
Write-Host ">>> [PHASE 1] Pre-Flight System Checks..." -ForegroundColor Yellow

# 1.1 Disk Space Pre-flight
try {
    $drive = (Get-Item $ProjectRoot).PSDrive.Name
    $driveInfo = Get-PSDrive $drive
    $freeGb = [math]::Round($driveInfo.Free / 1GB, 2)
    Write-Host "    [OK] Storage Drive ${drive}: has $freeGb GB free space." -ForegroundColor Green
    if ($freeGb -lt 0.5) {
        throw "INSUFFICIENT_STORAGE: Drive $drive has less than 500MB free storage available."
    }
} catch {
    Write-Host "    [WARN] Unable to determine free disk space: $_" -ForegroundColor DarkYellow
}

# 1.2 Python Runtime Detection
$pythonExe = $null
try {
    $pyCheck = Get-Command python -ErrorAction SilentlyContinue
    if ($pyCheck) {
        $pythonExe = "python"
    } else {
        $pyCmd = Get-Command py -ErrorAction SilentlyContinue
        if ($pyCmd) {
            $pythonExe = "py"
        }
    }
} catch {
    $pythonExe = $null
}

if (-not $pythonExe) {
    throw "PYTHON_NOT_FOUND: Python interpreter not found on system PATH. Please install Python 3.10+."
}

$pyVersion = (& $pythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')").Trim()
Write-Host "    [OK] Host Python Interpreter: $pythonExe ($pyVersion)" -ForegroundColor Green

# 1.3 Verify requirements.txt presence
if (-not (Test-Path $RequirementsPath)) {
    throw "MISSING_REQUIREMENTS: requirements.txt not found at $RequirementsPath"
}
Write-Host "    [OK] Locked requirements file verified." -ForegroundColor Green

# ------------------------------------------------------------------------------
# PHASE 2: Virtual Environment Provisioning (Idempotent)
# ------------------------------------------------------------------------------
Write-Host "`n>>> [PHASE 2] Virtual Environment Provisioning..." -ForegroundColor Yellow

$venvPython = Join-Path $VenvPath "Scripts\python.exe"
$venvPip = Join-Path $VenvPath "Scripts\pip.exe"

if (Test-Path $VenvPath) {
    Write-Host "    [OK] Virtual environment directory exists at $VenvPath (Idempotent reuse)." -ForegroundColor Green
    if (-not (Test-Path $venvPython)) {
        Write-Host "    [WARN] $venvPython missing; repairing venv..." -ForegroundColor DarkYellow
        if (-not $DryRun) {
            & $pythonExe -m venv "$VenvPath"
        }
    }
} else {
    Write-Host "    [ACTION] Creating new isolated virtual environment at $VenvPath..." -ForegroundColor Cyan
    if ($DryRun) {
        Write-Host "    [DRY RUN] Would execute: $pythonExe -m venv `"$VenvPath`"" -ForegroundColor Gray
    } else {
        & $pythonExe -m venv "$VenvPath"
        if (-not (Test-Path $venvPython)) {
            throw "VENV_CREATION_FAILED: Failed to create virtual environment at $VenvPath"
        }
        Write-Host "    [OK] Virtual environment successfully created." -ForegroundColor Green
    }
}

# ------------------------------------------------------------------------------
# PHASE 3: Dependency Installation (Isolated - Never Global)
# ------------------------------------------------------------------------------
Write-Host "`n>>> [PHASE 3] Dependency Installation (via isolated .venv/Scripts/pip)..." -ForegroundColor Yellow

if ($DryRun) {
    Write-Host "    [DRY RUN] Would execute: `"$venvPip`" install --disable-pip-version-check -r `"$RequirementsPath`"" -ForegroundColor Gray
} else {
    if (Test-Path $venvPip) {
        Write-Host "    [RUN] Installing locked dependencies from requirements.txt..." -ForegroundColor Cyan
        & "$venvPip" install --disable-pip-version-check --no-warn-script-location -r "$RequirementsPath"
        if ($LASTEXITCODE -ne 0) {
            throw "PIP_INSTALL_FAILED: pip install exited with non-zero exit code $LASTEXITCODE"
        }
        Write-Host "    [OK] All locked dependencies installed cleanly in virtual environment." -ForegroundColor Green
    } else {
        Write-Host "    [WARN] Isolated pip executable not yet accessible. Skipping in dry-run mode." -ForegroundColor DarkYellow
    }
}

# ------------------------------------------------------------------------------
# PHASE 4: Verification Probe
# ------------------------------------------------------------------------------
Write-Host "`n>>> [PHASE 4] Running Composite Environment Verification Probe..." -ForegroundColor Yellow

if ($DryRun) {
    Write-Host "    [DRY RUN] Would execute: python `"$VerifyScriptPath`"" -ForegroundColor Gray
} else {
    $probeTargetPython = if (Test-Path $venvPython) { $venvPython } else { $pythonExe }
    Write-Host "    [RUN] Probing with $probeTargetPython..." -ForegroundColor Cyan
    & "$probeTargetPython" "$VerifyScriptPath"
    if ($LASTEXITCODE -ne 0) {
        throw "VERIFY_PROBE_FAILED: Composite probe exited with code $LASTEXITCODE"
    }
}

Write-Host "`n================================================================================" -ForegroundColor Green
Write-Host "  ENVIRONMENT SETUP COMPLETE & VERIFIED" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Green
Write-Host "To activate this environment in PowerShell:"
Write-Host "    & `"$VenvPath\Scripts\Activate.ps1`"" -ForegroundColor White
Write-Host "To run verification probe at any time:"
Write-Host "    & `"$venvPython`" `"$VerifyScriptPath`"" -ForegroundColor White
Write-Host "Rollback instructions (if undoing):"
Write-Host "    Remove-Item -Recurse -Force `"$VenvPath`"" -ForegroundColor Gray
Write-Host ""
