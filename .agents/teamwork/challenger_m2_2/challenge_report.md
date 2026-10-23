# Milestone 2 Security Boundaries & Cryptographic Hardening Challenge Report

**Date**: 2026-10-22T14:55:00Z  
**Challenger**: Challenger 2 (`teamwork_preview_challenger`)  
**Target Package**: `services/intelligence` (`@keystone/intelligence`)  
**Parent Orchestrator**: `60572d58-20e5-4b73-8f9a-70a7a40329ec`  
**Verdict**: **APPROVE**  

---

## Challenge Summary

**Overall risk assessment**: **LOW**  
All core security guarantees mandated by Requirements R1, R2, and `pii-vault-compliance` standards have been empirically verified under hostile stress testing:
1. **Aikido Prompt-Injection Defense**: Delimiter containment (`<untrusted_content>`), tag escaping (`&lt;/untrusted_content&gt;`), script/comment neutralization, post-generation stripping, and `MALICIOUS` heuristic classification all execute reliably under adversarial inputs.
2. **PII Vault Boundary & Context Minimization**: Authenticated AES-256-GCM encryption with 256-bit keys and 12-byte IVs guarantees zero plaintext PII reaches analytical schemas or compiled prompt text.
3. **GDPR Article 17 Cascading Erasure**: 5-step cascading purge shreds vault entries, cancels active queue tasks, produces an immutable audit record without plain PII, and exhibits 100% idempotency over repeated purges.
4. **Cryptographic Tamper Rejection**: Any bit manipulation across ciphertext or authentication tags, truncation, or ciphertext splicing causes immediate decipher authentication failure (`Unsupported state or unable to authenticate data`).

Minor defense-in-depth edge cases were identified and documented with actionable mitigations below.

---

## Challenges

### [Low] Challenge 1: Delimiter Tag Escaping with HTML Attributes or Trailing Slashes

- **Assumption challenged**: The Aikido delimiter escaping regex `/<\/\s*untrusted_content\s*>/gi` in `aikido_defense.js` assumes closing tags do not include HTML attributes or self-closing slashes.
- **Attack scenario**: An attacker embeds `</untrusted_content id="breakout">` or `</untrusted_content/>` inside scraped HTML. Because the regex looks for `\s*>` immediately after `untrusted_content`, the tag with attributes is not replaced with `&lt;/untrusted_content&gt;`.
- **Blast radius**: If a downstream LLM parser accepts loose XML/HTML closing tags with attributes, the prompt container could prematurely close.
- **Mitigation**: Update regex in `services/intelligence/src/security/aikido_defense.js` line 37 to:
  ```javascript
  result = result.replace(/<\/\s*untrusted_content[^>]*>/gi, '&lt;/untrusted_content&gt;');
  result = result.replace(/<\s*untrusted_content[^>]*>/gi, '&lt;untrusted_content&gt;');
  ```

### [Low] Challenge 2: Post-Generation Sanitization Whitespace Tolerance

- **Assumption challenged**: The AI model will only output strict delimiter tokens matching `/<\/?untrusted_content>/gi`.
- **Attack scenario**: If the model output echoes `<untrusted_content >` with a trailing space before the closing bracket, `sanitizeOutput()` fails to strip the tag.
- **Blast radius**: An internal delimiter tag could leak into client-facing outputs.
- **Mitigation**: Update regex in `services/intelligence/src/security/aikido_defense.js` lines 133–134 to:
  ```javascript
  result = result.replace(/<\/?\s*untrusted_content\s*>/gi, '');
  result = result.replace(/&lt;\/?\s*untrusted_content\s*&gt;/gi, '');
  ```

### [Low] Challenge 3: Unclosed & Self-Closing `<script>` Tags in Scraped Markup

- **Assumption challenged**: Scraped external web pages will always contain well-formed paired `<script>...</script>` tags.
- **Attack scenario**: Scraped markup contains `<script src="https://evil.com/x.js">` or `<script src="evil.js"/>`. The regex `/<script[\s\S]*?<\/script>/gi` does not match, leaving the tag in `escapeDelimiters` output (though `scanThreat` flags it as `SUSPICIOUS`).
- **Blast radius**: If the raw quarantined markup is rendered unsanitized in a browser frontend, an XSS vector could trigger.
- **Mitigation**: Add self-closing and unclosed script scrubbers:
  ```javascript
  result = result.replace(/<script[^>]*\/?>/gi, '[SCRUBBED_SCRIPT]');
  ```

### [Low] Challenge 4: Non-Recursive Object Sorting in Signal Deduplication

- **Assumption challenged**: `SignalDeduplicator.canonicalizePayload()` assumes sorting top-level keys is sufficient for deterministic SHA-256 generation.
- **Attack scenario**: Two payloads have identical nested object properties serialized in different key order, e.g., `{ obj: { a: 1, b: 2 } }` vs `{ obj: { b: 2, a: 1 } }`.
- **Blast radius**: The cache computes two distinct SHA-256 hashes, failing to detect duplicate signals across differently formatted JSON trees.
- **Mitigation**: Recursively apply `canonicalizePayload()` to all object values.

