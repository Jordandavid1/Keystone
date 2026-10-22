'use strict';

function pb(id, label, keywords, outcome, slots, steps) {
  return { id, label, keywords, outcome, criticalSlots: slots, path: steps.map(([title, objective, doneWhen]) => ({ title, objective, doneWhen })) };
}
const common = (noun) => [
  ['Define the objective', `Clarify the exact ${noun} outcome and success criteria.`, 'A written definition of done.'],
  ['Gather requirements', 'Collect constraints, inputs, references, and dependencies.', 'A verified requirements checklist.'],
  ['Design the approach', 'Choose the structure, sequence, and implementation strategy.', 'An approved execution design.'],
  ['Build the core', 'Implement the highest-value working path first.', 'A functioning core deliverable.'],
  ['Integrate and test', 'Connect supporting pieces and test realistic scenarios.', 'Passing acceptance tests and issue log.'],
  ['Polish and deliver', 'Review against the objective and package the final result.', 'A production-ready final deliverable.']
];
const slot = (id, why, assumption) => ({ id, why, assumption });
const playbooks = [
  pb('software','Build software',['app','software','website','code','api','saas'],'a working shipped version real users can try',[slot('audience','Tailor UX and scope.','early adopters'),slot('platform','Choose the implementation target.','modern web application')],common('software')),
  pb('writing','Write something',['write','book','novel','essay','story'],'a finished polished piece that lands with its readers',[slot('audience','Set voice and depth.','general readers'),slot('format','Set structure and length.','long-form')],common('writing')),
  pb('marketing','Market and grow',['market','growth','ads','seo','campaign'],'a measurable stream of the right people discovering and acting',[slot('audience','Focus messaging.','decision-makers'),slot('channel','Focus distribution.','organic and niche communities')],common('campaign')),
  pb('business','Start or grow a business',['business','startup','revenue','sales','offer'],'a viable offer with paying customers and a path to profit',[slot('offering','Define the commercial deliverable.','digital product'),slot('budget','Set constraints.','lean bootstrap')],common('business')),
  pb('learning','Learn a skill',['learn','study','course','skill','exam'],'demonstrable competence rather than familiarity',[slot('level','Set prerequisites.','beginner'),slot('timeframe','Set pace.','30 days')],common('learning plan')),
  pb('career','Career move',['job','career','resume','interview','promotion'],'the target role or offer on strong terms',[slot('role','Tailor positioning.','senior practitioner'),slot('timeframe','Set search cadence.','60 days')],common('career move')),
  pb('content','Create content or a channel',['podcast','youtube','newsletter','channel','content'],'a consistent show with a growing engaged audience',[slot('topic','Focus positioning.','practical expertise'),slot('format','Set production needs.','weekly deep dive')],common('content system')),
  pb('research','Research and analysis',['research','analysis','benchmark','study','evaluate'],'a defensible evidence-backed answer ready for action',[slot('topic','Set boundaries.','market trend'),slot('depth','Set method.','executive briefing')],common('research')),
  pb('design','Design and visual work',['design','ui','ux','branding','visual','wireframe'],'a finished visual that is on-brief and production-ready',[slot('medium','Set output constraints.','responsive digital'),slot('style','Set visual direction.','clean modern')],common('design')),
  pb('fitness','Health and fitness',['workout','fitness','exercise','nutrition','gym'],'measurable sustainable progress',[slot('goal_type','Set training direction.','strength and endurance'),slot('schedule','Set realistic cadence.','three days weekly')],common('fitness plan')),
  pb('events','Plan an event or trip',['event','trip','travel','wedding','itinerary'],'a smooth experience matching the vision and budget',[slot('guest_count','Set capacity.','small group'),slot('budget','Set constraints.','moderate budget')],common('event')),
  pb('finance','Personal finance',['finance','invest','budget','saving','debt'],'a clear money system moving toward the target',[slot('focus','Prioritize the plan.','stability and long-term growth'),slot('timeframe','Set horizon.','twelve months')],common('financial plan')),
  pb('general','Anything else',[],'the concrete result requested',[slot('success_metric','Know when complete.','practical completion')],common('goal'))
];
module.exports = { playbooks };
