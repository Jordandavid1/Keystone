'use strict';

/**
 * KEYSTONE E2E Intelligence Verification Suite Runner
 * Executes Tiers 1-4 tests, summarizes results, and returns exit code.
 */

const { spawnSync } = require('node:child_process');
const path = require('node:path');

const projectRoot = path.resolve(__dirname, '../..');
const testFiles = [
  { tier: 'Tier 1: Feature Coverage (F1-F12 Isolation)', file: 'tests/e2e/tier1_features.test.js' },
  { tier: 'Tier 2: Boundary & Corner Cases (F1-F12 BVA)', file: 'tests/e2e/tier2_boundaries.test.js' },
  { tier: 'Tier 3: Cross-Feature Combinations', file: 'tests/e2e/tier3_combinations.test.js' },
  { tier: 'Tier 4: Real-World 6-Target Scenarios', file: 'tests/e2e/tier4_realworld.test.js' }
];

console.log('='.repeat(80));
console.log('  KEYSTONE E2E INTELLIGENCE TEST SUITE RUNNER');
console.log('  Mode: Opaque-Box Native Node.js Test Runner');
console.log('  Catalog: 6 Leading Benchmark Targets');
console.log('='.repeat(80));

let totalPassed = 0;
let totalFailed = 0;
const results = [];

const suiteStartTime = Date.now();

for (const { tier, file } of testFiles) {
  console.log(`\n>>> Running ${tier} [${file}]...`);
  const startTime = Date.now();
  const run = spawnSync(process.execPath, ['--test', file], {
    cwd: projectRoot,
    encoding: 'utf8'
  });

  const duration = Date.now() - startTime;
  const stdout = run.stdout || '';
  const stderr = run.stderr || '';

  // Extract pass / fail counts from node test output
  const passMatch = stdout.match(/ℹ pass (\d+)/);
  const failMatch = stdout.match(/ℹ fail (\d+)/);

  const passed = passMatch ? parseInt(passMatch[1], 10) : 0;
  const failed = failMatch ? parseInt(failMatch[1], 10) : 0;

  totalPassed += passed;
  totalFailed += failed;

  results.push({
    tier,
    file,
    passed,
    failed,
    durationMs: duration,
    exitCode: run.status
  });

  if (run.status === 0) {
    console.log(`    PASS: ${passed} tests passed (${duration}ms)`);
  } else {
    console.error(`    FAIL: ${failed} tests failed!`);
    console.error(stdout);
    if (stderr) console.error(stderr);
  }
}

const totalDuration = Date.now() - suiteStartTime;

console.log('\n' + '='.repeat(80));
console.log('  E2E TEST EXECUTION SUMMARY REPORT');
console.log('='.repeat(80));
console.log(
  '| Tier / Suite                                      | Pass | Fail | Duration  | Status |'
);
console.log(
  '|:--------------------------------------------------|:----:|:----:|:---------:|:------:|'
);
for (const r of results) {
  const status = r.failed === 0 ? '  OK  ' : ' FAIL ';
  const tierPadded = r.tier.padEnd(50, ' ');
  const passPadded = String(r.passed).padStart(4, ' ');
  const failPadded = String(r.failed).padStart(4, ' ');
  const durPadded = `${r.durationMs}ms`.padStart(9, ' ');
  console.log(`| ${tierPadded} | ${passPadded} | ${failPadded} | ${durPadded} | ${status} |`);
}
console.log('-'.repeat(80));
console.log(`Total Tests Executed: ${totalPassed + totalFailed}`);
console.log(`Total Passed:         ${totalPassed}`);
console.log(`Total Failed:         ${totalFailed}`);
console.log(`Total Duration:       ${totalDuration}ms`);
console.log('='.repeat(80));

if (totalFailed > 0) {
  console.error('\nE2E Suite Verification: FAILED');
  process.exit(1);
} else {
  console.log('\nE2E Suite Verification: 100% GREEN (ALL TIERS PASSING)');
  process.exit(0);
}
