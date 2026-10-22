'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { generate } = require('../packages/prompt-engine/src/engine');
const { playbooks } = require('../packages/prompt-engine/src/playbooks');
const { compilePrompt } = require('../packages/prompt-engine/src/prompt-compiler');

test('KEYSTONE preserves plan.v1 and six-part PromptAnatomy', () => {
  const plan = generate('build a web app for creators');
  assert.equal(plan.contract, 'plan.v1');
  assert.equal(plan.domain.id, 'software');
  assert.equal(plan.path.length, 6);
  for (const step of plan.path) {
    for (const key of ['role','task','context','constraints','outputFormat','reasoning']) assert.ok(step.prompt[key]);
    assert.ok(step.promptText.includes('## ROLE'));
  }
});

test('KEYSTONE preserves all 13 domain playbooks', () => assert.equal(playbooks.length, 13));

test('compiler remains model-agnostic with chat and reasoning profiles', () => {
  const p = { role:'Expert',task:'Do work',context:['Goal'],constraints:['Be precise'],outputFormat:'JSON',reasoning:'Check trade-offs' };
  assert.ok(compilePrompt(p).includes('## ROLE'));
  assert.equal(compilePrompt(p,{profile:'chat'})[0].role,'system');
  assert.ok(compilePrompt(p,{profile:'reasoning'}).includes('## REASONING OBJECTIVE'));
});