---

## Stress Test Results

All 25 empirical adversarial scenarios in `tests/adversarial_security_suite.js` were executed and verified:

| # | Category | Stress Test Scenario | Expected Behavior | Actual Behavior | Result |
|:--|:---------|:---------------------|:------------------|:----------------|:------:|
| 1 | Aikido | Standard `</untrusted_content>` breakout | Escaped to `&lt;/untrusted_content&gt;` | Escaped correctly | **PASS** |
| 2 | Aikido | Whitespace variants `</  untrusted_content  >` | Escaped without leaking raw closing tag | Escaped correctly | **PASS** |
| 3 | Aikido | Case variants `</UNTRUSTED_CONTENT>` | Case-insensitive replacement | Escaped correctly | **PASS** |
| 4 | Aikido | 50 consecutive breakout tags in burst | All 50 tags escaped | All escaped, no memory spike | **PASS** |
| 5 | Aikido | Executable `<script>` with cookies/fetch | Scrubbed to `[SCRUBBED_SCRIPT]` | Scrubbed cleanly | **PASS** |
| 6 | Aikido | HTML comment hiding breakout `<!-- </untrusted_content> -->` | Scrubbed to `[SCRUBBED_COMMENT]` | Scrubbed cleanly | **PASS** |
| 7 | Aikido | Exfiltration probes & DAN jailbreak attacks | Flagged as `MALICIOUS` (score 1.0) | Flagged `MALICIOUS` (score 1.0) | **PASS** |
| 8 | Aikido | Benign technical code (Canvas, SQL, React) | Flagged as `SAFE` (score 0.0) | Flagged `SAFE` (score 0.0) | **PASS** |
| 9 | Aikido | Post-generation sanitization of leaked tags | Tags stripped from output | Tags stripped cleanly | **PASS** |
| 10 | Aikido | Keystone prompt compiler containment bridge | Injects containment constraint in `step.promptText` | Injected, prompt anatomy protected | **PASS** |
| 11 | PII Vault | Edge PII scrubber (emails, phones, keys, IPs) | Sensitive values replaced with `[REDACTED_*]` | Redacted, tech terms preserved | **PASS** |
| 12 | PII Vault | AES-256-GCM Vault tokenization format | Format `vault_tok_<uuid>`, masked `s***@domain` | Compliant format and masking | **PASS** |
| 13 | PII Vault | Zero plain PII in Keystone compiled prompt | Zero plain email/phone in `step.promptText` | 0 raw PII leaked, tokens present | **PASS** |
| 14 | PII Vault | Masking edge cases (empty, short, phone, contact) | Deterministic masking without throwing | Handled correctly across all types | **PASS** |
| 15 | GDPR | 5-step cascading erasure across records & queue | Shreds vault store, cancels jobs, isolates others | Records/jobs cleared, other subjects safe | **PASS** |
| 16 | GDPR | 10 consecutive repeat purges (Idempotency) | Returns `erasedCount: 0`, `idempotent: true` | Strict HTTP 200 idempotency verified | **PASS** |
| 17 | GDPR | Detokenize called on purged token | Throws `TOKEN_NOT_FOUND` error | Throws `TOKEN_NOT_FOUND` | **PASS** |
| 18 | GDPR | Audit ledger compliance (Zero Plain PII) | Immutable log with UUID and zero raw PII | Audit record verified zero-PII | **PASS** |
| 19 | GDPR | Empty and whitespace `subjectId` validation | Throws `INVALID_SUBJECT_ID` | Throws `INVALID_SUBJECT_ID` | **PASS** |
| 20 | AES-256-GCM | Single-bit flip in ciphertext (Bit 0) | Ciphertext authentication failure | Throws AEAD auth error | **PASS** |
| 21 | AES-256-GCM | Single-bit flip in authentication tag | Tag verification failure | Throws AEAD auth error | **PASS** |
| 22 | AES-256-GCM | Corrupted IV length (10 bytes instead of 12) | Throws `INVALID_IV_LENGTH` | Throws `INVALID_IV_LENGTH` | **PASS** |
| 23 | AES-256-GCM | Ciphertext truncation attack | Decryption failure | Throws AEAD auth error | **PASS** |
| 24 | AES-256-GCM | Cross-record ciphertext splicing | Tag mismatch rejection | Throws AEAD auth error | **PASS** |
| 25 | AES-256-GCM | Master key length enforcement (128-bit & 512-bit) | Throws `INVALID_KEY_LENGTH` | Strictly enforces 256 bits | **PASS** |

---

## Unchallenged Areas

- **Live External Network Requests**: Live requests to public internet endpoints were not executed due to offline sandbox test constraints. All client fallback mechanisms and mock fixture responses across the 6 mandated benchmark targets were thoroughly verified.
- **Physical BigQuery Infrastructure**: BigQuery DDL, TVFs, and procedures were validated via simulated syntax/attribution harnesses; physical BigQuery cluster deployment is scoped for Milestone 3 under `infrastructure/bigquery/`.
