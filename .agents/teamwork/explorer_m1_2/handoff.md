# Technical Investigation & Implementation Strategy: Milestone M1 (F07, F08, F09)

**Author:** `explorer_m1_2` (Technical Explorer)  
**Date:** 2026-10-22  
**Target Milestone:** M1 (Wave 1: Creative Tool Fabric & Core Shell)  
**Assigned Features:**
- **F07**: Asset Storage & Short-Expiry URLs (Cloud Storage / Local Provider, HMAC-SHA256 URL Signing)
- **F08**: Lineage DAG Tracking (`asset_relationships`, 8 Relationship Types, Cycle Detection, Ancestor/Descendant Traversal)
- **F09**: Job State Machine Engine (13-State Machine, State Transition Matrix, Terminal State Guards, Event History)

---

## 1. Observation

Direct observations extracted from canonical specifications, migrations, models, and test harnesses:

### 1.1 F07: Asset Storage & Short-Expiry URLs

1. **Storage Architecture (`KEYSTONE_BIBLE.md:958, 966–968`)**:
   - Bible §21: "media binaries kept in object storage".
   - Bible §22: "PostgreSQL stores asset metadata. Object storage stores binaries."
   - Bible §24, §29: Cloud Run deployment uses Google Cloud Storage for persistent asset binaries in production.

2. **Tenant-Scoped Storage Key Structure (`keystone_oracle.js:374–376`, `tier1_features.test.js:307–310`)**:
   - The authoritative key layout is verbatim:
     ```text
     tenants/{user_id}/assets/{asset_id}/{safe_filename}
     ```
   - Character sanitization rule (`keystone_oracle.js:375`):
     ```javascript
     const safeFilename = path.basename(filename).replace(/[^a-zA-Z0-9._-]/g, '_');
     ```
   - Path traversal prevention (`tier2_boundaries.test.js:253–257`):
     Input: `generateStorageKey('u1', 'a1', '../../../etc/passwd.png')`
     Output: `tenants/u1/assets/a1/passwd.png` (does not contain `..` or leading slashes).

3. **HMAC-SHA256 Signed URLs (`keystone_oracle.js:379–397`, `tier1_features.test.js:312–338`)**:
   - Expiration default: Exactly 900 seconds (15 minutes).
   - Maximum ceiling: 3600 seconds (1 hour). Exceeding 3600s raises:
     ```text
     EXPIRY_EXCEEDED: Maximum signed URL expiry is 3600s
     ```
   - Non-positive duration (`<= 0`) raises:
     ```text
     INVALID_EXPIRY
     ```
   - Signature payload: `${storageKey}:${expiresAt}`.
   - Signature algorithm: `HMAC-SHA256` hex digest.
   - Canonical URL structure:
     `https://storage.keystone.internal/{storageKey}?expires={expiresAt}&signature={token}`
   - Validation failures (`tier2_boundaries.test.js:271–287`):
     - Altered signature raises: `INVALID_SIGNATURE`
     - Expired timestamp (`current_time > expires`) raises: `URL_EXPIRED`
     - Valid URL returns: `{ valid: true, storageKey: ... }`.

---

### 1.2 F08: Lineage DAG Tracking

1. **Database Schema (`infrastructure/migrations/versions/0002_keystone_full_schema.sql:316–331`)**:
   ```sql
   CREATE TABLE IF NOT EXISTS asset_relationships (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       parent_asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
       child_asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
       job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
       relationship_type TEXT NOT NULL CHECK (relationship_type IN (
           'source', 'edit', 'variation', 'animation', 'upscale', 'reference', 'selected-final', 'intermediate'
       )),
       metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
       created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
       UNIQUE(parent_asset_id, child_asset_id, relationship_type)
   );
   ```

