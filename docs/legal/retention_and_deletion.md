# KEYSTONE Data Retention and Deletion Policy

**Effective Date:** January 1, 2026  
**Last Updated:** November 23, 2026  
**Ownership:** Jordan Maxwell  

## 1. Asset, Credentials & Memory Retention Windows
- **Workspace Assets & Lineage:** Retained while active and tenant-owned (`deleted_at IS NULL`), served exclusively via short-expiry (900s) signed URLs with HTTP Range 206 support and `X-Content-Type-Options: nosniff`.
- **C2PA Content Credentials:** Cryptographically signed C2PA manifests (`assets.c2pa_manifest`) are stored alongside asset checksums for verifiable output provenance until asset deletion or account erasure.
- **Project Recipes & Embeddings:** Retained within tenant/project/mode isolation (`recipes`, `recipe_embeddings`, `style_rules`); mature (`unrestricted`) recipes never surface under SFW retrieval.
- **Authority Decisions, Evaluations & Audit Logs:** Gate decisions (`authority_decisions`), 5-family quality evaluations (`harness_runs`), and security audit trails (`audit_events`) are retained for forensic auditability and billing reconciliation.

## 2. User-Initiated Erasure (GDPR Article 17)
Executing cascading erasure (`GdprErasureService.cascade_erase_user` / `cascade_erase_user_async`):
1. Soft-deletes user `assets` (clearing `c2pa_manifest`) and deletes backing storage objects from Cloud Storage.
2. Deletes user conversation `messages`, `sessions`, `recipes`, and `style_rules`, revokes all `api_keys`, and soft-deletes `projects` and `personas`.
3. Redacts User account PII (`email`, `display_name`, credentials, verification method).
4. Preserves immutable statutory accounting ledger rows (`credit_ledger` / `usage_records`) in anonymized form (`ANONYMIZED_GDPR_USER`) without violating append-only database immutability triggers.
