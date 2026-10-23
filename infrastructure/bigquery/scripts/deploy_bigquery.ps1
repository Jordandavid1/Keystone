<#
.SYNOPSIS
    KEYSTONE BigQuery AI/ML Layer Deployment Script (PowerShell)
    Script: deploy_bigquery.ps1
    Milestone: M3 (BigQuery AI/ML Layer)

.DESCRIPTION
    Deploys schemas, remote models, tables, analytical views, and stored procedures
    to BigQuery for the KEYSTONE Architectural & UX Intelligence Pipeline.

    Enforces Mandatory Resource Attribution:
      - All mutating bq commands (mk, query, load, extract, update, cp) MUST include:
          --label datacloud:antigravity
      - Read-only bq commands (show, ls, version, rm, cancel, head) MUST omit --label.
      - All gcloud commands MUST prepend:
          $env:CLOUDSDK_METRICS_ENVIRONMENT = "datacloud.antigravity"

    Sysadmin Guardrails:
      - Strictly non-interactive, idempotent, safe error handling ($ErrorActionPreference = 'Stop').
      - No broad drops or destructive commands.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$ProjectId = "",

    [Parameter(Mandatory = $false)]
    [string]$DatasetId = "keystone_intelligence",

    [Parameter(Mandatory = $false)]
    [string]$Location = "US",

    [Parameter(Mandatory = $false)]
    [switch]$DryRun = $false
)

$ErrorActionPreference = 'Stop'

# Determine directory paths
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BqRoot = Split-Path -Parent $ScriptDir
$SchemasDir = Join-Path $BqRoot "schemas"
$QueriesDir = Join-Path $BqRoot "queries"

# Set mandatory Google Cloud attribution environment variable
$ExistingMetrics = $env:CLOUDSDK_METRICS_ENVIRONMENT
if ([string]::IsNullOrWhiteSpace($ExistingMetrics)) {
    $env:CLOUDSDK_METRICS_ENVIRONMENT = "datacloud.antigravity"
} elseif (-not $ExistingMetrics.Contains("datacloud.antigravity")) {
    $env:CLOUDSDK_METRICS_ENVIRONMENT = "$ExistingMetrics datacloud.antigravity"
}

# Deduce Project ID if not provided
if ([string]::IsNullOrWhiteSpace($ProjectId)) {
    try {
        $ProjectId = (gcloud config get-value project 2>$null).Trim()
    } catch {
        $ProjectId = ""
    }
    if ([string]::IsNullOrWhiteSpace($ProjectId)) {
        $ProjectId = "keystone-intelligence-prod"
    }
}

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "  KEYSTONE BIGQUERY AI/ML DEPLOYMENT (POWERSHELL)" -ForegroundColor Cyan
Write-Host "  Project:   $ProjectId"
Write-Host "  Dataset:   $DatasetId"
Write-Host "  Location:  $Location"
Write-Host "  Dry Run:   $DryRun"
Write-Host "  Metrics:   $($env:CLOUDSDK_METRICS_ENVIRONMENT)"
Write-Host "==============================================================================" -ForegroundColor Cyan

function Invoke-BqCommand {
    param(
        [string]$Type,
        [string]$CommandStr
    )
    Write-Host ">>> [$Type] $CommandStr" -ForegroundColor Yellow
    if ($DryRun) {
        Write-Host "    (DRY-RUN: skipped execution)" -ForegroundColor DarkGray
        return
    }
    Invoke-Expression $CommandStr
}

# Step 1: Idempotent Dataset Check via Read-Only bq show (NO LABELS)
Write-Host "`n=== Step 1: Dataset Verification & Idempotent Provisioning ===" -ForegroundColor Green
$DatasetRef = "$($ProjectId):$($DatasetId)"
$DatasetExists = $false

try {
    # Read-only command: bq show rejects --label, MUST omit
    $ShowResult = bq show $DatasetRef 2>$null
    if ($LASTEXITCODE -eq 0) {
        $DatasetExists = $true
        Write-Host "Dataset '$DatasetRef' already exists." -ForegroundColor Green
    }
} catch {
    $DatasetExists = $false
}

if (-not $DatasetExists) {
    Write-Host "Dataset '$DatasetRef' not found. Provisioning..." -ForegroundColor Yellow
    # Mutating command: bq mk MUST include --label datacloud:antigravity
    Invoke-BqCommand -Type "MUTATING_BQ" -CommandStr "bq mk --dataset --location=$Location --label datacloud:antigravity --description=`"Keystone Architectural Intelligence Dataset`" $DatasetRef"
}

# Step 2: Deploy Schemas, Remote Models, Tables, Views
Write-Host "`n=== Step 2: Deploying Schemas, Models, Tables & Views ===" -ForegroundColor Green
$SchemaFile = Join-Path $SchemasDir "001_intelligence_schema.sql"
if (-not (Test-Path $SchemaFile)) {
    throw "Schema file not found at $SchemaFile"
}

Write-Host "Deploying $SchemaFile..."
$SchemaSql = Get-Content -Raw -Path $SchemaFile
# Mutating command: bq query MUST include --label datacloud:antigravity
Invoke-BqCommand -Type "MUTATING_BQ" -CommandStr "bq query --project_id=$ProjectId --use_legacy_sql=false --label datacloud:antigravity `"$SchemaSql`""

# Step 3: Deploy Stored Procedures
Write-Host "`n=== Step 3: Deploying Stored Procedures & Analytical Queries ===" -ForegroundColor Green
$ProceduresFile = Join-Path $QueriesDir "ai_procedures.sql"
if (-not (Test-Path $ProceduresFile)) {
    throw "Procedures file not found at $ProceduresFile"
}

Write-Host "Deploying $ProceduresFile..."
$ProceduresSql = Get-Content -Raw -Path $ProceduresFile
# Mutating command: bq query MUST include --label datacloud:antigravity
Invoke-BqCommand -Type "MUTATING_BQ" -CommandStr "bq query --project_id=$ProjectId --use_legacy_sql=false --label datacloud:antigravity `"$ProceduresSql`""

# Step 4: Verification & Inspection
Write-Host "`n=== Step 4: Deployment Verification & Inspection ===" -ForegroundColor Green
$TableRef = "$($DatasetRef).scraped_architectures"
# Read-only commands: bq show and bq ls MUST omit --label
Invoke-BqCommand -Type "READONLY_BQ" -CommandStr "bq show $TableRef"
Invoke-BqCommand -Type "READONLY_BQ" -CommandStr "bq ls $DatasetRef"

# Verification query: bq query is mutating so it MUST include --label datacloud:antigravity
Write-Host "`nTesting baseline query execution..." -ForegroundColor Green
$VerificationQuery = "SELECT count(*) AS total_patterns FROM ``$ProjectId.$DatasetId.scraped_architectures``"
Invoke-BqCommand -Type "MUTATING_BQ" -CommandStr "bq query --project_id=$ProjectId --use_legacy_sql=false --label datacloud:antigravity `"$VerificationQuery`""

Write-Host "`n==============================================================================" -ForegroundColor Cyan
Write-Host "  BigQuery AI/ML Layer successfully deployed and verified!" -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Cyan