2. **The 8 Authoritative Relationship Types (`KEYSTONE_BIBLE.md:984`, `keystone_oracle.js:405–414`)**:
   - `source`: Root parent asset (uploaded original).
   - `edit`: Direct modification (inpainting, background removal, layer edit).
   - `variation`: Alternative composition, prompt, or seed variation.
   - `animation`: Video generated from image (e.g. Wan Image-to-Video).
   - `upscale`: Resolution/quality enhancement (e.g. 4x upscale).
   - `reference`: Conditioning media (pose, style, character reference).
   - `selected-final`: User-approved or starred deliverable asset.
   - `intermediate`: Transient workflow artifact (preview frame, mask, latent).

3. **Graph Validation & Error Invariants (`keystone_oracle.js:420–430`, `tier2_boundaries.test.js:293–313`)**:
   - Self-referential edge (`parent_id === child_id`):
     Raises: `SELF_REFERENTIAL_LINEAGE: An asset cannot be its own parent`.
   - Unsupported relationship type:
     Raises: `INVALID_RELATIONSHIP_TYPE: '<type>' is not supported`.
   - Cycle detection:
     If a directed path already exists from `child_id` to `parent_id`, adding the edge would complete a directed cycle (`parent -> child -> ... -> parent`).
     Raises: `CYCLE_DETECTED: Adding this relationship creates a directed cycle in lineage DAG`.

4. **Traversal Operations (`tier1_features.test.js:361–381`, `tier2_boundaries.test.js:315–325`)**:
   - `getAncestors(asset_id)`: Traverses directed edges backwards (`child -> parent`). Returns list of all upstream ancestor IDs. Returns `[]` if root.
   - `getDescendants(asset_id)`: Traverses directed edges forwards (`parent -> child`). Returns list of all downstream descendant IDs. Returns `[]` if leaf.

---

### 1.3 F09: Job State Machine Engine

1. **Discrete States (`KEYSTONE_BIBLE.md:779–792`, `keystone_oracle.js:494–508`)**:
   The canonical specification defines exactly 13 states:
   ```text
   CREATED
   VALIDATING
   PLANNING
   AUTHORIZING
   QUEUED
   RUNNING
   VALIDATING_OUTPUT
   RETRY_PENDING
   REPLAN_REQUIRED
   COMPLETED
   FAILED
   CANCELLED
   REJECTED
   ```

2. **Terminal States & Guards (`keystone_oracle.js:510, 538–540`, `tier2_boundaries.test.js:331–353`)**:
   - Terminal states: `COMPLETED`, `FAILED`, `CANCELLED`, `REJECTED`.
   - Transitioning out of ANY terminal state raises:
     ```text
     ILLEGAL_TRANSITION: Cannot transition out of terminal state <state>
     ```

3. **Allowed Transitions Table (`keystone_oracle.js:512–526`)**:
   - `CREATED` -> `['VALIDATING', 'CANCELLED', 'REJECTED']`
   - `VALIDATING` -> `['PLANNING', 'FAILED', 'CANCELLED', 'REJECTED']`
   - `PLANNING` -> `['AUTHORIZING', 'FAILED', 'CANCELLED']`
   - `AUTHORIZING` -> `['QUEUED', 'REJECTED', 'CANCELLED', 'PLANNING']`
   - `QUEUED` -> `['RUNNING', 'CANCELLED', 'FAILED']`
   - `RUNNING` -> `['VALIDATING_OUTPUT', 'RETRY_PENDING', 'FAILED', 'CANCELLED']`
   - `VALIDATING_OUTPUT` -> `['COMPLETED', 'RETRY_PENDING', 'REPLAN_REQUIRED', 'FAILED']`
   - `RETRY_PENDING` -> `['QUEUED', 'FAILED', 'CANCELLED']`
   - `REPLAN_REQUIRED` -> `['PLANNING', 'FAILED', 'CANCELLED']`
   - Terminal states: `[]` (no outgoing transitions allowed).

4. **Transition Semantics (`tier1_features.test.js:401–432`)**:
   - Valid transition returns `nextState`.
   - Idempotent transition (`currentState === nextState`) returns `currentState` (legal no-op).
   - Skipping or illegal transition raises:
     ```text
     ILLEGAL_TRANSITION: Transition from <state1> to <state2> is not permitted
     ```
   - Unknown state raises:
     ```text
     UNKNOWN_CURRENT_STATE: <state>
     UNKNOWN_NEXT_STATE: <state>
     ```

