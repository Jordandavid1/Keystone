# ADR-[NUMBER]: [INVARIANT MODIFICATION TITLE]

- **Date:** [YYYY-MM-DD]
- **Target Invariant:** [Bible §2 Invariant #]
- **Status:** [PROPOSED | FOUNDER_APPROVED | REJECTED]

## 1. Explicit Founder Approval
- **Approval Timestamp:** [UTC Timestamp]
- **Verbatim Founder Directive:** "[Exact directive quoted from founder]"
- **Sign-off Identification:** [Jordan Maxwell / Founder Token]

## 2. Architecture Decision Record
- **Context:** [Why is this modification requested?]
- **Decision:** [What technical change is being made?]
- **Alternatives Considered & Rejected:** [Why were other paths insufficient?]

## 3. Compatibility Impact Analysis
- **API Impact:** [Does this affect /v1/plan, /v1/health, or OpenAPI 3.1.0?]
- **Client Impact:** [Does this break PromptAnatomy, ExecutionEnvelope, or HarnessResult?]
- **State & Storage Impact:** [Database migration or asset format changes]

## 4. KHF Regression Coverage
- **Regression Suite:** [Which test files cover this change?]
- **Test Scenarios:** [Specific assertions verifying non-regression]
- **Pre-Change vs Post-Change Verification:** [Pass counts and evidence]

## 5. Migration Plan
- **Step 1:** [Additive schema / model introduction]
- **Step 2:** [Contract version bump]
- **Step 3:** [Worker / engine rollout]

## 6. Rollback Plan
- **Trigger Conditions:** [What error rate or latency triggers rollback?]
- **Immediate Reversion Steps:** [Commands to revert commits or migration rollback]
- **State Recovery:** [Database rollback scripts]

## 7. Versioned Contract Updates
- **Old Contract Hash:** [SHA-256]
- **New Contract Hash:** [SHA-256]
- **OpenAPI Version:** [Semantic Version Bump]
