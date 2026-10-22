# KEYSTONE

**Same AI. Expert results.**

KEYSTONE is the prompt-intelligence engine and ultimate prompting authority of the platform. It clarifies intent, decomposes goals into finishable steps, compiles expert-grade prompts, reasons through its embedded cognitive runtime, selects capabilities, governs execution, evaluates outputs, and preserves prompt provenance.

## Identity invariants

1. KEYSTONE remains the product and prompt engine.
2. `generate(goal, options) -> plan.v1` remains a supported compatibility contract.
3. PromptAnatomy remains: Role, Task, Context, Constraints, Output Format, Reasoning.
4. The original 13 domain playbooks remain first-class data.
5. Every model-facing prompt is compiled by KEYSTONE.
6. Tools contribute capability manifests and observations; they do not become prompt authorities.
7. Qwen is an embedded cognitive component, not a separate product authority.
8. Harnesses measure; workers execute only authorized envelopes; KEYSTONE decides.
9. The original repo is never overwritten by this integration.

## Structure

- `packages/prompt-engine`: preserved/evolved KEYSTONE brain
- `packages/contracts`: canonical contracts shared by API and UI
- `services/cognition`: vLLM/Qwen runtime adapter
- `services/authority`: policy, decisions, execution envelopes
- `services/harness`: quality and feedback loops
- `services/comfy`: creative workflow adapters
- `apps/api`: public and internal API
- `apps/web`: premium creative workspace
- `apps/admin`: operator workspace
- `infrastructure/kaggle`: T4 x2 BF16/offload bootstrap
- `infrastructure/migrations`: PostgreSQL/Alembic migrations
- `docs`: Bible, roadmap, preservation map and architecture decisions

## Immediate start

```bash
npm test
```

The Python API and frontend are scaffolded for the next implementation pass. The identity tests must remain green throughout the build.
