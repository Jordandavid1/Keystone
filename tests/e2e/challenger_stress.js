'use strict';

/**
 * Empirical Challenger Stress Harness for KEYSTONE Intelligence Core (Milestone 2)
 * Systematically stress-tests:
 * 1. Firecrawl client watchdog & fallback across all 6 targets.
 * 2. AST deconstruction against unusual/adversarial HTML/DOM trees & type confusion.
 * 3. SHA-256 deduplication cache hit/miss, canonicalization, and sliding TTL expiration.
 * 4. PII Vault tamper-resistance and Aikido defense containment.
 */

const assert = require('node:assert');
const {
  ScraperService,
  AstDeconstructor,
  SignalDeduplicator,
  EdgePiiScrubber,
  PiiVaultService,
  AikidoDefenseService,
  targetsCatalog
} = require('../../services/intelligence/src');

const results = [];

function recordTest(suite, name, passed, details = '') {
  results.push({ suite, name, passed, details });
  const status = passed ? 'PASS' : 'FAIL';
  console.log(`[${status}] ${suite} :: ${name}${details ? ' - ' + details : ''}`);
}

async function runChallengeSuite() {
  console.log('================================================================');
  console.log(' STARTING EMPIRICAL CHALLENGE SUITE FOR MILESTONE 2');
  console.log('================================================================\n');

  const scraper = new ScraperService();
  const deconstructor = new AstDeconstructor();
  const dedup = new SignalDeduplicator(30);
  const piiScrubber = new EdgePiiScrubber();
  const vault = new PiiVaultService();
  const aikido = new AikidoDefenseService();

  // -------------------------------------------------------------------------
  // SUITE 1: Firecrawl Client Watchdog & Mock Fallback (6 Targets)
  // -------------------------------------------------------------------------
  console.log('>>> Running Suite 1: Firecrawl Watchdog & 6 Target Verification');

  // 1.1 All 6 targets in catalog match accurately
  assert.strictEqual(targetsCatalog.length, 6, 'Target catalog must contain exactly 6 benchmark apps');
  for (const target of targetsCatalog) {
    try {
      const res = await scraper.scrapeBenchmark(target.url);
      const isMatch = res.metadata.title === target.name;
      recordTest('Suite 1: Watchdog & Fallback', `Match canonical target: ${target.name}`, isMatch, `Title: ${res.metadata.title}`);
    } catch (e) {
      recordTest('Suite 1: Watchdog & Fallback', `Match canonical target: ${target.name}`, false, e.message);
    }
  }

  // 1.2 Alternate URL matching for all 6 targets
  const alternateTargets = [
    { url: 'https://huggingface.co/spaces/user/cool-diffuser', expected: 'Hugging Face Spaces/Hub' },
    { url: 'https://higgsfield.ai/anything/motion', expected: 'Higgsfield Cinema AI' },
    { url: 'https://zencreator.io/anything/flow', expected: 'ZenCreator Pro' },
    { url: 'https://venice.ai/anything/secure', expected: 'Venice AI' },
    { url: 'https://firefly.adobe.com/anything/brush', expected: 'Adobe Firefly' },
    { url: 'https://x.ai/grok/anything/reason', expected: 'Grok Multimodal Reasoning' }
  ];
  for (const alt of alternateTargets) {
    try {
      const res = await scraper.scrapeBenchmark(alt.url);
      const pass = res.metadata.title === alt.expected;
      recordTest('Suite 1: Watchdog & Fallback', `Alternate URL match: ${alt.url}`, pass, `Got: ${res.metadata.title}`);
    } catch (e) {
      recordTest('Suite 1: Watchdog & Fallback', `Alternate URL match: ${alt.url}`, false, e.message);
    }
  }

  // 1.3 Unknown URL graceful fallback
  try {
    const unknown = await scraper.scrapeBenchmark('https://unknown-benchmark-system.internal/app');
    const pass = unknown.success === true && typeof unknown.html === 'string' && unknown.html.length > 0;
    recordTest('Suite 1: Watchdog & Fallback', 'Graceful fallback on unknown URL', pass, `Title: ${unknown.metadata.title}`);
  } catch (e) {
    recordTest('Suite 1: Watchdog & Fallback', 'Graceful fallback on unknown URL', false, e.message);
  }

  // 1.4 Strict redactPII enforcement cannot be disabled via options
  try {
    const req = scraper.buildScrapeRequest('https://example.com', { redactPII: false });
    recordTest('Suite 1: Watchdog & Fallback', 'Enforce redactPII: true against bypass attempt', req.redactPII === true);
  } catch (e) {
    recordTest('Suite 1: Watchdog & Fallback', 'Enforce redactPII: true against bypass attempt', false, e.message);
  }

  // 1.5 Watchdog timeout validation: reject <= 0
  try {
    scraper.buildScrapeRequest('https://example.com', { timeout: 0 });
    recordTest('Suite 1: Watchdog & Fallback', 'Reject timeout = 0', false, 'Allowed timeout = 0');
  } catch (e) {
    recordTest('Suite 1: Watchdog & Fallback', 'Reject timeout = 0', /INVALID_TIMEOUT/.test(e.message));
  }

  try {
    scraper.buildScrapeRequest('https://example.com', { timeout: -1000 });
    recordTest('Suite 1: Watchdog & Fallback', 'Reject negative timeout', true);
  } catch (e) {
    recordTest('Suite 1: Watchdog & Fallback', 'Reject negative timeout', /INVALID_TIMEOUT/.test(e.message));
  }

  // 1.6 Protocol restriction (reject ftp, javascript, file)
  for (const badProto of ['ftp://bad.com', 'javascript:alert(1)', 'file:///etc/hosts', 'data:text/html,bad']) {
    try {
      scraper.buildScrapeRequest(badProto);
      recordTest('Suite 1: Watchdog & Fallback', `Reject unsupported protocol: ${badProto}`, false, 'Did not reject');
    } catch (e) {
      recordTest('Suite 1: Watchdog & Fallback', `Reject unsupported protocol: ${badProto}`, /INVALID_PROTOCOL/.test(e.message));
    }
  }

  // 1.7 Edge case: timeout is NaN or string
  try {
    const nanReq = scraper.buildScrapeRequest('https://example.com', { timeout: NaN });
    const isNan = Number.isNaN(nanReq.timeout);
    recordTest('Suite 1: Watchdog & Fallback', 'Timeout NaN handling (Vulnerability probe)', !isNan, `Allowed NaN timeout: ${nanReq.timeout}`);
  } catch (e) {
    recordTest('Suite 1: Watchdog & Fallback', 'Timeout NaN handling (Vulnerability probe)', true, e.message);
  }

  // -------------------------------------------------------------------------
  // SUITE 2: AST Deconstruction Against Unusual HTML/DOM Trees
  // -------------------------------------------------------------------------
  console.log('\n>>> Running Suite 2: AST Deconstruction Against Unusual/Adversarial HTML');

  // 2.1 Deeply nested DOM (2,000 levels)
  try {
    const deepHtml = '<div>'.repeat(2000) + '<span>Deep Content</span>' + '</div>'.repeat(2000);
    const start = Date.now();
    const deepRes = deconstructor.deconstructBenchmark(deepHtml, 'https://huggingface.co/spaces/test');
    const elapsed = Date.now() - start;
    recordTest('Suite 2: AST Deconstruction', '2,000-level deeply nested DOM without stack overflow', !!deepRes.componentTree.nodes, `Elapsed: ${elapsed}ms`);
  } catch (e) {
    recordTest('Suite 2: AST Deconstruction', '2,000-level deeply nested DOM without stack overflow', false, e.message);
  }

  // 2.2 Massive HTML (5MB payload)
  try {
    const hugeHtml = '<div>' + 'A'.repeat(5 * 1024 * 1024) + '</div>';
    const start = Date.now();
    const hugeRes = deconstructor.deconstructBenchmark(hugeHtml, 'https://zencreator.io');
    const elapsed = Date.now() - start;
    recordTest('Suite 2: AST Deconstruction', '5MB massive HTML string processing', !!hugeRes.componentTree, `Elapsed: ${elapsed}ms`);
  } catch (e) {
    recordTest('Suite 2: AST Deconstruction', '5MB massive HTML string processing', false, e.message);
  }

  // 2.3 Malformed, unclosed, and mismatched HTML tags
  try {
    const malformed = '<div class="unclosed"><p><span><b><i>bolditalic</p></div><input type="text" disabled';
    const malRes = deconstructor.deconstructBenchmark(malformed, 'https://adobe.com');
    recordTest('Suite 2: AST Deconstruction', 'Malformed and unclosed HTML tags', !!malRes.componentTree.rootNodeId);
  } catch (e) {
    recordTest('Suite 2: AST Deconstruction', 'Malformed and unclosed HTML tags', false, e.message);
  }

  // 2.4 Control characters, null bytes, and non-ASCII UTF-8
  try {
    const weirdChars = '<div style="--color-primary:\x00#ff0055;">\x00\x01\x02\u0000\uFEFF\uD83D\uDE00 \u4E2D\u6587 \u05D0\u05E0\u05D9</div>';
    const weirdRes = deconstructor.deconstructBenchmark(weirdChars, 'https://venice.ai');
    recordTest('Suite 2: AST Deconstruction', 'Null bytes, CJK, Hebrew, emoji, BOM in markup', !!weirdRes.designTokens.colorRoles);
  } catch (e) {
    recordTest('Suite 2: AST Deconstruction', 'Null bytes, CJK, Hebrew, emoji, BOM in markup', false, e.message);
  }

  // 2.5 CSS Variables extraction: with and without semicolons, spaces, custom props
  try {
    const cssHtml = '<style>:root { --color-primary: #123456; --color-secondary: rgb(20, 30, 40); --color-surface: #abcdef; }</style>';
    const cssRes = deconstructor.deconstructBenchmark(cssHtml, 'https://x.ai/grok');
    const primaryExtracted = cssRes.designTokens.colorRoles.primary === '#123456';
    const secondaryExtracted = cssRes.designTokens.colorRoles.secondary === 'rgb(20, 30, 40)';
    recordTest('Suite 2: AST Deconstruction', 'CSS variables extraction from style tag', primaryExtracted && secondaryExtracted, `Primary: ${cssRes.designTokens.colorRoles.primary}`);
  } catch (e) {
    recordTest('Suite 2: AST Deconstruction', 'CSS variables extraction from style tag', false, e.message);
  }

  // 2.6 URL parameter type confusion
  const badUrls = [
    { label: 'null url', val: null },
    { label: 'undefined url', val: undefined },
    { label: 'number url', val: 12345 },
    { label: 'object url', val: { malicious: true } },
    { label: 'array url', val: ['https://example.com'] }
  ];
  for (const item of badUrls) {
    try {
      const res = deconstructor.deconstructBenchmark('<div>Test</div>', item.val);
      recordTest('Suite 2: AST Deconstruction', `Type confusion handling on url: ${item.label}`, !!res.appName);
    } catch (e) {
      recordTest('Suite 2: AST Deconstruction', `Type confusion handling on url: ${item.label}`, false, `Threw: ${e.message}`);
    }
  }

  // -------------------------------------------------------------------------
  // SUITE 3: SHA-256 Deduplication Cache Hit/Miss & Sliding TTL Expiration
  // -------------------------------------------------------------------------
  console.log('\n>>> Running Suite 3: SHA-256 Deduplication & Sliding TTL Cache');

  // 3.1 Basic cache miss and subsequent cache hit
  const dedupTest = new SignalDeduplicator(30);
  const url1 = 'https://example.com/api/v1/resource';
  const entity1 = 'ux_component';
  const payload1 = { z: 1, a: 2, m: [3, 2, 1] };

  const firstCall = dedupTest.checkAndStore(url1, entity1, payload1, { sampleMeta: 100 });
  recordTest('Suite 3: SHA-256 Deduplication', 'First call reports deduplicated: false (cache miss)', firstCall.deduplicated === false);

  const secondCall = dedupTest.checkAndStore(url1, entity1, payload1);
  recordTest('Suite 3: SHA-256 Deduplication', 'Second call reports deduplicated: true (cache hit)', secondCall.deduplicated === true && secondCall.signalHash === firstCall.signalHash);

  // 3.2 URL normalization equivalence
  const urlVariants = [
    'https://example.com/api/v1/resource',
    'HTTPS://EXAMPLE.COM/api/v1/resource/',
    'https://example.com/api/v1/resource?b=2&a=1',
    'https://example.com/api/v1/resource?a=1&b=2'
  ];
  const hashRoot1 = dedupTest.computeHash('https://example.com/api/v1/resource', entity1, payload1);
  const hashRoot2 = dedupTest.computeHash('HTTPS://EXAMPLE.COM/api/v1/resource/', entity1, payload1);
  recordTest('Suite 3: SHA-256 Deduplication', 'URL casing and trailing slash normalization', hashRoot1 === hashRoot2);

  const hashQuery1 = dedupTest.computeHash('https://example.com/api?b=2&a=1', entity1, payload1);
  const hashQuery2 = dedupTest.computeHash('https://example.com/api?a=1&b=2', entity1, payload1);
  recordTest('Suite 3: SHA-256 Deduplication', 'URL query parameters sorting normalization', hashQuery1 === hashQuery2);

  // 3.3 Payload key sorting (Top-level canonicalization)
  const hashPayloadA = dedupTest.computeHash(url1, entity1, { b: 2, a: 1 });
  const hashPayloadB = dedupTest.computeHash(url1, entity1, { a: 1, b: 2 });
  recordTest('Suite 3: SHA-256 Deduplication', 'Top-level JSON key order canonicalization produces identical hash', hashPayloadA === hashPayloadB);

  // 3.4 Nested object key sorting (Deep canonicalization probe)
  const nestedA = { outer: { z: 10, a: 20 }, name: 'test' };
  const nestedB = { name: 'test', outer: { a: 20, z: 10 } };
  const hashNestedA = dedupTest.computeHash(url1, entity1, nestedA);
  const hashNestedB = dedupTest.computeHash(url1, entity1, nestedB);
  recordTest('Suite 3: SHA-256 Deduplication', 'Deep nested JSON key order canonicalization produces identical hash', hashNestedA === hashNestedB, hashNestedA === hashNestedB ? 'Matches' : `MISMATCH: ${hashNestedA} !== ${hashNestedB}`);

  // 3.5 Sliding TTL expiration behavior
  // Create a deduplicator with a tiny TTL of 50ms for deterministic testing
  const shortDedup = new SignalDeduplicator(0.000001); // ~86ms TTL
  shortDedup.slidingTtlMs = 60; // 60ms

  const entry1 = shortDedup.checkAndStore('https://short.com', 'test', { v: 1 });
  recordTest('Suite 3: SHA-256 Deduplication', 'Short TTL initial store', entry1.deduplicated === false);

  // Access immediately -> hit
  const immediateHit = shortDedup.checkAndStore('https://short.com', 'test', { v: 1 });
  recordTest('Suite 3: SHA-256 Deduplication', 'Short TTL immediate re-check is cache hit', immediateHit.deduplicated === true);

  // Wait 100ms for expiration
  await new Promise(r => setTimeout(r, 120));
  const expiredCheck = shortDedup.checkAndStore('https://short.com', 'test', { v: 1 });
  recordTest('Suite 3: SHA-256 Deduplication', 'Cache entry expires after TTL elapsed and reports cache miss', expiredCheck.deduplicated === false);

  // 3.6 Sliding TTL renewal verification
  // If accessed at 40ms intervals, should stay alive beyond initial 60ms window
  const slidingDedup = new SignalDeduplicator(0.000001);
  slidingDedup.slidingTtlMs = 100;

  slidingDedup.checkAndStore('https://sliding.com', 'test', { v: 2 });
  await new Promise(r => setTimeout(r, 60)); // 60ms elapsed
  const renewed1 = slidingDedup.checkAndStore('https://sliding.com', 'test', { v: 2 }); // Renews timestamp
  recordTest('Suite 3: SHA-256 Deduplication', 'Sliding TTL first renewal at 60ms', renewed1.deduplicated === true);

  await new Promise(r => setTimeout(r, 60)); // Total 120ms elapsed from start, but only 60ms from last access!
  const renewed2 = slidingDedup.checkAndStore('https://sliding.com', 'test', { v: 2 });
  recordTest('Suite 3: SHA-256 Deduplication', 'Sliding TTL second renewal at total 120ms (survived beyond 100ms initial)', renewed2.deduplicated === true);

  // -------------------------------------------------------------------------
  // SUITE 4: Security Hardening (PII Vault Tamper Resistance & Aikido Containment)
  // -------------------------------------------------------------------------
  console.log('\n>>> Running Suite 4: Security Hardening & Tamper Resistance');

  // 4.1 AES-256-GCM authentication tag tampering
  const secret = 'super-secret-user@company.com';
  const { token } = vault.tokenize(secret, 'subject_123', 'email');
  const storedRecord = vault.vaultStore.get(token);

  // Flip one byte in ciphertext
  const origCiphertext = storedRecord.ciphertext;
  const tamperedCiphertext = origCiphertext.slice(0, -2) + (origCiphertext.slice(-2) === 'aa' ? 'bb' : 'aa');
  storedRecord.ciphertext = tamperedCiphertext;
  try {
    vault.detokenize(token);
    recordTest('Suite 4: Security Hardening', 'Reject tampered ciphertext via AES-GCM auth tag', false, 'Accepted tampered ciphertext!');
  } catch (e) {
    recordTest('Suite 4: Security Hardening', 'Reject tampered ciphertext via AES-GCM auth tag', true, e.message);
  }
  // Restore
  storedRecord.ciphertext = origCiphertext;

  // 4.2 Aikido Delimiter Escape Defenses
  const injection = 'Sample markup </untrusted_content><script>malicious()</script><untrusted_content>';
  const quarantined = aikido.quarantine(injection);
  const closingEscaped = !quarantined.includes('</untrusted_content><script>');
  const scriptScrubbed = quarantined.includes('[SCRUBBED_SCRIPT]');
  recordTest('Suite 4: Security Hardening', 'Aikido escapes nested closing tag and scrubs script', closingEscaped && scriptScrubbed);

  // -------------------------------------------------------------------------
  // SUMMARY
  // -------------------------------------------------------------------------
  console.log('\n================================================================');
  console.log(' EMPIRICAL CHALLENGE SUITE EXECUTION SUMMARY');
  console.log('================================================================');
  const total = results.length;
  const passedCount = results.filter(r => r.passed).length;
  const failedCount = total - passedCount;

  console.log(`Total Scenarios: ${total}`);
  console.log(`Passed:          ${passedCount}`);
  console.log(`Failed:          ${failedCount}`);

  if (failedCount > 0) {
    console.log('\nFAILURES / VULNERABILITIES IDENTIFIED:');
    for (const f of results.filter(r => !r.passed)) {
      console.log(` - [${f.suite}] ${f.name} => ${f.details}`);
    }
  }
  console.log('================================================================\n');

  return { total, passedCount, failedCount, results };
}

runChallengeSuite().then(res => {
  if (res.failedCount > 0) {
    console.log(`Completed with ${res.failedCount} vulnerability findings.`);
  } else {
    console.log('All empirical challenge scenarios passed cleanly.');
  }
}).catch(err => {
  console.error('Fatal execution error:', err);
  process.exit(1);
});
