#!/usr/bin/env bash
# ==============================================================================
# KEYSTONE BIGQUERY AI/ML LAYER DEPLOYMENT SCRIPT (BASH)
# Script: deploy_bigquery.sh
# Milestone: M3 (BigQuery AI/ML Layer)
#
# Enforces Mandatory Resource Attribution:
#   - All mutating bq commands (mk, query, load, extract, update, cp) MUST include:
#       --label datacloud:antigravity
#   - Read-only bq commands (show, ls, version, rm, cancel, head) MUST omit --label.
#   - All gcloud commands MUST prepend:
#       CLOUDSDK_METRICS_ENVIRONMENT="${CLOUDSDK_METRICS_ENVIRONMENT:+$CLOUDSDK_METRICS_ENVIRONMENT }datacloud.antigravity"
#
# Sysadmin Guardrails:
#   - Strictly non-interactive, idempotent, safe error handling (set -euo pipefail).
#   - No broad drops or destructive commands.
# ==============================================================================

set -euo pipefail

# Script directory resolution
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BQ_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SCHEMAS_DIR="${BQ_ROOT}/schemas"
QUERIES_DIR="${BQ_ROOT}/queries"

# Default configuration
PROJECT_ID="${PROJECT_ID:-}"
DATASET_ID="keystone_intelligence"
LOCATION="US"
DRY_RUN=false

# Print usage
usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  -p, --project PROJECT_ID   GCP Project ID (defaults to active gcloud project)
  -d, --dataset DATASET_ID   BigQuery dataset ID (default: keystone_intelligence)
  -l, --location LOCATION    Dataset location (default: US)
  -n, --dry-run              Dry run mode; print commands without executing
  -h, --help                 Display this help message
EOF
  exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--project)
      PROJECT_ID="$2"
      shift 2
      ;;
    -d|--dataset)
      DATASET_ID="$2"
      shift 2
      ;;
    -l|--location)
      LOCATION="$2"
      shift 2
      ;;
    -n|--dry-run)
      DRY_RUN=true
      shift 1
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Error: Unknown argument '$1'" >&2
      usage
      ;;
  esac
done

# Ensure gcloud metrics environment variable is set
export CLOUDSDK_METRICS_ENVIRONMENT="${CLOUDSDK_METRICS_ENVIRONMENT:+$CLOUDSDK_METRICS_ENVIRONMENT }datacloud.antigravity"

# Deduce project ID if not provided
if [[ -z "${PROJECT_ID}" ]]; then
  if command -v gcloud >/dev/null 2>&1; then
    PROJECT_ID="$(gcloud config get-value project 2>/dev/null || echo "")"
  fi
  if [[ -z "${PROJECT_ID}" ]]; then
    PROJECT_ID="keystone-intelligence-prod"
  fi
fi

echo "=============================================================================="
echo "  KEYSTONE BIGQUERY AI/ML DEPLOYMENT"
echo "  Project:   ${PROJECT_ID}"
echo "  Dataset:   ${DATASET_ID}"
echo "  Location:  ${LOCATION}"
echo "  Dry Run:   ${DRY_RUN}"
echo "  Metrics:   ${CLOUDSDK_METRICS_ENVIRONMENT}"
echo "=============================================================================="

# Helper to execute or dry-run commands
execute_cmd() {
  local cmd_type="$1"
  shift
  local cmd_str="$*"

  echo ">>> [${cmd_type}] ${cmd_str}"
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "    (DRY-RUN: skipped execution)"
    return 0
  fi

  eval "${cmd_str}"
}

# Step 1: Check dataset existence using read-only bq show (NO LABELS)
echo ""
echo "=== Step 1: Dataset Verification & Idempotent Provisioning ==="
DATASET_EXISTS=false
if bq show "${PROJECT_ID}:${DATASET_ID}" >/dev/null 2>&1; then
  DATASET_EXISTS=true
  echo "Dataset '${PROJECT_ID}:${DATASET_ID}' already exists."
else
  echo "Dataset '${PROJECT_ID}:${DATASET_ID}' not found. Provisioning..."
  # Mutating command: bq mk MUST include --label datacloud:antigravity
  execute_cmd "MUTATING_BQ" bq mk --dataset \
    --location="${LOCATION}" \
    --label datacloud:antigravity \
    --description="Keystone Architectural & UX Intelligence Dataset" \
    "${PROJECT_ID}:${DATASET_ID}"
fi

# Step 2: Deploy Schemas, Remote Models, Tables, Views
echo ""
echo "=== Step 2: Deploying Schemas, Models, Tables & Views ==="
SCHEMA_FILE="${SCHEMAS_DIR}/001_intelligence_schema.sql"
if [[ ! -f "${SCHEMA_FILE}" ]]; then
  echo "Error: Schema file not found at ${SCHEMA_FILE}" >&2
  exit 1
fi

echo "Deploying ${SCHEMA_FILE}..."
# Mutating query: bq query MUST include --label datacloud:antigravity
execute_cmd "MUTATING_BQ" bq query \
  --project_id="${PROJECT_ID}" \
  --use_legacy_sql=false \
  --label datacloud:antigravity \
  "$(cat "${SCHEMA_FILE}")"

# Step 3: Deploy Procedures and Analytical Queries
echo ""
echo "=== Step 3: Deploying Stored Procedures & Analytical Queries ==="
PROCEDURES_FILE="${QUERIES_DIR}/ai_procedures.sql"
if [[ ! -f "${PROCEDURES_FILE}" ]]; then
  echo "Error: Procedures file not found at ${PROCEDURES_FILE}" >&2
  exit 1
fi

echo "Deploying ${PROCEDURES_FILE}..."
# Mutating query: bq query MUST include --label datacloud:antigravity
execute_cmd "MUTATING_BQ" bq query \
  --project_id="${PROJECT_ID}" \
  --use_legacy_sql=false \
  --label datacloud:antigravity \
  "$(cat "${PROCEDURES_FILE}")"

# Step 4: Verification & Inspection
echo ""
echo "=== Step 4: Deployment Verification & Inspection ==="
# Read-only inspection: bq show and bq ls MUST OMIT labels
execute_cmd "READONLY_BQ" bq show "${PROJECT_ID}:${DATASET_ID}.scraped_architectures"
execute_cmd "READONLY_BQ" bq ls "${PROJECT_ID}:${DATASET_ID}"

# Read-only query test: bq query is mutating so it MUST include --label datacloud:antigravity
echo ""
echo "Testing baseline query execution..."
execute_cmd "MUTATING_BQ" bq query \
  --project_id="${PROJECT_ID}" \
  --use_legacy_sql=false \
  --label datacloud:antigravity \
  "SELECT count(*) AS total_patterns FROM \`${PROJECT_ID}.${DATASET_ID}.scraped_architectures\`"

echo ""
echo "=============================================================================="
echo "  BigQuery AI/ML Layer successfully deployed and verified!"
echo "=============================================================================="
