'use strict';

/**
 * KEYSTONE Opaque-Box E2E Test Suite Runner (v2 - F01–F35)
 * Executes Tiers 1-4 using the native Node.js test runner and produces
 * a structured markdown execution report.
 */

const { spawn } = require('node:child_process');
const path = require('node:path');

const TIERS = [
  {
    tier: 'Tier 1: Feature Coverage (F01–F35 Isolation)',
    file: 'tests/e2e_v2/tier1_features.test.js'
  },
  {
    tier: 'Tier 2: Boundary & Corner Cases (F01–F35 BVA)',
    file: 'tests/e2e_v2/tier2_boundaries.test.js'
  },
  {
    tier: 'Tier 3: Cross-Feature Combinations & State Transitions',
    file: 'tests/e2e_v2/tier3_combinations.test.js'
  },
  {
    tier: 'Tier 4: Real-World Creative Workflow Scenarios',
    file: 'tests/e2e_v2/tier4_realworld.test.js'
  }
];

const results = [];
let totalExecuted = 0;
let totalPassed = 0;
let totalFailed = 0;
const overallStartTime = Date.now();

console.log('='.repeat(80));
console.log('  KEYSTONE E2E V2 FULL TEST SUITE RUNNER');
console.log('  Coverage: Features F01–F35 across Tiers 1–4');
console.log('  Mode: Opaque-Box Native Node.js Test Runner');
console.log('='.repeat(80));
console.log('');

function runTier(index) {
  if (index >= TIERS.length) {
    printSummary();
    return;
  }

  const { tier, file } = TIERS[index];
  const absPath = path.resolve(__dirname, '../../', file);
  const startTime = Date.now();

  console.log(`>>> Running ${tier} [${file}]...`);

  const child = spawn(process.execPath, ['--test', absPath], {
    stdio: ['inherit', 'pipe', 'pipe'],
    shell: false
  });

  let stdout = '';
  let stderr = '';

  child.stdout.on('data', data => {
    stdout += data.toString();
  });

  child.stderr.on('data', data => {
    stderr += data.toString();
  });

  child.on('close', code => {
    const duration = Date.now() - startTime;

    // Parse counts from stdout:
    // ℹ tests 175
    // ℹ pass 175
    // ℹ fail 0
    let passCount = 0;
    let failCount = 0;
    let testsCount = 0;

    const passMatch = stdout.match(/ℹ pass (\d+)/);
    const failMatch = stdout.match(/ℹ fail (\d+)/);
    const testsMatch = stdout.match(/ℹ tests (\d+)/);

    if (passMatch) passCount = parseInt(passMatch[1], 10);
    if (failMatch) failCount = parseInt(failMatch[1], 10);
    if (testsMatch) testsCount = parseInt(testsMatch[1], 10);

    totalExecuted += testsCount;
    totalPassed += passCount;
    totalFailed += failCount;

    const status = (code === 0 && failCount === 0) ? 'OK' : 'FAIL';
    results.push({
      tier,
      pass: passCount,
      fail: failCount,
      duration: `${duration}ms`,
      status
    });

    if (code === 0) {
      console.log(`    PASS: ${passCount} tests passed (${duration}ms)\n`);
    } else {
      console.error(`    FAIL: ${failCount} tests failed (${duration}ms)\n`);
      if (stderr) console.error(stderr);
    }

    runTier(index + 1);
  });
}

function printSummary() {
  const totalDuration = Date.now() - overallStartTime;

  console.log('='.repeat(80));
  console.log('  E2E V2 TEST EXECUTION SUMMARY REPORT (F01–F35)');
  console.log('='.repeat(80));
  console.log('| Tier / Suite                                                | Pass | Fail | Duration  | Status |');
  console.log('|:------------------------------------------------------------|:----:|:----:|:---------:|:------:|');

  for (const r of results) {
    const tierPadded = r.tier.padEnd(58, ' ');
    const passPadded = String(r.pass).padStart(4, ' ');
    const failPadded = String(r.fail).padStart(4, ' ');
    const durPadded = r.duration.padStart(9, ' ');
    const statusPadded = r.status.padStart(6, ' ');
    console.log(`| ${tierPadded} | ${passPadded} | ${failPadded} | ${durPadded} | ${statusPadded} |`);
  }

  console.log('-'.repeat(80));
  console.log(`Total Tests Executed: ${totalExecuted}`);
  console.log(`Total Passed:         ${totalPassed}`);
  console.log(`Total Failed:         ${totalFailed}`);
  console.log(`Total Duration:       ${totalDuration}ms`);
  console.log('='.repeat(80));

  if (totalFailed === 0) {
    console.log('\nE2E v2 Suite Verification: 100% GREEN (ALL TIERS PASSING)\n');
    process.exit(0);
  } else {
    console.error(`\nE2E v2 Suite Verification FAILED: ${totalFailed} tests failed.\n`);
    process.exit(1);
  }
}

runTier(0);
