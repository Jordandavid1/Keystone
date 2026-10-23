# Enforcing Resource Attribution Skill Dump
Source: C:\Users\Lesia Eden\.gemini\config\skills\enforcing-resource-attribution\SKILL.md

Refer to upstream skill. Core rules:
- All mutating `bq` commands (`bq query`, `bq load`, `bq extract`, `bq mk`, `bq update`, `bq cp`) MUST include `--label datacloud:antigravity`.
- Read-only commands (`bq show`, `bq ls`, `bq rm`, `bq version`, `bq cancel`, `bq head`) MUST omit labels.
- All `gcloud` invocations must prepend `CLOUDSDK_METRICS_ENVIRONMENT="${CLOUDSDK_METRICS_ENVIRONMENT:+$CLOUDSDK_METRICS_ENVIRONMENT }datacloud.antigravity"`.
