# KEYSTONE Premium Local & Self-Hosted License Agreement

**Effective Date:** January 1, 2026  
**Ownership:** Jordan Maxwell  

## 1. Scope of Local Execution
This Agreement governs Enterprise and Studio customers authorized to deploy KEYSTONE creative workers on self-hosted or dedicated hardware (on-premises GPUs or private clusters).

## 2. Invariant Adherence
Local workers must:
- Connect securely via TLS tunnels using authorized API tokens.
- Execute only cryptographically signed `ExecutionEnvelope` tokens issued by the sovereign KEYSTONE Authority Engine.
- Never mutate compiled prompts or modify prompt provenance hashes.
- Return structured `HarnessResult` telemetry to the central ledger.

## 3. Auditing & Revocation
Jordan Maxwell reserves the right to audit local worker conformance and revoke tunnel authorizations upon detection of unsigned envelopes or license breaches.