5. **Reconciliation of Dispatch Prompt's 13 Lifecycle Names**:
   The dispatch prompt listed:
   `CREATED, QUEUED, COMPILING_PROMPT, PROPOSED_ACTION_PENDING, AWAITING_AUTHORIZATION, ENVELOPE_ISSUED, DISPATCHED_TO_WORKER, WORKER_RUNNING, EVALUATING_OUTPUT, COMPLETED, FAILED, CANCELLED, REJECTED`.
   Cross-referencing with Bible §19 and test suites reveals this is a worker-oriented execution breakdown mapping directly to the canonical states:
   - `COMPILING_PROMPT` = `VALIDATING`
   - `PROPOSED_ACTION_PENDING` = `PLANNING`
   - `AWAITING_AUTHORIZATION` = `AUTHORIZING`
   - `ENVELOPE_ISSUED` = `QUEUED`
   - `DISPATCHED_TO_WORKER` / `WORKER_RUNNING` = `RUNNING`
   - `EVALUATING_OUTPUT` = `VALIDATING_OUTPUT`
   - `COMPLETED`, `FAILED`, `CANCELLED`, `REJECTED` = identical terminal states.
   Canonical states MUST remain the primary enum values because `node --test tests/e2e_v2/tier1_features.test.js` tests `VALIDATING`, `PLANNING`, `AUTHORIZING`, `RUNNING`, `VALIDATING_OUTPUT`. Supporting aliases ensures 100% test compatibility while honoring the dispatch lifecycle terminology.

---

## 2. Logic Chain

### 2.1 Storage Architecture & Signed URL Logic Chain

```
[Observation 1.1.1: Object storage separates binaries from PostgreSQL metadata]
                      │
                      ▼
[Step 1: Enforce multi-tenant prefix isolation: 'tenants/{user_id}/assets/{asset_id}/']
                      │
                      ▼
[Observation 1.1.2: Path traversal attack vectors in filename e.g. '../../../etc/passwd']
                      │
                      ▼
[Step 2: Apply basename + regex sanitizer '[^a-zA-Z0-9._-]' -> safe_filename]
                      │
                      ▼
[Observation 1.1.3: Signed URL bounds: default 900s, max 3600s, min > 0s]
                      │
                      ▼
[Step 3: Construct HMAC-SHA256 signature over '{storage_key}:{expires_at}']
                      │
                      ▼
[Step 4: Abstract storage provider: LocalStorageProvider for local dev, GoogleCloudStorageProvider for GCP Cloud Run]
```

- **Inference**: Creating an abstract base class `StorageProvider` with concrete implementations `LocalStorageProvider` and `GoogleCloudStorageProvider` allows the system to pass 100% of local unit and E2E tests without cloud dependencies, while providing direct drop-in readiness for Google Cloud Run deployment.

### 2.2 Lineage DAG & Cycle Detection Logic Chain

```
[Observation 1.2.1: asset_relationships stores (parent_asset_id, child_asset_id, relationship_type, job_id)]
                      │
                      ▼
[Observation 1.2.3: Invariant 1 - Self-referential edge is invalid (parent == child)]
                      │
                      ▼
[Step 1: Assert parent_id != child_id else raise SELF_REFERENTIAL_LINEAGE]
                      │
                      ▼
[Observation 1.2.2: Invariant 2 - Relationship type must be in the 8 valid types]
                      │
                      ▼
[Step 2: Assert relationship_type in VALID_RELATIONSHIPS else raise INVALID_RELATIONSHIP_TYPE]
                      │
                      ▼
[Observation 1.2.3: Invariant 3 - Graph must remain a Directed Acyclic Graph (DAG)]
                      │
                      ▼
[Step 3: Graph cycle check: run reachability test has_path(child_id, parent_id)]
                      │
       ┌──────────────┴──────────────┐
       ▼                             ▼
[Path exists: True]           [Path exists: False]
       │                             │
       ▼                             ▼
[Raise CYCLE_DETECTED]        [Insert edge into asset_relationships]
```

