# Enforcing Resource Attribution Skill (Local Copy)
Source: C:\Users\Lesia Eden\.gemini\config\skills\enforcing-resource-attribution\SKILL.md
Methodology: Apply `--label datacloud:antigravity` only to mutating `bq` commands (query, load, extract, mk, update, cp). Do NOT apply to read-only `bq` commands (show, ls, version, rm, cancel, head). Prepend `CLOUDSDK_METRICS_ENVIRONMENT` to `gcloud` commands.
