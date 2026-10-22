'use strict';

const META_PROMPT_CORE = [
  'You are an expert strategist and prompt engineer.',
  'The user gives a raw goal.',
  'Restate the true goal clearly and ask only essential clarifying questions.',
  'Break the goal into an ordered sequence of small, finishable steps.',
  'For each step, create a ready-to-use prompt with expert role, task, context, constraints, output format, and reasoning objective.',
  'Keep the semantic contract model-agnostic; KEYSTONE owns provider-specific compilation.'
].join(' ');

module.exports = { META_PROMPT_CORE };