- **Inference**: Cycle detection is mathematically sound: an edge $(u, v)$ (where $u$ is parent, $v$ is child) creates a cycle if and only if there already exists a directed path from $v$ to $u$. By evaluating `has_path(child_id, parent_id)` prior to insertion, acyclicity is guaranteed.
- **Inference on Traversal**: Both ancestor and descendant traversals are directed reachability searches. In Python, BFS with a `visited: set` guarantees $O(V + E)$ performance. In PostgreSQL, recursive CTEs (`WITH RECURSIVE`) provide sub-millisecond database-level evaluation.

### 2.3 Job State Machine Logic Chain

```
[Observation 1.3.1: Exactly 13 discrete job states per Bible §19]
                      │
                      ▼
[Step 1: Define JobState Enum with all 13 states + bidirectional alias mapping]
                      │
                      ▼
[Observation 1.3.2: 4 terminal states cannot be mutated: COMPLETED, FAILED, CANCELLED, REJECTED]
                      │
                      ▼
[Step 2: If current_state in TERMINAL_STATES and current_state != next_state -> raise ILLEGAL_TRANSITION]
                      │
                      ▼
[Observation 1.3.4: Idempotency rule - currentState == nextState returns currentState]
                      │
                      ▼
[Step 3: If current_state == next_state -> return current_state immediately]
                      │
                      ▼
[Observation 1.3.3: ALLOWED_TRANSITIONS adjacency table defines legal forward steps]
                      │
                      ▼
[Step 4: If next_state not in ALLOWED_TRANSITIONS[current_state] -> raise ILLEGAL_TRANSITION]
                      │
                      ▼
[Step 5: Record state transition event in audit_events table with timestamp, actor, and trigger]
```

- **Inference**: Strict adherence to the state transition matrix prevents orphaned jobs, zombie processes, double execution, or runaway worker billing.

---

## 3. Caveats & Risks

1. **Pre-Built File Preservation (Invariant)**:
   - `apps/api/src/main.py`, `apps/api/src/intelligence_router.py`, `infrastructure/migrations/versions/0001_core.sql`, and all files in `tests/e2e/` must remain byte-identical.
   - All M1 implementation files must be created strictly additively under `apps/api/src/storage/`, `apps/api/src/lineage/`, `apps/api/src/jobs/`, and `apps/api/src/routers/`.

2. **State Name Duality (Bible §19 vs Dispatch Prompt)**:
   - The dispatch prompt mentioned: `CREATED, QUEUED, COMPILING_PROMPT, PROPOSED_ACTION_PENDING, AWAITING_AUTHORIZATION, ENVELOPE_ISSUED, DISPATCHED_TO_WORKER, WORKER_RUNNING, EVALUATING_OUTPUT, COMPLETED, FAILED, CANCELLED, REJECTED`.
   - The canonical Bible §19 and test suites (`tier1_features.test.js:393–432`) require: `CREATED, VALIDATING, PLANNING, AUTHORIZING, QUEUED, RUNNING, VALIDATING_OUTPUT, RETRY_PENDING, REPLAN_REQUIRED, COMPLETED, FAILED, CANCELLED, REJECTED`.
   - **Resolution**: The implementation must treat Bible §19 names as canonical enum values, and provide `STATE_ALIASES` normalizer so that worker phase strings seamlessly map to canonical states without breaking any test suite.

3. **Database Concurrency and Cycle Detection**:
   - Concurrent edge insertions could theoretically race if two edges are added simultaneously in a distributed environment.
   - **Mitigation**: Use transactional locking (`SELECT ... FOR UPDATE` on parent/child asset rows) or in-memory transaction lock when writing to `asset_relationships`.

4. **Secret Key Handling for Signed URLs**:
   - Hardcoded signing secrets must never be committed (Bible §28).
   - Use `KEYSTONE_STORAGE_SIGNING_KEY` environment variable with fallback to a deterministic local development key (`keystone_dev_storage_secret`) for tests.

---

## 4. Conclusion & Recommended Implementation Strategy

