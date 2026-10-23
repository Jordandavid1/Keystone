## 2026-10-22T14:29:00Z
You are Explorer M2_2 (Aikido Prompt Injection Defense & Packaging Specialist).
Working directory: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m2_2
Authoritative Request: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md
Authoritative Plan: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_1\PROJECT.md
Existing Keystone Prompt Engine: c:\Users\Lesia Eden\Downloads\keystone-cowork\packages\prompt-engine\src\engine.js

CRITICAL INVARIANTS:
1. You are READ-ONLY. Do NOT write or modify application code.
2. Formulate implementation specifications for Aikido Prompt Injection Defense:
   - Structural delimiter containment (`<untrusted_content>`).
   - Tag escaping (`</untrusted_content>` -> `&lt;/untrusted_content&gt;`).
   - Post-generation sanitization stripping leaked delimiters.
   - Heuristic threat scoring (threat levels: SAFE, SUSPICIOUS, MALICIOUS).
3. Formulate packaging and module structure under `services/intelligence`:
   - `services/intelligence/package.json`
   - `services/intelligence/src/index.js` exporting the unified intelligence service.
4. Write your report to `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m2_2\aikido_spec.md` and send your handoff back.
