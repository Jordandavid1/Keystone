# Milestone M1 (Core Shell) Adversarial Challenge Handoff Report

**Agent**: `challenger_m1_1` (Empirical Challenger, Critic, Specialist)  
**Milestone**: M1 (Wave 1: Creative Tool Fabric & Core Shell)  
**Target Scope**: F07 (Asset Storage & Short-Expiry URLs), F08 (Lineage DAG Tracking), F09 (Job State Machine Engine)  
**Date**: 2026-10-22  
**Final Verdict**: **REQUEST_CHANGES** (Storage Path Traversal Vulnerabilities Identified)

---

## 1. Observation

Direct empirical observations, tool commands, code references, and test outputs obtained during adversarial challenge execution:

### 1.1 Invariant Preservation & Baseline Verification
- Executed `python scripts/verify_invariants.py --require-docs-bible`:
  - `Overall Status: [PASS] 100% INVARIANTS SATISFIED`
  - Bible SHA-256: `1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788` [VALID]
  - Pre-built Manifest: 69/69 files byte-identical.
  - Identity tests: 3/3 passed.
  - Run 1 E2E tests: 132/132 passed.
- Executed `pytest tests/e2e_v2/test_m1_core_shell.py -v`:
  - 23/23 tests passed in 15.91s.

### 1.2 Adversarial Stress Suite Execution
Executed custom adversarial harness `.agents/teamwork/challenger_m1_1/test_m1_adversarial.py` (59 discrete test cases):
- **Overall Result**: `55/59 PASSED (4 FAILED)`
- **Area 1: Storage Key Sanitization & Path Traversal (F07)**: 7 passed, 4 failed.
- **Area 2: Signed URL Forgery & Expirations (F07)**: 12 passed, 0 failed (100% resilient).
- **Area 3: Lineage DAG Cycle Stress Tests & Diamond Topologies (F08)**: 22 passed, 0 failed (100% resilient).
- **Area 4: Job State Machine Illegal Transitions & Terminal Locks (F09)**: 14 passed, 0 failed (100% resilient, 169/169 matrix pairs strictly verified).

### 1.3 Concrete Storage Vulnerability Observations (Verbatim Code & Output)

#### Observation 1: Sibling Directory Partial Path Traversal (CWE-22) in `LocalStorageProvider._resolve_path`
- **Location**: `apps/api/src/storage/service.py:148–155`:
  ```python
  def _resolve_path(self, key: str) -> Path:
      clean_key = key.lstrip("/").replace("\\", "/")
      target = (self.base_dir / clean_key).resolve()
      # Enforce no directory traversal outside base_dir
      if not str(target).startswith(str(self.base_dir.resolve())):
          raise ValueError(f"ILLEGAL_STORAGE_PATH: Key traversal attempted: {key}")
      return target
  ```
- **Adversarial Test Command**:
  ```powershell
  python -c "from apps.api.src.storage.service import LocalStorageProvider; p = LocalStorageProvider(); resolved = p._resolve_path('../storage_evil/file.txt'); print('Resolved outside base_dir without error:', resolved)"
  ```
- **Verbatim Output**:
  ```
  Resolved outside base_dir without error: C:\Users\Lesia Eden\Downloads\keystone-cowork\data\storage_evil\file.txt
  ```
- **Mechanics**: Because `self.base_dir.resolve()` is `C:\...\data\storage`, and `target` is `C:\...\data\storage_evil\file.txt`, `str(target).startswith(str(self.base_dir.resolve()))` evaluates to `True` (prefix match on the string `"storage"`). The directory escape into a sibling directory is completely undetected.

#### Observation 2: Unsanitized `user_id` / `tenant_id` in `generate_storage_key`
- **Location**: `apps/api/src/storage/service.py:29–39`:
  ```python
  def generate_storage_key(user_id: str, asset_id: str, filename: str) -> str:
      raw_basename = os.path.basename(filename)
      # Sanitize characters: allow only alphanumeric, dot, underscore, hyphen
      safe_filename = re.sub(r"[^a-zA-Z0-9._-]", "_", raw_basename)
      if not safe_filename:
          safe_filename = "asset.bin"
      return f"tenants/{user_id}/assets/{asset_id}/{safe_filename}"
  ```
- **Adversarial Test Command**:
  ```powershell
  python -c "from apps.api.src.storage.service import LocalStorageProvider, generate_storage_key; p = LocalStorageProvider(); k = generate_storage_key('../../storage_evil', 'a1', 'f.png'); print('Key:', k); res = p._resolve_path(k); print('Resolved:', res)"
  ```
- **Verbatim Output**:
  ```
  Key: tenants/../../storage_evil/assets/a1/f.png
  Resolved: C:\Users\Lesia Eden\Downloads\keystone-cowork\data\storage_evil\assets\a1\f.png
  ```
- **Mechanics**: `user_id` is interpolated directly without character filtering or regex validation, allowing path traversal sequences like `../../` to be injected into generated storage keys.