### 4.1 Component Architecture Map

```
apps/api/src/
├── storage/
│   ├── __init__.py           # Exports StorageProvider, LocalStorageProvider, GoogleCloudStorageProvider, get_storage_provider
│   ├── base.py               # Abstract StorageProvider class with HMAC-SHA256 signing/validation
│   ├── local.py              # Local filesystem implementation with sanitized key resolution
│   └── gcs.py                # Google Cloud Storage provider with bucket client and v4 signed URLs
├── lineage/
│   ├── __init__.py           # Exports LineageDagEngine, LineageRelationshipType, LineageEdge
│   ├── types.py              # Relationship types enum and dataclasses
│   └── engine.py             # Cycle detection, path reachability, ancestor/descendant traversal
├── jobs/
│   ├── __init__.py           # Exports JobState, JobStateMachine, JobStateTransition
│   ├── state_machine.py      # 13-state transition matrix, terminal state guards, idempotency
│   └── service.py            # State transition execution, PostgreSQL persistence, audit event logging
└── routers/
    ├── assets.py             # REST endpoints for upload-url, download-url, and lineage traversal
    └── jobs.py               # REST endpoints for job creation, transition, and event history
```

---

### 4.2 Concrete Implementation Specifications

#### Feature F07: Asset Storage & Short-Expiry URLs

File: `apps/api/src/storage/base.py`
```python
from abc import ABC, abstractmethod
import hmac
import hashlib
import time
import os
import re
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs

class StorageProvider(ABC):
    """Abstract base class for Keystone asset storage backends."""

    def __init__(self, signing_key: str, base_url: str):
        self.signing_key = signing_key
        self.base_url = base_url.rstrip("/")

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitizes filename, eliminating path traversal and invalid characters."""
        base = os.path.basename(filename)
        sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", base)
        return sanitized or "unnamed_asset"

    def generate_storage_key(self, user_id: str, asset_id: str, filename: str) -> str:
        """Constructs tenant-isolated storage key: tenants/{user_id}/assets/{asset_id}/{safe_filename}"""
        safe_name = self.sanitize_filename(filename)
        return f"tenants/{user_id}/assets/{asset_id}/{safe_name}"

    def generate_signed_url(self, storage_key: str, expiry_seconds: int = 900) -> str:
        """Generates HMAC-SHA256 signed URL with strict bounds checking."""
        if expiry_seconds > 3600:
            raise ValueError("EXPIRY_EXCEEDED: Maximum signed URL expiry is 3600s")
        if expiry_seconds <= 0:
            raise ValueError("INVALID_EXPIRY")

        expires_at = int(time.time()) + expiry_seconds
        sig_payload = f"{storage_key}:{expires_at}"
        signature = hmac.new(
            self.signing_key.encode("utf-8"),
            sig_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        return f"{self.base_url}/{storage_key}?expires={expires_at}&signature={signature}"

    def validate_signed_url(self, url: str) -> Dict[str, Any]:
        """Validates signed URL signature and expiration."""
        parsed = urlparse(url)
        storage_key = parsed.path.lstrip("/")
        params = parse_qs(parsed.query)

        if "expires" not in params or "signature" not in params:
            raise ValueError("MALFORMED_SIGNED_URL: Missing expires or signature query parameters")

        expires = int(params["expires"][0])
        sig = params["signature"][0]

        if time.time() > expires:
            raise ValueError("URL_EXPIRED")

        expected_sig = hmac.new(
            self.signing_key.encode("utf-8"),
            f"{storage_key}:{expires}".encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("INVALID_SIGNATURE")

        return {"valid": True, "storage_key": storage_key, "expires_at": expires}

    @abstractmethod
    async def save_bytes(self, storage_key: str, data: bytes, content_type: str = "application/octet-stream") -> Dict[str, Any]:
        pass

    @abstractmethod
    async def get_bytes(self, storage_key: str) -> bytes:
        pass

    @abstractmethod
    async def delete(self, storage_key: str) -> bool:
        pass

    @abstractmethod
    async def exists(self, storage_key: str) -> bool:
        pass
```

