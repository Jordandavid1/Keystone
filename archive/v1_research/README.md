# Archived v1 Research Track (`intelligence` + `bigquery`)

**Archived in:** Pre-PR1 Cleanup (ADR-004 D13)  
**Date:** 2026-11-23  
**Rollback tag:** `bible-v1-final`

## Why Archived

Per **KEYSTONE Bible v2 §2 Invariant 2**, **§31**, **§42**, and **ADR-004 (D13)**:

- `services/intelligence/` (10 mocked Node.js scraper/BigQuery files with zero runtime callers in `apps/api/src/`) and `infrastructure/bigquery/` (Vertex AI `gemini-2.5-flash` + `text-embedding-005` SQL scripts) were an early UX-benchmarking research sprint.
- Calling Google's closed, aligned `gemini-2.5-flash` violated KEYSTONE's No Outer Alignment & Single Prompting Authority invariants.
- BigQuery's semantic search role is superseded by **Bible v2 §42 (Memory & Recipe Library)** backed by PostgreSQL + `pgvector` and local Qwen embeddings (zero external embedding vendors).
- The accompanying Run 1 JS test fixtures (`tests_e2e_run1/`, `adversarial_security_suite.js`) are preserved here for historical traceability.
