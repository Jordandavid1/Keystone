# KEYSTONE Terms of Service

**Effective Date:** January 1, 2026  
**Last Updated:** November 23, 2026  
**Ownership:** Jordan Maxwell. All rights reserved.  

## 1. Acceptance of Terms
By accessing or using the KEYSTONE platform, API, Studio web interface, or worker infrastructure, you agree to be bound by these Terms of Service and confirm compliance with applicable laws in your jurisdiction.

## 2. Age Requirement & Content Mode Governance
- Access to KEYSTONE `unrestricted` mode requires explicit adult verification (18+): Stage-1 attestation (`POST /v1/account/age-verification`) and/or Stage-2 card/adult-processor verification (`POST /v1/billing/webhooks/adult-processor`).
- Accounts default to `sfw` mode. Misrepresenting age status or attempting to bypass the Gate or lawful-content floor is prohibited and grounds for immediate termination.

## 3. Proprietary Ownership & Sovereign Prompt Governance
KEYSTONE is proprietary, closed-source software owned by Jordan Maxwell. Customers receive a revocable, non-transferable license to access hosted services according to plan terms. KEYSTONE alone compiles prompts, evaluates lawful floors, enforces mode separation, issues signed v2 `ExecutionEnvelope` tokens, and stamps C2PA Content Credentials provenance on generated outputs.

## 4. Dual-Rail Billing, Credits & Provenance
Generative executions hold credits transactionally prior to dispatch and settle upon verified completion (`vram_minutes`, `eval_seconds` usage records) or release in full on failure. Mainstream payment processors (Stripe) process `sfw` mode transactions only; `unrestricted` billing requires a sanctioned adult payment rail or crypto processor.

## 5. Limitation of Liability
KEYSTONE is provided "as is". In no event shall Jordan Maxwell or KEYSTONE operators be liable for indirect, incidental, punitive, or consequential damages arising from model outputs or third-party integrations.
