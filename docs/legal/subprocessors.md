# KEYSTONE Subprocessor Inventory

**Effective Date:** January 1, 2026  
**Last Updated:** November 23, 2026  
**Ownership:** Jordan Maxwell  

## Authorized Infrastructure & Payment Subprocessors
KEYSTONE engages strictly bounded third-party infrastructure and dual-rail payment processors. **Zero closed-source external LLM or embedding API vendors** receive user prompts or generated assets:

1. **Google Cloud Platform (GCP):**
   - **Services:** Cloud Run (container hosting), Cloud SQL (PostgreSQL + `pgvector` database), Cloud Storage (encrypted asset binaries), Secret Manager.
   - **Location:** United States.
   - **Compliance:** SOC 1/2/3, ISO/IEC 27001, GDPR.

2. **Stripe, Inc. (SFW Payment Rail Only):**
   - **Services:** Mainstream SFW checkout sessions, subscription billing, and HMAC-verified webhooks strictly restricted to `sfw` mode.
   - **Location:** United States.
   - **Compliance:** PCI-DSS Level 1.

3. **Dedicated Adult Payment Processor Rail / Crypto Settlement (UNRESTRICTED Rail Only):**
   - **Services:** Stage-2 card/processor age verification (`card_adult_processor`) and credit deposits for `unrestricted` creative workloads via HMAC-signed webhooks (`/v1/billing/webhooks/adult-processor`).
   - **Compliance:** PCI-DSS / 2257 billing-rail compliance isolation (strictly segregated from Stripe SFW transactions).

4. **Operator / Kaggle Ephemeral GPU Worker Pool:**
   - **Services:** Ephemeral GPU worker nodes executing pinned open weights (`OBLITERATUS/Qwen3.8-27B-OBLITERATED`, `Qwen/Qwen3-Embedding-0.6B-GGUF`, ComfyUI / MiniMax H3 / Wan2.1) strictly under signed `ExecutionEnvelope` v2 verification.
   - **Zero External Aligned API Vendors:** No user prompts, embeddings, or images are routed to OpenAI, Anthropic, or Google Gemini external inference endpoints.