File: `apps/api/src/storage/local.py`
```python
import os
import aiofiles
from pathlib import Path
from typing import Dict, Any
from apps.api.src.storage.base import StorageProvider

class LocalStorageProvider(StorageProvider):
    """Local filesystem storage provider for development and testing."""

    def __init__(self, storage_root: str = "./data/storage", signing_key: str = "mock_storage_signing_key", base_url: str = "https://storage.keystone.internal"):
        super().__init__(signing_key=signing_key, base_url=base_url)
        self.storage_root = Path(storage_root).resolve()
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, storage_key: str) -> Path:
        resolved = (self.storage_root / storage_key).resolve()
        # Security invariant: prevent directory breakout
        if not str(resolved).startswith(str(self.storage_root)):
            raise ValueError("SECURITY_VIOLATION: Attempted path escape out of storage root")
        return resolved

    async def save_bytes(self, storage_key: str, data: bytes, content_type: str = "application/octet-stream") -> Dict[str, Any]:
        target = self._resolve_path(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(target, "wb") as f:
            await f.write(data)
        return {
            "storage_key": storage_key,
            "byte_size": len(data),
            "content_type": content_type,
            "local_path": str(target)
        }

    async def get_bytes(self, storage_key: str) -> bytes:
        target = self._resolve_path(storage_key)
        if not target.exists():
            raise FileNotFoundError(f"ASSET_NOT_FOUND: {storage_key}")
        async with aiofiles.open(target, "rb") as f:
            return await f.read()

    async def delete(self, storage_key: str) -> bool:
        target = self._resolve_path(storage_key)
        if target.exists():
            target.unlink()
            return True
        return False

    async def exists(self, storage_key: str) -> bool:
        return self._resolve_path(storage_key).exists()
```

---

#### Feature F08: Lineage DAG Tracking

File: `apps/api/src/lineage/types.py`
```python
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class LineageRelationshipType(str, Enum):
    SOURCE = "source"
    EDIT = "edit"
    VARIATION = "variation"
    ANIMATION = "animation"
    UPSCALE = "upscale"
    REFERENCE = "reference"
    SELECTED_FINAL = "selected-final"
    INTERMEDIATE = "intermediate"

class LineageEdge(BaseModel):
    parent_id: str
    child_id: str
    relationship_type: LineageRelationshipType
    job_id: Optional[str] = None
    created_at: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

File: `apps/api/src/lineage/engine.py`
```python
from datetime import datetime, timezone
from typing import List, Set, Dict, Optional, Any
from apps.api.src.lineage.types import LineageRelationshipType, LineageEdge

