# KEYSTONE Privacy Policy

**Effective Date:** January 1, 2026  
**Last Updated:** November 23, 2026  
**Ownership:** Proprietary software owned by Jordan Maxwell  

## 1. Introduction & Sovereign Data Commitment
KEYSTONE ("we", "us", "our") provides an authoritative prompt-intelligence engine, multimodal reasoning core, and generative studio platform. Your tenant workspace, creative assets, personas, project memories, and billing records are isolated per user tenant in sovereign storage and PostgreSQL (`+pgvector`).

## 2. Personal Information & Records Posture
- **Account & Age Verification Data:** Email address, user identifier, hashed credentials, and Stage-1/Stage-2 age verification metadata (`age_verified`, `age_verified_at`, `age_verification_method`). No raw government IDs or raw payment card numbers are stored on KEYSTONE infrastructure.
- **Dual-Rail Billing Records:** Append-only `credit_ledger` entries and `usage_records` scoped by payment processor rail (`stripe` strictly for SFW; dedicated adult processor / crypto rail for UNRESTRICTED).
- **Creative Inputs & Content Credentials:** Prompts, uploaded reference media, personas, recipes, `pgvector` embeddings, and signed **C2PA Content Credentials** (`c2pa_manifest`, cryptographic `asset_sha256`, platform provenance) stamped with dedicated key `KEYSTONE_C2PA_SIGNING_KEY`.
- **Audit & Evaluation Telemetry:** Gate `authority_decisions`, `harness_runs` quality evaluations, and execution telemetry.

## 3. PII Vault & Local Self-Hosted Inference Invariant
Untrusted inputs and scraped content are scrubbed at the boundary and tokenized with AES-256-GCM before model invocation. All reasoning (`OBLITERATUS/Qwen3.8-27B-OBLITERATED`), local embeddings (`Qwen/Qwen3-Embedding-0.6B-GGUF`), and visual generation run strictly on self-hosted/operator worker infrastructure with zero closed external AI vendors.

## 4. GDPR Article 17 ("Right to Erasure")
Users maintain the right to request cascading erasure (`GdprErasureService`) across DB accounts, sessions, messages, assets, backing Cloud Storage objects, personas, recipes, style rules, API keys, and vaulted PII tokens, while retaining immutable accounting ledger obligations in anonymized form.

## 5. Contact
For privacy inquiries or data subject access requests: privacy@keystone.ai
