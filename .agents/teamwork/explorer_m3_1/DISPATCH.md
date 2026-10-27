## 2026-10-23T06:55:26Z
You are explorer_m3_1, a teamwork_preview_explorer subagent for Milestone M3 (Wave 3: Cognition & Authority).
Your parent is the Project Orchestrator (Conversation ID: 6f59f58e-8034-400a-bd25-c869a10728f4).
Your dedicated working directory is: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m3_1

MANDATORY INPUTS:
- Read ORIGINAL_REQUEST.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md
- Read KEYSTONE_BIBLE.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\KEYSTONE_BIBLE.md (§11 Cognition, §12 ProposedAction, §13 Authority Engine, §14 ExecutionEnvelope, §24 Kaggle Tier 0, §33 Wave 3)
- Read PROJECT.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_2\PROJECT.md
- Inspect packages/contracts/src/models.py and services/cognition/src/client.py

OBJECTIVE:
Investigate, design, and produce the comprehensive architectural blueprint for Milestone M3 (Wave 3: Cognition & Authority):
1. F14: ProposedAction Structured Output & Capability Typing:
   - Design strictly-typed ProposedAction schema and validator supporting all 6 action types (`generate`, `edit`, `variate`, `animate`, `upscale`, `analyze`) across 6 capability namespaces.
   - Design parameter constraint validation, estimated credit calculation rules, and fallback handling.
2. F15: Authority Decision Engine (services/authority/src/):
   - Design AuthorityEngine and Evaluator evaluating ProposedAction against:
     a) Safety & prompt policy invariants (forbidden terms, destructive operations).
     b) Tenant credit balance (verify available credits >= estimated_credits).
     c) Parameter boundary validation (resolution ceilings, aspect ratio whitelist).
   - Generates AuthorityDecision (ALLOW, DENY, REQUIRE_CONFIRMATION) with audit event emission into audit_events.
3. F16: Kaggle Memory Harness & Hardware Probe (KAGGLE_SETUP/scripts/probe_hardware.py):
   - Design hardware probe measuring 2x Nvidia T4 (16GB VRAM each, total 32GB, TP=2).
   - Calculation of remaining BF16 weights (~26.7GB) CPU-offload into Kaggle host RAM (~80GB pool).
   - Define 7 retry profiles (vanilla, memory-conserve, swap-heavy, offload-fallback, context-truncate, etc.).
4. F17: Kaggle Worker Bridge & Ephemeral Registration (services/harness/src/worker_bridge.py):
   - Design worker registration endpoint POST /internal/workers/register.
   - Ephemeral tunnel handshake (Cloudflare / ngrok tunnel URL), worker capability registration, health check loop (30s heartbeat).
5. F18: Signed Execution Envelope Engine (services/harness/src/envelope.py):
   - Design ExecutionEnvelope generation with HMAC-SHA256 signature and single-use nonce.
   - Nonce management & replay attack prevention (TTL cache).
   - Expiration and clock skew tolerance (300s window).
6. Design additive REST API routers for M3 and integration with apps/api/src/server.py.
7. Design comprehensive test suite for M3 (tests/e2e_v2/test_m3_cognition_authority.py).
8. Write comprehensive blueprint to: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m3_1\m3_cognition_authority_blueprint.md
9. Write handoff to: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m3_1\handoff.md
10. Send completion message to parent when done. Do NOT modify source files.