class LineageDagEngine:
    """Directed Acyclic Graph engine for asset provenance and lineage tracking."""

    VALID_RELATIONSHIPS = {t.value for t in LineageRelationshipType}

    def __init__(self, initial_edges: Optional[List[LineageEdge]] = None):
        self.edges: List[LineageEdge] = initial_edges or []

    def add_relationship(
        self,
        parent_id: str,
        child_id: str,
        relationship_type: str,
        job_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> LineageEdge:
        """Inserts an edge after validating relationship type, self-loop, and cycle absence."""
        if parent_id == child_id:
            raise ValueError("SELF_REFERENTIAL_LINEAGE: An asset cannot be its own parent")

        if relationship_type not in self.VALID_RELATIONSHIPS:
            raise ValueError(f"INVALID_RELATIONSHIP_TYPE: '{relationship_type}' is not supported")

        # Cycle check: would adding parent -> child create a path from child to parent?
        if self.has_path(start=child_id, target=parent_id):
            raise ValueError("CYCLE_DETECTED: Adding this relationship creates a directed cycle in lineage DAG")

        edge = LineageEdge(
            parent_id=parent_id,
            child_id=child_id,
            relationship_type=LineageRelationshipType(relationship_type),
            job_id=job_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {}
        )
        self.edges.append(edge)
        return edge

    def has_path(self, start: str, target: str, visited: Optional[Set[str]] = None) -> bool:
        """Recursive reachability search using visited set to prevent infinite loops."""
        if start == target:
            return True
        if visited is None:
            visited = set()
        visited.add(start)

        next_nodes = [e.child_id for e in self.edges if e.parent_id == start]
        for next_node in next_nodes:
            if next_node not in visited:
                if self.has_path(next_node, target, visited):
                    return True
        return False

    def get_ancestors(self, asset_id: str) -> List[str]:
        """BFS upwards (child -> parent) returning all upstream ancestor asset IDs."""
        ancestors: List[str] = []
        queue = [asset_id]
        visited = {asset_id}

        while queue:
            cur = queue.pop(0)
            parents = [e.parent_id for e in self.edges if e.child_id == cur]
            for p in parents:
                if p not in visited:
                    visited.add(p)
                    ancestors.append(p)
                    queue.append(p)

        return ancestors

    def get_descendants(self, asset_id: str) -> List[str]:
        """BFS downwards (parent -> child) returning all downstream descendant asset IDs."""
        descendants: List[str] = []
        queue = [asset_id]
        visited = {asset_id}

        while queue:
            cur = queue.pop(0)
            children = [e.child_id for e in self.edges if e.parent_id == cur]
            for c in children:
                if c not in visited:
                    visited.add(c)
                    descendants.append(c)
                    queue.append(c)

        return descendants

    def get_subgraph(self, asset_id: str) -> Dict[str, Any]:
        """Returns node IDs and edge definitions for canvas graph rendering."""
        ancestor_ids = set(self.get_ancestors(asset_id))
        descendant_ids = set(self.get_descendants(asset_id))
        node_ids = ancestor_ids | descendant_ids | {asset_id}

        subgraph_edges = [
            e.model_dump() for e in self.edges
            if e.parent_id in node_ids and e.child_id in node_ids
        ]
        return {
            "root_asset_id": asset_id,
            "nodes": list(node_ids),
            "edges": subgraph_edges
        }
```

---

#### Feature F09: Job State Machine Engine

File: `apps/api/src/jobs/state_machine.py`
```python
from enum import Enum
from typing import Dict, Set, List, Optional

class JobState(str, Enum):
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    PLANNING = "PLANNING"
    AUTHORIZING = "AUTHORIZING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    VALIDATING_OUTPUT = "VALIDATING_OUTPUT"
    RETRY_PENDING = "RETRY_PENDING"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

class JobStateMachine:
    """Authoritative 13-state deterministic job state machine engine per Bible §19."""

    STATES: List[str] = [s.value for s in JobState]
    TERMINAL_STATES: Set[str] = {
        JobState.COMPLETED.value,
        JobState.FAILED.value,
        JobState.CANCELLED.value,
        JobState.REJECTED.value
    }

    ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
        JobState.CREATED.value: [JobState.VALIDATING.value, JobState.CANCELLED.value, JobState.REJECTED.value],
        JobState.VALIDATING.value: [JobState.PLANNING.value, JobState.FAILED.value, JobState.CANCELLED.value, JobState.REJECTED.value],
        JobState.PLANNING.value: [JobState.AUTHORIZING.value, JobState.FAILED.value, JobState.CANCELLED.value],
        JobState.AUTHORIZING.value: [JobState.QUEUED.value, JobState.REJECTED.value, JobState.CANCELLED.value, JobState.PLANNING.value],
        JobState.QUEUED.value: [JobState.RUNNING.value, JobState.CANCELLED.value, JobState.FAILED.value],
        JobState.RUNNING.value: [JobState.VALIDATING_OUTPUT.value, JobState.RETRY_PENDING.value, JobState.FAILED.value, JobState.CANCELLED.value],
        JobState.VALIDATING_OUTPUT.value: [JobState.COMPLETED.value, JobState.RETRY_PENDING.value, JobState.REPLAN_REQUIRED.value, JobState.FAILED.value],
        JobState.RETRY_PENDING.value: [JobState.QUEUED.value, JobState.FAILED.value, JobState.CANCELLED.value],
        JobState.REPLAN_REQUIRED.value: [JobState.PLANNING.value, JobState.FAILED.value, JobState.CANCELLED.value],
        JobState.COMPLETED.value: [],
        JobState.FAILED.value: [],
        JobState.CANCELLED.value: [],
        JobState.REJECTED.value: []
    }

    STATE_ALIASES: Dict[str, str] = {
        "COMPILING_PROMPT": JobState.VALIDATING.value,
        "PROPOSED_ACTION_PENDING": JobState.PLANNING.value,
        "AWAITING_AUTHORIZATION": JobState.AUTHORIZING.value,
        "ENVELOPE_ISSUED": JobState.QUEUED.value,
        "DISPATCHED_TO_WORKER": JobState.RUNNING.value,
        "WORKER_RUNNING": JobState.RUNNING.value,
        "EVALUATING_OUTPUT": JobState.VALIDATING_OUTPUT.value
    }

    @classmethod
    def normalize_state(cls, state: str) -> str:
        """Normalizes state aliases to canonical Bible §19 enum strings."""
        if not state or not isinstance(state, str):
            raise ValueError(f"UNKNOWN_CURRENT_STATE: {state}")
        upper = state.strip().upper()
        return cls.STATE_ALIASES.get(upper, upper)

    @classmethod
    def transition(cls, current_state: str, next_state: str) -> str:
        """Executes validated deterministic state transition."""
        norm_current = cls.normalize_state(current_state)
        norm_next = cls.normalize_state(next_state)

        if norm_current not in cls.STATES:
            raise ValueError(f"UNKNOWN_CURRENT_STATE: {current_state}")
        if norm_next not in cls.STATES:
            raise ValueError(f"UNKNOWN_NEXT_STATE: {next_state}")

        # Idempotency rule: no-op if target equals current
        if norm_current == norm_next:
            return norm_current

        # Terminal state protection rule
        if norm_current in cls.TERMINAL_STATES:
            raise ValueError(f"ILLEGAL_TRANSITION: Cannot transition out of terminal state {norm_current}")

        # Permitted transition check
        allowed = cls.ALLOWED_TRANSITIONS.get(norm_current, [])
        if norm_next not in allowed:
            raise ValueError(f"ILLEGAL_TRANSITION: Transition from {norm_current} to {norm_next} is not permitted")

        return norm_next
