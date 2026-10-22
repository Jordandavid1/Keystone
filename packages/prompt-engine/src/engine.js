'use strict';
const { playbooks } = require('./playbooks');
const { compilePrompt } = require('./prompt-compiler');

function normalizeGoal(goal) { return String(goal || '').trim().replace(/^(i want to|help me|how do i|i need to)\s+/i, ''); }
function classifyDomain(goal) {
  const text = goal.toLowerCase();
  let best = playbooks.find(x => x.id === 'general'); let bestScore = 0; let runnerUp = null;
  for (const item of playbooks) {
    if (item.id === 'general') continue;
    const score = item.keywords.reduce((n, k) => n + (text.includes(k) ? 1 : 0), 0);
    if (score > bestScore) { runnerUp = best; best = item; bestScore = score; }
  }
  return { playbook: best, confidence: bestScore ? Math.min(0.5 + bestScore * 0.15, 0.95) : 0.4, runnerUp: runnerUp && runnerUp.id !== 'general' ? runnerUp.id : null };
}
function extractSignals(goal, answers = {}) {
  const timeframe = goal.match(/\b\d+\s+(?:days?|weeks?|months?)\b/i);
  return { audience: answers.audience || null, timeframe: answers.timeframe || (timeframe ? timeframe[0] : null), budget: answers.budget || null, level: answers.level || null, tools: answers.tools || [], ...answers };
}
function buildStepPromptAnatomy(step, index, total, playbook, signals, rawGoal) {
  return {
    role: `Senior Expert in ${playbook.label}`,
    task: `${step.title}: ${step.objective}`,
    context: [
      `Overall Goal: ${rawGoal}`,
      `Execution Sequence: Step ${index + 1} of ${total} in the "${playbook.label}" path.`,
      signals.timeframe ? `Timeframe Constraint: ${signals.timeframe}` : null,
      signals.audience ? `Target Audience: ${signals.audience}` : null,
      index > 0 ? `<previous_step_output>\n[Insert deliverable output from Step ${index} here]\n</previous_step_output>` : null
    ].filter(Boolean),
    constraints: ['Be specific, concrete, and directly actionable.','Eliminate generic boilerplate and filler.','State operational assumptions explicitly.','Preserve the user goal and authoritative KEYSTONE context.'],
    outputFormat: `Deliverable format: ${step.doneWhen}`,
    reasoning: 'Analyze structural trade-offs, failure modes, and edge cases before producing the deliverable.'
  };
}
function generate(goal, options = {}) {
  if (!goal || String(goal).trim().length === 0) return { error: { code: 'invalid_request', message: 'Goal is required.' } };
  const normalized = normalizeGoal(goal); const match = classifyDomain(normalized); const p = match.playbook;
  const answers = options.answers || {}; const signals = extractSignals(goal, answers); const maxQuestions = Math.min(options.maxQuestions ?? 3, 5);
  const clarifyingQuestions = []; const assumptions = [];
  for (const s of p.criticalSlots) {
    if (!answers[s.id]) { assumptions.push({ slot: s.id, text: s.assumption }); if (clarifyingQuestions.length < maxQuestions) clarifyingQuestions.push({ id: s.id, question: `What is the target ${s.id.replace(/_/g,' ')}?`, why: s.why, assumption: s.assumption }); }
  }
  const path = p.path.map((step, index) => { const prompt = buildStepPromptAnatomy(step,index,p.path.length,p,signals,goal); return { step:index+1, ...step, prompt, promptText:compilePrompt(prompt,{profile:options.profile || 'standard'}) }; });
  return { contract:'plan.v1',engine:'local-heuristic@2.0.0',goal,intent:`You want to ${normalized} - ending with ${p.outcome}.`,domain:{id:p.id,label:p.label,confidence:match.confidence,runnerUp:match.runnerUp},signals,clarifyingQuestions,assumptions,path,meta:{stepCount:path.length,questionCount:clarifyingQuestions.length,generatedAt:new Date().toISOString(),routingHints:{pathMapping:'reasoning',promptFormatting:'fast'}} };
}
module.exports = { generate, buildStepPromptAnatomy, classifyDomain, extractSignals };
