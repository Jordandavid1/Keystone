# KEYSTONE Identity Preservation Contract

## Preserved from yerrrrr.zip

- Product name: KEYSTONE
- Positioning: Same AI. Expert results.
- Product category: prompt-intelligence platform
- Core compatibility interface: `generate(goal, options) -> plan.v1`
- Six-part PromptAnatomy
- Thirteen domain playbooks (extended to sixteen by the amendment below)
- Ordered, finishable steps and done-when deliverables
- Assumption-driven planning and capped clarifying questions
- Decoupled, model-agnostic prompt compiler
- Local heuristic fallback
- Prompt cards, intent, path, and refinement concepts

## Evolved without replacing identity

- KEYSTONE becomes sole prompting authority for cognitive and generative models.
- Qwen becomes an embedded cognitive runtime behind an adapter.
- Capability manifests allow tools to contribute expertise.
- Authority and execution envelopes protect tool boundaries.
- Harnesses create bounded feedback and quality loops.
- PostgreSQL, Redis/Celery, object storage, subscriptions and a premium workspace add product infrastructure.

## Extended playbook catalog (amendment 2026-11-01)

The original thirteen playbooks are preserved unchanged and remain first-class prompt-engine data. Three extended operating modes were added on top of them, bringing the catalog to sixteen:

| # | id | Label | Guardrail carried in the playbook |
|---|----|-------|----------------------------------|
| 14 | `nsfw` | Mature and adult creative work | 18+ gated audience; rating slot defaults to "suggestive rather than explicit" |
| 15 | `hacker` | Security research and red team | written authorization / owned-or-authorized systems only; lab or staging target |
| 16 | `freedom` | Freedom mode (YOLO) | scope bounded to the stated objective; reversible changes only |

Aliases resolve onto these ids: `nsfw_mode` / `adult` -> `nsfw`; `hacker_mode` / `hacking` / `red_team` -> `hacker`; `yolo` / `yolo_mode` / `unrestricted` / `fully_unrestricted` / `full_freedom` -> `freedom`. Unknown ids continue to fall back to `general`.

The catalog is owned by `packages/prompt_engine/playbooks.py` (authoritative runtime registry) and mirrored in `packages/prompt-engine/src/playbooks.js`. `apps/api/src/server.py` (`/v1/contracts`) and `apps/web/app.js` (`PLAYBOOKS_16`) enumerate the same sixteen, and the pre-built manifest entries for the two baseline engine files were re-pinned to their amended bytes.

## Locked invariant (Bible §2, Invariant 14)

Amended canonical text:

> The original thirteen domain playbooks remain first-class prompt-engine data, joined by three extended operating modes (14 NSFW, 15 Hacker, 16 Freedom/YOLO) for sixteen playbooks total.

What the lock guarantees:

- All thirteen original ids remain loadable, first-class data with a six-step path each: `software`, `writing`, `marketing`, `business`, `learning`, `career`, `content`, `research`, `design`, `fitness`, `events`, `finance`, `general`.
- The three extended modes remain resolvable by id and by alias. Removing one is an identity change and falls under Bible §37 change control, not routine refactoring.
- Playbooks are additive only: none may be renamed, merged, reordered out of existence, or repurposed away from its domain.
- `general` remains the fallback for unrecognized playbook ids, so unknown input never fails compilation.
- Every playbook keeps the six-step path shape required by `plan.v1` and the six-part `PromptAnatomy`, so the compiler contract is unchanged by the extension.
- The amended Bible is pinned at `3BFF4E7063733146B663BDBE9C9BAD7271D480152243A05542F256DC05E7B25D` (39,830 bytes) in `scripts/verify_invariants.py` (`BIBLE_EXPECTED_SHA256` / `BIBLE_EXPECTED_SIZE`), the E2E oracle, the tier-1 checksum test, and the OpenAPI description in `apps/api/src/server.py`.

## Explicitly excluded

The source archive also contains unrelated Triton/background-check automation, government-ID staging instructions, browser-session automation, compiled caches, screenshots containing personal data, and Git internals. Those are not KEYSTONE product identity and are not copied into this repo.
