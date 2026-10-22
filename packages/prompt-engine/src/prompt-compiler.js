'use strict';

const REQUIRED = ['role', 'task', 'context', 'constraints', 'outputFormat', 'reasoning'];

function validatePromptAnatomy(prompt) {
  if (!prompt || typeof prompt !== 'object') throw new TypeError('Prompt must be an object');
  for (const field of REQUIRED) {
    if (!prompt[field]) throw new Error(`Prompt missing required field: "${field}"`);
  }
  if (!Array.isArray(prompt.context)) throw new TypeError('Prompt context must be an array');
  if (!Array.isArray(prompt.constraints)) throw new TypeError('Prompt constraints must be an array');
  return true;
}

function compileToMarkdown(prompt) {
  validatePromptAnatomy(prompt);
  return [
    `## ROLE\n${prompt.role}`,
    `## TASK\n${prompt.task}`,
    `## CONTEXT\n${prompt.context.filter(Boolean).join('\n')}`,
    `## CONSTRAINTS\n${prompt.constraints.map(x => `- ${x}`).join('\n')}`,
    `## OUTPUT FORMAT\n${prompt.outputFormat}`,
    `## REASONING\n${prompt.reasoning}`
  ].join('\n\n');
}

function compileToChatMessages(prompt) {
  validatePromptAnatomy(prompt);
  return [
    { role: 'system', content: `Identity & Role:\n${prompt.role}\n\nOperational Constraints:\n${prompt.constraints.map(x => `- ${x}`).join('\n')}` },
    { role: 'user', content: `## TASK\n${prompt.task}\n\n## CONTEXT\n${prompt.context.join('\n')}\n\n## OUTPUT FORMAT\n${prompt.outputFormat}\n\n## REASONING OBJECTIVE\n${prompt.reasoning}` }
  ];
}

function compileForReasoningModel(prompt) {
  validatePromptAnatomy(prompt);
  return [
    `## ROLE & PERSPECTIVE\n${prompt.role}`,
    `## OBJECTIVE\n${prompt.task}`,
    `## CONTEXT & DEPENDENCIES\n${prompt.context.filter(Boolean).join('\n')}`,
    `## CONSTRAINTS\n${prompt.constraints.map(x => `- ${x}`).join('\n')}`,
    `## DELIVERABLE CONTRACT\n${prompt.outputFormat}`,
    '## REASONING OBJECTIVE\nAnalyze requirements holistically and verify edge cases before producing the deliverable.'
  ].join('\n\n');
}

function compilePrompt(prompt, options = {}) {
  const profile = options.profile || 'standard';
  if (profile === 'chat') return compileToChatMessages(prompt);
  if (profile === 'reasoning') return compileForReasoningModel(prompt);
  return compileToMarkdown(prompt);
}

module.exports = { validatePromptAnatomy, compileToMarkdown, compileToChatMessages, compileForReasoningModel, compilePrompt };
