"""
KEYSTONE Domain Playbooks (Python Implementation)
Byte-accurate, contract-compliant mirror of packages/prompt-engine/src/playbooks.js.
Preserves the 13 canonical domain playbooks plus 3 extended operating modes
(14 nsfw, 15 hacker, 16 freedom/YOLO) and 6-step path structures per Bible §2 Invariant 14, §6.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple


@dataclass(frozen=True)
class CriticalSlot:
    id: str
    why: str
    assumption: str

    def to_dict(self) -> Dict[str, str]:
        return {"id": self.id, "why": self.why, "assumption": self.assumption}


@dataclass(frozen=True)
class PathStep:
    title: str
    objective: str
    doneWhen: str

    def to_dict(self) -> Dict[str, str]:
        return {"title": self.title, "objective": self.objective, "doneWhen": self.doneWhen}


@dataclass(frozen=True)
class Playbook:
    id: str
    label: str
    keywords: List[str]
    outcome: str
    criticalSlots: List[CriticalSlot]
    path: List[PathStep]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "keywords": list(self.keywords),
            "outcome": self.outcome,
            "criticalSlots": [s.to_dict() for s in self.criticalSlots],
            "path": [p.to_dict() for p in self.path]
        }


def _common_steps(noun: str) -> List[PathStep]:
    return [
        PathStep("Define the objective", f"Clarify the exact {noun} outcome and success criteria.", "A written definition of done."),
        PathStep("Gather requirements", "Collect constraints, inputs, references, and dependencies.", "A verified requirements checklist."),
        PathStep("Design the approach", "Choose the structure, sequence, and implementation strategy.", "An approved execution design."),
        PathStep("Build the core", "Implement the highest-value working path first.", "A functioning core deliverable."),
        PathStep("Integrate and test", "Connect supporting pieces and test realistic scenarios.", "Passing acceptance tests and issue log."),
        PathStep("Polish and deliver", "Review against the objective and package the final result.", "A production-ready final deliverable.")
    ]


# The 16 playbooks: 13 preserved from the KEYSTONE baseline + 3 extended operating modes
CANONICAL_PLAYBOOKS: List[Playbook] = [
    Playbook(
        id="software",
        label="Build software",
        keywords=["app", "software", "website", "code", "api", "saas"],
        outcome="a working shipped version real users can try",
        criticalSlots=[
            CriticalSlot("audience", "Tailor UX and scope.", "early adopters"),
            CriticalSlot("platform", "Choose the implementation target.", "modern web application")
        ],
        path=_common_steps("software")
    ),
    Playbook(
        id="writing",
        label="Write something",
        keywords=["write", "book", "novel", "essay", "story"],
        outcome="a finished polished piece that lands with its readers",
        criticalSlots=[
            CriticalSlot("audience", "Set voice and depth.", "general readers"),
            CriticalSlot("format", "Set structure and length.", "long-form")
        ],
        path=_common_steps("writing")
    ),
    Playbook(
        id="marketing",
        label="Market and grow",
        keywords=["market", "growth", "ads", "seo", "campaign"],
        outcome="a measurable stream of the right people discovering and acting",
        criticalSlots=[
            CriticalSlot("audience", "Focus messaging.", "decision-makers"),
            CriticalSlot("channel", "Focus distribution.", "organic and niche communities")
        ],
        path=_common_steps("campaign")
    ),
    Playbook(
        id="business",
        label="Start or grow a business",
        keywords=["business", "startup", "revenue", "sales", "offer"],
        outcome="a viable offer with paying customers and a path to profit",
        criticalSlots=[
            CriticalSlot("offering", "Define the commercial deliverable.", "digital product"),
            CriticalSlot("budget", "Set constraints.", "lean bootstrap")
        ],
        path=_common_steps("business")
    ),
    Playbook(
        id="learning",
        label="Learn a skill",
        keywords=["learn", "study", "course", "skill", "exam"],
        outcome="demonstrable competence rather than familiarity",
        criticalSlots=[
            CriticalSlot("level", "Set prerequisites.", "beginner"),
            CriticalSlot("timeframe", "Set pace.", "30 days")
        ],
        path=_common_steps("learning plan")
    ),
    Playbook(
        id="career",
        label="Career move",
        keywords=["job", "career", "resume", "interview", "promotion"],
        outcome="the target role or offer on strong terms",
        criticalSlots=[
            CriticalSlot("role", "Tailor positioning.", "senior practitioner"),
            CriticalSlot("timeframe", "Set search cadence.", "60 days")
        ],
        path=_common_steps("career move")
    ),
    Playbook(
        id="content",
        label="Create content or a channel",
        keywords=["podcast", "youtube", "newsletter", "channel", "content"],
        outcome="a consistent show with a growing engaged audience",
        criticalSlots=[
            CriticalSlot("topic", "Focus positioning.", "practical expertise"),
            CriticalSlot("format", "Set production needs.", "weekly deep dive")
        ],
        path=_common_steps("content system")
    ),
    Playbook(
        id="research",
        label="Research and analysis",
        keywords=["research", "analysis", "benchmark", "study", "evaluate"],
        outcome="a defensible evidence-backed answer ready for action",
        criticalSlots=[
            CriticalSlot("topic", "Set boundaries.", "market trend"),
            CriticalSlot("depth", "Set method.", "executive briefing")
        ],
        path=_common_steps("research")
    ),
    Playbook(
        id="design",
        label="Design and visual work",
        keywords=["design", "ui", "ux", "branding", "visual", "wireframe"],
        outcome="a finished visual that is on-brief and production-ready",
        criticalSlots=[
            CriticalSlot("medium", "Set output constraints.", "responsive digital"),
            CriticalSlot("style", "Set visual direction.", "clean modern")
        ],
        path=_common_steps("design")
    ),
    Playbook(
        id="fitness",
        label="Health and fitness",
        keywords=["workout", "fitness", "exercise", "nutrition", "gym"],
        outcome="measurable sustainable progress",
        criticalSlots=[
            CriticalSlot("goal_type", "Set training direction.", "strength and endurance"),
            CriticalSlot("schedule", "Set realistic cadence.", "three days weekly")
        ],
        path=_common_steps("fitness plan")
    ),
    Playbook(
        id="events",
        label="Plan an event or trip",
        keywords=["event", "trip", "travel", "wedding", "itinerary"],
        outcome="a smooth experience matching the vision and budget",
        criticalSlots=[
            CriticalSlot("guest_count", "Set capacity.", "small group"),
            CriticalSlot("budget", "Set constraints.", "moderate budget")
        ],
        path=_common_steps("event")
    ),
    Playbook(
        id="finance",
        label="Personal finance",
        keywords=["finance", "invest", "budget", "saving", "debt"],
        outcome="a clear money system moving toward the target",
        criticalSlots=[
            CriticalSlot("focus", "Prioritize the plan.", "stability and long-term growth"),
            CriticalSlot("timeframe", "Set horizon.", "twelve months")
        ],
        path=_common_steps("financial plan")
    ),
    # --- Extended operating modes added on top of the original 13 ---
    Playbook(
        id="nsfw",
        label="Mature and adult creative work",
        keywords=["nsfw", "adult", "explicit", "erotic", "mature", "intimate", "18+", "steamy"],
        outcome="a finished adult-oriented work that lands with its intended grown-up audience",
        criticalSlots=[
            CriticalSlot("audience", "Confirm the audience is 18+ and how it is gated.", "verified adult audience"),
            CriticalSlot("rating", "Set explicitness and platform limits.", "suggestive rather than explicit")
        ],
        path=_common_steps("adult creative work")
    ),
    Playbook(
        id="hacker",
        label="Security research and red team",
        keywords=["hacker", "hacking", "security", "pentest", "penetration test", "vulnerability", "exploit", "red team", "ctf", "threat model", "harden"],
        outcome="a verified finding, a reproducible proof, and a concrete remediation plan",
        criticalSlots=[
            CriticalSlot("authorization", "Confirm written scope and permission.", "owned or explicitly authorized systems only"),
            CriticalSlot("target", "Define the attack surface in scope.", "a lab or staging environment")
        ],
        path=_common_steps("security assessment")
    ),
    Playbook(
        id="freedom",
        label="Freedom mode (YOLO)",
        keywords=["unrestricted", "yolo", "full freedom", "no limits", "autopilot", "just do it", "ship it", "hands off"],
        outcome="a shipped deliverable produced in one autonomous pass with the decisions already made",
        criticalSlots=[
            CriticalSlot("scope", "Bound the autonomous run.", "the single stated objective and its direct dependencies"),
            CriticalSlot("risk_tolerance", "Set how far to go unattended.", "reversible changes only")
        ],
        path=_common_steps("autonomous run")
    ),
    Playbook(
        id="general",
        label="Anything else",
        keywords=[],
        outcome="the concrete result requested",
        criticalSlots=[
            CriticalSlot("success_metric", "Know when complete.", "practical completion")
        ],
        path=_common_steps("goal")
    )
]

PLAYBOOKS_BY_ID: Dict[str, Playbook] = {p.id: p for p in CANONICAL_PLAYBOOKS}
PLAYBOOK_IDS: List[str] = [p.id for p in CANONICAL_PLAYBOOKS]

# Friendly aliases so the requested mode names resolve to their playbook ids
PLAYBOOK_ALIASES: Dict[str, str] = {
    "nsfw_mode": "nsfw",
    "adult": "nsfw",
    "hacker_mode": "hacker",
    "hacking": "hacker",
    "red_team": "hacker",
    "yolo": "freedom",
    "yolo_mode": "freedom",
    "unrestricted": "freedom",
    "fully_unrestricted": "freedom",
    "full_freedom": "freedom",
}


class PlaybookRegistry:
    """Registry providing fast lookup, listing, and domain classification across playbooks."""

    @classmethod
    def list_playbooks(cls) -> List[Playbook]:
        return list(CANONICAL_PLAYBOOKS)

    @classmethod
    def list_ids(cls) -> List[str]:
        return list(PLAYBOOK_IDS)

    @classmethod
    def resolve_id(cls, playbook_id: str | None) -> str:
        """Canonicalizes an id or alias; unknown ids fall back to 'general'."""
        key = (str(playbook_id) if playbook_id else "").strip().lower()
        key = key.replace("-", "_").replace(" ", "_")
        key = PLAYBOOK_ALIASES.get(key, key)
        return key if key in PLAYBOOKS_BY_ID else "general"

    @classmethod
    def get(cls, playbook_id: str | None) -> Playbook:
        return PLAYBOOKS_BY_ID[cls.resolve_id(playbook_id)]

    @classmethod
    def classify(cls, goal: str) -> Tuple[Playbook, float, Optional[str]]:
        """Classify a goal into a playbook using keyword scoring matching engine.js."""
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
        return best, confidence, runner_up_id
