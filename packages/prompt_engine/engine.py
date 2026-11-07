"""
KEYSTONE Original Prompt Engine Compatibility Gateway (Python Implementation)
Implements `generate(goal, options) -> plan.v1`, goal normalization, domain classification,
signal extraction, and step anatomy construction per Bible §2 Invariant 12, §6.
"""

from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from packages.prompt_engine.playbooks import PlaybookRegistry, Playbook, CANONICAL_PLAYBOOKS, PLAYBOOKS_BY_ID
from packages.prompt_engine.compiler import compile_prompt


def normalize_goal(goal: str | None) -> str:
    """Strips conversational prefixes like 'i want to', 'help me', 'how do i', 'i need to'."""
    text = str(goal or "").strip()
    return re.sub(r"^(i want to|help me|how do i|i need to)\s+", "", text, flags=re.IGNORECASE)


def classify_domain(goal: str) -> Dict[str, Any]:
    """Classifies a goal into a playbook, returning {playbook, confidence, runnerUp}."""
    text = (goal or "").lower()
    best: Playbook = PLAYBOOKS_BY_ID["general"]
    best_score = 0
    runner_up: Optional[Playbook] = None

    for item in CANONICAL_PLAYBOOKS:
        if item.id == "general":
            continue
        score = sum(1 for k in item.keywords if k in text)
        if score > best_score:
            runner_up = best
            best = item
            best_score = score

    confidence = min(0.5 + best_score * 0.15, 0.95) if best_score > 0 else 0.4
    runner_up_id = runner_up.id if (runner_up and runner_up.id != "general") else None

    return {
        "playbook": best,
        "confidence": confidence,
        "runnerUp": runner_up_id
    }


def extract_signals(goal: str, answers: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Extracts explicit constraints and implicit timeline/budget signals from goal and answers."""
    ans = answers or {}
    timeframe_match = re.search(r"\b\d+\s+(?:days?|weeks?|months?)\b", goal or "", re.IGNORECASE)
    timeframe = ans.get("timeframe") or (timeframe_match.group(0) if timeframe_match else None)

    signals: Dict[str, Any] = {
        "audience": ans.get("audience"),
        "timeframe": timeframe,
        "budget": ans.get("budget"),
        "level": ans.get("level"),
        "tools": ans.get("tools", []),
    }
    signals.update(ans)
    return signals


def build_step_prompt_anatomy(
    step: Any,
    index: int,
    total: int,
    playbook: Playbook,
    signals: Dict[str, Any],
    raw_goal: str
) -> Dict[str, Any]:
    """Constructs the six-part PromptAnatomy for an individual execution step."""
    step_title = getattr(step, "title", None) or (step["title"] if isinstance(step, dict) else str(step))
    step_obj = getattr(step, "objective", None) or (step["objective"] if isinstance(step, dict) else "")
    step_done = getattr(step, "doneWhen", None) or (step["doneWhen"] if isinstance(step, dict) else "")

    context: List[str] = [
        f"Overall Goal: {raw_goal}",
        f'Execution Sequence: Step {index + 1} of {total} in the "{playbook.label}" path.',
    ]
    if playbook.domain_context and playbook.domain_context.get("domain_brief"):
        context.append(f"Domain Context: {playbook.domain_context['domain_brief']}")
    if playbook.skills:
        skill_names = ", ".join(s.get("name", s.get("id", "")) for s in playbook.skills)
        context.append(f"Bound Domain Skills: {skill_names}")
    if signals.get("timeframe"):
        context.append(f"Timeframe Constraint: {signals['timeframe']}")
    if signals.get("audience"):
        context.append(f"Target Audience: {signals['audience']}")
    if index > 0:
        context.append(
            f"<previous_step_output>\n[Insert deliverable output from Step {index} here]\n</previous_step_output>"
        )

    return {
        "role": f"Senior Expert in {playbook.label}",
        "task": f"{step_title}: {step_obj}",
        "context": context,
        "constraints": [
            "Be specific, concrete, and directly actionable.",
            "Eliminate generic boilerplate and filler.",
            "State operational assumptions explicitly.",
            "Preserve the user goal and authoritative KEYSTONE context."
        ],
        "outputFormat": f"Deliverable format: {step_done}",
        "reasoning": "Analyze structural trade-offs, failure modes, and edge cases before producing the deliverable."
    }


def generate(goal: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Original KEYSTONE planning engine entry point.
    Compatibility contract: `generate(goal, options) -> plan.v1`.
    """
    if not goal or not str(goal).strip():
        return {
            "error": {
                "code": "invalid_request",
                "message": "Goal is required."
            }
        }

    opts = options or {}
    normalized = normalize_goal(goal)
    match_res = classify_domain(normalized)
    p: Playbook = match_res["playbook"]

    answers = opts.get("answers", {})
    signals = extract_signals(goal, answers)
    max_questions = min(opts.get("maxQuestions", 3), 5)

    clarifying_questions: List[Dict[str, Any]] = []
    assumptions: List[Dict[str, str]] = []

    for s in p.criticalSlots:
        if s.id not in answers:
            assumptions.append({"slot": s.id, "text": s.assumption})
            if len(clarifying_questions) < max_questions:
                clarifying_questions.append({
                    "id": s.id,
                    "question": f"What is the target {s.id.replace('_', ' ')}?",
                    "why": s.why,
                    "assumption": s.assumption
                })

    path: List[Dict[str, Any]] = []
    total_steps = len(p.path)
    profile = opts.get("profile", "standard")

    for index, step in enumerate(p.path):
        anatomy = build_step_prompt_anatomy(step, index, total_steps, p, signals, goal)
        compiled_text = compile_prompt(anatomy, {"profile": profile})
        path.append({
            "step": index + 1,
            "title": step.title,
            "objective": step.objective,
            "doneWhen": step.doneWhen,
            "prompt": anatomy,
            "promptText": compiled_text
        })

    return {
        "contract": "plan.v1",
        "engine": "local-heuristic@2.0.0",
        "goal": goal,
        "intent": f"You want to {normalized} - ending with {p.outcome}.",
        "domain": {
            "id": p.id,
            "label": p.label,
            "confidence": match_res["confidence"],
            "runnerUp": match_res["runnerUp"],
            "context": p.domain_context,
            "useCases": p.use_cases,
            "skills": p.skills,
        },
        "signals": signals,
        "clarifyingQuestions": clarifying_questions,
        "assumptions": assumptions,
        "path": path,
        "meta": {
            "stepCount": len(path),
            "questionCount": len(clarifying_questions),
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "routingHints": {
                "pathMapping": "reasoning",
                "promptFormatting": "fast"
            }
        }
    }
