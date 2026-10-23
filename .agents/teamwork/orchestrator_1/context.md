# Context Tracking

## Workspace Details
- Project root: `c:\Users\Lesia Eden\Downloads\keystone-cowork`
- Dedicated orchestrator directory: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_1`
- Parent conversation ID: `fdb557b8-e3bb-468a-8845-79517375cf4b` (Sentinel)
- Authoritative request: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md`

## Invariants & Critical Instructions
1. DO NOT MODIFY OR OVERWRITE ANY PRE-BUILT CODE. Build strictly additively.
2. Baseline tests (`npm test`) must remain 100% green at all times.
3. Orchestrator never writes application code directly, never runs test commands directly — delegate all technical tasks to subagents.
4. Forensic auditor verdict is a binary veto.
5. PII Vault: AES-256-GCM tokenization, GDPR Article 17 erasure, zero plain PII in model contexts.
6. Aikido Defense: `<untrusted_content>` containment, tag escaping, post-generation sanitization.
7. BigQuery AI/ML: `AI.GENERATE`, `AI.GENERATE_EMBEDDING`, `AI.SIMILARITY`, `AI.CLASSIFY` with mandatory resource attribution labeling.