#### Observation 3: Directory Traversal via `filename = ".."` or `"."`
- **Location**: `apps/api/src/storage/service.py:34–38`:
  ```python
  raw_basename = os.path.basename(filename)
  safe_filename = re.sub(r"[^a-zA-Z0-9._-]", "_", raw_basename)
  ```
- **Adversarial Test Command**:
  ```powershell
  python -c "from apps.api.src.storage.service import LocalStorageProvider, generate_storage_key; p = LocalStorageProvider(); print('Resolved dotdot key:', p._resolve_path(generate_storage_key('u1', 'a1', '..')))"
  ```
- **Verbatim Output**:
  ```
  Resolved dotdot key: C:\Users\Lesia Eden\Downloads\keystone-cowork\data\storage\tenants\u1\assets
  ```
- **Mechanics**: `os.path.basename("..")` returns `".."`. The regex whitelist `[^a-zA-Z0-9._-]` preserves dots. Thus, `safe_filename = ".."`. When resolved by `LocalStorageProvider`, `tenants/u1/assets/a1/..` resolves to `tenants/u1/assets`, escaping the asset's dedicated directory.

#### Observation 4: Windows Path Normalization / Directory Collision on `filename = "...."`
- **Adversarial Test Command**:
  ```powershell
  python -c "from apps.api.src.storage.service import generate_storage_key, LocalStorageProvider; k = generate_storage_key('u1', 'a1', '....'); p = LocalStorageProvider(); print('Resolved:', p._resolve_path(k))"
  ```
- **Verbatim Output**:
  ```
  Resolved: C:\Users\Lesia Eden\Downloads\keystone-cowork\data\storage\tenants\u1\assets\a1
  ```
- **Mechanics**: On Windows, trailing dots and strings of dots normalize to `.` (the directory itself). When resolved by `LocalStorageProvider`, `tenants/u1/assets/a1/....` resolves to the directory `tenants/u1/assets/a1` itself instead of a file inside it, causing subsequent `write_bytes` calls in `put_object` to crash with permission/directory exceptions.

#### Observation 5: Arbitrary Unsanitized `storage_key` Allowed in `POST /v1/assets`
- **Location**: `apps/api/src/routers/assets.py:30, 59`, `apps/api/src/repositories/assets.py:30–31`:
  ```python
  class CreateAssetRequest(BaseModel):
      filename: str
      mime_type: str
      byte_size: int
      storage_key: Optional[str] = None
  ...
  storage_key = req.storage_key or generate_storage_key(tenant_id, asset_id, req.filename)
  ```
- **Adversarial Test Command**:
  Executed `POST /v1/assets` via FastAPI `TestClient` with payload:
  `{"filename": "innocent.png", "mime_type": "image/png", "byte_size": 100, "storage_key": "../storage_evil/escaped_asset.png"}`
- **Verbatim Output**:
  ```
  Status: 200
  Response: {'status': 'ok', 'id': 'd60dc4e8-a9c3-43b7-bc07-8ff8d2130642', 'owner_id': '90e2a9da-864a-4a9c-936e-0e41cef5d1b4', 'project_id': None, 'media_type': 'image', 'mime_type': 'image/png', 'storage_provider': 'local', 'storage_key': '../storage_evil/escaped_asset.png', 'byte_size': 100, 'download_url': 'https://storage.keystone.internal/../storage_evil/escaped_asset.png?expires=1792698760&signature=cedde35fc05c8162b447a4d5af08b8dd309085f88d9cec50569c59bfad0a4100', 'created_at': '2026-10-22T19:37:40'}
  ```
- **Mechanics**: The REST endpoint accepts caller-supplied `storage_key` without validation, bypassing `generate_storage_key` and storing arbitrary traversal keys into the database and returning signed URLs for them.

---

## 2. Logic Chain

1. **Storage Path Boundary Failure (Observation 1)**: `LocalStorageProvider._resolve_path` attempts to ensure path confinement using `str(target).startswith(str(self.base_dir.resolve()))`. Because string `.startswith()` does not verify boundary separators, any relative path of the form `../<base_dir_name><suffix>/...` resolves to a path that textually starts with `str(base_dir)` while being outside the directory tree. This allows writing and reading files in arbitrary sibling folders.
2. **Namespace Pollution Failure (Observation 2)**: `generate_storage_key` assumes `user_id` and `asset_id` are pre-validated, but does not sanitize them. If a caller or upstream service passes an identifier containing `../`, it propagates into the storage key. Combined with the resolution flaw in Step 1, this enables cross-tenant and out-of-bounds filesystem operations.
3. **Dot-Directory Escapes (Observation 3 & 4)**: The regex `re.sub(r"[^a-zA-Z0-9._-]", "_", raw_basename)` treats dots as valid characters. When inputs are `..` or `....`, `os.path.basename` does not remove them, and the regex retains them. Resolving these keys either climbs up one directory level (`..`) or collapses to the directory itself (`....`), violating the invariant that storage keys must resolve to individual regular files inside the asset directory.
4. **API Gateway Exposure (Observation 5)**: In `apps/api/src/routers/assets.py`, `CreateAssetRequest` exposes `storage_key: Optional[str] = None`. By submitting a custom `storage_key`, an attacker bypasses `generate_storage_key` entirely and persists an escaped path directly into the `assets` table.
5. **Acyclicity & State Machine Verification**: Lineage DAG (F08) and Job State Machine (F09) successfully neutralized 100% of adversarial attacks (deep cycles, diamond cycles, ultra-deep chains, illegal jumps, terminal breakouts, and matrix coverage).
6. **Synthesis**: Because F07 contains 4 distinct storage path traversal vulnerabilities and an API injection vector, Milestone M1 fails security criteria and cannot be approved in its current state.

