<#
.SYNOPSIS
    KEYSTONE Full-Stack Turnkey Launcher (ComfyUI + FastAPI + Next.js Studio + Edge)
.DESCRIPTION
    Starts local ComfyUI (127.0.0.1:8188), FastAPI Backend (127.0.0.1:8000),
    and Next.js Web Studio (http://localhost:3001), wires COMFY_BASE_URL,
    verifies live HTTP 200 readiness across all services, and opens Microsoft Edge.
#>
param(
    [int]$WebPort = 3001,
    [int]$ApiPort = 8000,
    [int]$ComfyPort = 8188,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Continue'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RunDir = Join-Path $RepoRoot ".run"
if (-not (Test-Path $RunDir)) { New-Item -ItemType Directory -Path $RunDir -Force | Out-Null }

function Test-HttpOk([string]$Url, [int]$TimeoutSec = 2) {
    try {
        $resp = Invoke-WebRequest -Uri $Url -Method Get -UseBasicParsing -TimeoutSec $TimeoutSec
        return ($resp.StatusCode -eq 200)
    } catch {
        return $false
    }
}

Write-Host "=== [1/3] Checking ComfyUI Server (127.0.0.1:$ComfyPort) ===" -ForegroundColor Cyan
$ComfyUrl = "http://127.0.0.1:$ComfyPort"
if (-not (Test-HttpOk "$ComfyUrl/system_stats")) {
    $ComfyDir = Join-Path $HOME "ComfyUI"
    if (Test-Path (Join-Path $ComfyDir "main.py")) {
        $ComfyPy = Join-Path $ComfyDir "venv\Scripts\python.exe"
        if (-not (Test-Path $ComfyPy)) { $ComfyPy = "python" }
        $cudaCheck = & $ComfyPy -c "import torch; print('1' if torch.cuda.is_available() else '0')" 2>$null
        $comfyArgs = @("main.py", "--listen", "127.0.0.1", "--port", "$ComfyPort")
        if ($cudaCheck -notmatch "1") { $comfyArgs += "--cpu" }
        Start-Process -FilePath $ComfyPy -ArgumentList $comfyArgs -WorkingDirectory $ComfyDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $RunDir "comfyui.out.log") -RedirectStandardError (Join-Path $RunDir "comfyui.err.log")
        Write-Host "    Spawned ComfyUI daemon from $ComfyDir..." -ForegroundColor Yellow
    }
}

Write-Host "=== [2/3] Checking FastAPI Backend (127.0.0.1:$ApiPort) ===" -ForegroundColor Cyan
$env:COMFY_BASE_URL = $ComfyUrl
$env:KEYSTONE_COMFY_URL = $ComfyUrl
$env:KEYSTONE_WEB_URL = "http://localhost:$WebPort"
$ApiUrl = "http://127.0.0.1:$ApiPort"
if (-not (Test-HttpOk "$ApiUrl/v1/health")) {
    $ApiPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    Start-Process -FilePath $ApiPy -ArgumentList @("-m", "uvicorn", "apps.api.src.server:app", "--host", "127.0.0.1", "--port", "$ApiPort") -WorkingDirectory $RepoRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $RunDir "api.out.log") -RedirectStandardError (Join-Path $RunDir "api.err.log")
    Write-Host "    Spawned FastAPI backend on $ApiUrl..." -ForegroundColor Yellow
}

Write-Host "=== [3/3] Checking Next.js Web Studio (http://localhost:$WebPort) ===" -ForegroundColor Cyan
$WebUrl = "http://localhost:$WebPort"
if (-not (Test-HttpOk $WebUrl)) {
    $WebDir = Join-Path $RepoRoot "apps\web"
    Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "npx next dev -p $WebPort") -WorkingDirectory $WebDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $RunDir "web.out.log") -RedirectStandardError (Join-Path $RunDir "web.err.log")
    Write-Host "    Spawned Next.js Studio on $WebUrl..." -ForegroundColor Yellow
}

Write-Host "=== Waiting for services to report HTTP 200 ===" -ForegroundColor Cyan
for ($i = 0; $i -lt 45; $i++) {
    $apiOk = Test-HttpOk "$ApiUrl/v1/health"
    $webOk = Test-HttpOk $WebUrl
    $comfyOk = Test-HttpOk "$ComfyUrl/system_stats"
    if ($apiOk -and $webOk -and $comfyOk) { break }
    Start-Sleep -Seconds 2
}

try {
    Invoke-RestMethod -Uri "$ApiUrl/v1/studio/engine/configure" -Method Post -ContentType "application/json" -Body (@{ comfy_base_url = $ComfyUrl } | ConvertTo-Json) -TimeoutSec 5 | Out-Null
} catch {}

Write-Host "API Health    : $(Test-HttpOk "$ApiUrl/v1/health") ($ApiUrl)" -ForegroundColor Green
Write-Host "Web Studio    : $(Test-HttpOk $WebUrl) ($WebUrl)" -ForegroundColor Green
Write-Host "ComfyUI + H3  : $(Test-HttpOk "$ComfyUrl/system_stats") ($ComfyUrl)" -ForegroundColor Green

if (-not $NoBrowser) {
    $EdgeExe = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if (Test-Path $EdgeExe) {
        Start-Process $EdgeExe $WebUrl
    }
}