```

---

## 5. Verification Method

To verify the investigation and ensure the recommended implementation passes all tests:

1. **Verify Baseline Non-Regression (Mandatory)**:
   ```powershell
   npm test
   # Expected: 3/3 passed (100% green)
   ```

2. **Verify Full E2E V2 Test Suite (373 tests across Tiers 1–4)**:
   ```powershell
   node tests/e2e_v2/runner.js
   # Expected: 373/373 passed across Tier 1, Tier 2, Tier 3, and Tier 4
   ```

3. **Verify Specific Feature Isolation Tests**:
   ```powershell
   node --test --test-name-pattern="F07" tests/e2e_v2/tier1_features.test.js
   node --test --test-name-pattern="F08" tests/e2e_v2/tier1_features.test.js
   node --test --test-name-pattern="F09" tests/e2e_v2/tier1_features.test.js
   ```

4. **Verify Boundary Value Analysis Tests**:
   ```powershell
   node --test --test-name-pattern="F07" tests/e2e_v2/tier2_boundaries.test.js
   node --test --test-name-pattern="F08" tests/e2e_v2/tier2_boundaries.test.js
   node --test --test-name-pattern="F09" tests/e2e_v2/tier2_boundaries.test.js
   ```

5. **Verify Python M0 Verification Suites**:
   ```powershell
   pytest
   # Expected: 58/58 passed in tests/e2e_v2/
   ```

6. **Invalidation Conditions**:
   - Any modification to `KEYSTONE_BIBLE.md` (SHA-256 altered).
   - Any mutation or overwrite of pre-built baseline files (`main.py`, `intelligence_router.py`, `0001_core.sql`, `tests/e2e/`).
   - Permitting transition out of terminal job states.
   - Permitting circular relationships in `asset_relationships`.
   - Permitting signed URL expiry > 3600s or non-positive durations.
