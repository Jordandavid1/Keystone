# Archived v1 Verification Suite (`e2e_v2` JS Mock Oracle)

**Archived in:** `O0.5` (ADR-004 / ADR-005 — Bible v2 Ratification)  
**Date:** 2026-11-22  
**Rollback tag:** `bible-v1-final`

## Why Archived

The 373 tests in this directory (`tier1_features.test.js` through `tier4_realworld.test.js`) executed against `harness/keystone_oracle.js`, a standalone 1,381-line JavaScript reference mock rather than live FastAPI endpoints, PostgreSQL/SQLite persistence, or real worker boundaries.

Per **KEYSTONE Bible v2 §2 Invariant 12 (Real Tests Only)**, **ADR-004**, and **ADR-005**:

> No gate passes on mocks, oracles testing themselves, or hardcoded PASS. Behavioral integration tests against real API/DB boundaries are the only green.

This suite is parked here for historical traceability until **PR10** replaces it with the real HTTP/DB acceptance suite under `tests/acceptance/`.