---

## 3. Caveats

- **Signed URL Engine (F07)**: The HMAC-SHA256 signature algorithm and timestamp expiration logic in `service.py` (`generate_signed_url` and `validate_signed_url`) are completely sound. They passed all 12 adversarial stress tests including bit flips, signature truncation, 3600s ceiling, negative timestamps, replay attacks, and cross-key replays. The issues in F07 are confined to path resolution, key generation, and endpoint parameter validation.
- **Lineage DAG (F08)**: Self-referential edges, direct cycles, deep cycles, ultra-deep cycles, diamond graphs, and traversals are completely sound. No vulnerabilities detected in F08.
- **Job State Machine (F09)**: All 13 states, 4 terminal states, transition matrix rules (169 pairs), retry loops, replan loops, and aliases are completely sound. No vulnerabilities detected in F09.
- **Review Constraint Respected**: As an empirical challenger, I did not modify any source code or existing tests. All findings are verified through runnable test harnesses and verbatim command output.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

Milestone M1 cannot be approved until the following remediations are applied by the worker:

### Required Remediations

1. **Fix `LocalStorageProvider._resolve_path` (`apps/api/src/storage/service.py:152`)**:
   Replace the flawed `str(target).startswith(str(self.base_dir.resolve()))` check with strict path containment:
   ```python
   try:
       target.relative_to(self.base_dir.resolve())
   except ValueError:
       raise ValueError(f"ILLEGAL_STORAGE_PATH: Key traversal attempted: {key}")
   ```
2. **Harden `generate_storage_key` (`apps/api/src/storage/service.py:29–39`)**:
   - Sanitize `user_id` and `asset_id`:
     ```python
     safe_user = re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id))
     safe_asset = re.sub(r"[^a-zA-Z0-9_-]", "_", str(asset_id))
     ```
   - Strip leading/trailing dots and enforce non-empty valid filename:
     ```python
     safe_filename = re.sub(r"[^a-zA-Z0-9._-]", "_", raw_basename)
     if safe_filename in {".", ".."} or not safe_filename or safe_filename.strip(".") == "":
         safe_filename = "asset.bin"
     ```
3. **Harden `POST /v1/assets` and `AssetRepository.create_asset` (`apps/api/src/routers/assets.py:59`, `apps/api/src/repositories/assets.py:30`)**:
   - Either disallow client-supplied `storage_key` in `CreateAssetRequest` or enforce that any provided `storage_key` strictly matches `^tenants/[a-zA-Z0-9_-]+/assets/[a-zA-Z0-9_-]+/[a-zA-Z0-9._-]+$` and cannot contain `..` or path separators outside that pattern.

---

## 5. Verification Method

To independently verify these findings and reproduce the vulnerability evidence:

1. **Run the Full Adversarial Stress Harness**:
   ```powershell
   python .agents/teamwork/challenger_m1_1/test_m1_adversarial.py
   ```
   *Expected Output*: Fails with exit code 1, displaying 4 failed tests: `ST-06`, `ST-07`, `ST-08`, and `ST-09`.

2. **Run Sibling Directory Traversal Reproduction**:
   ```powershell
   python -c "from apps.api.src.storage.service import LocalStorageProvider; p = LocalStorageProvider(); print('Resolved:', p._resolve_path('../storage_evil/file.txt'))"
   ```
   *Vulnerability Proof*: Resolves to `.../data/storage_evil/file.txt` without raising `ValueError`.

3. **Run User ID Traversal Key Generation Reproduction**:
   ```powershell
   python -c "from apps.api.src.storage.service import generate_storage_key; print('Key:', generate_storage_key('../../admin', 'ast_1', 'pic.png'))"
   ```
   *Vulnerability Proof*: Prints `tenants/../../admin/assets/ast_1/pic.png`.

4. **Run Invariant Guard Verification**:
   ```powershell
   python scripts/verify_invariants.py --require-docs-bible
   ```
   *Expected Output*: `100% INVARIANTS SATISFIED (69/69 prebuilt files byte-identical)`.
