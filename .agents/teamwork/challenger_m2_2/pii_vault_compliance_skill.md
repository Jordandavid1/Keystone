# PII Vault & Enterprise Compliance Skill
Copied from C:\Users\Lesia Eden\.gemini\config\skills\pii-vault-compliance\SKILL.md

Enterprise patterns for GDPR Article 17, SOC2 data isolation, AES-256-GCM tokenization, zero-PII LLM context minimization, and Aikido prompt injection defense.

## Core Principles:
1. Context Minimization (Zero Plain PII to LLM): AES-256-GCM vault tokenization, reference passing, rehydration only at final transactional dispatch step.
2. GDPR Article 17 Cascading Erasure: Vault erasure, signal retention purge, queue cascade, audit logging, idempotency (subsequent purges return HTTP 200 with erasedCount: 0).
3. Aikido Prompt Injection Defense: Delimiter containment (<untrusted_content>), tag scrubbing (escaping literal </untrusted_content>), post-generation sanitization.
4. Client Response Masking: Masking emails/PII in API responses.
